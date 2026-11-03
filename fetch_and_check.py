import requests
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

# ========== 配置区 ==========
SOURCE_URL = "https://stottv.ccwu.cc/ZB.TXT"
EXTRA_URL = "http://203.135.100.107:7681/iptasd.txt"
DONG_URL = "http://a.u9c.cn/5P1He0"
OUTPUT_FILE = "live.txt"
TIMEOUT = 10
MAX_WORKERS = 12
READ_BYTES = 2048
NEED_GROUPS = ["4K频道", "轮播剧场"]
DONG_GROUP_NAME = "东方有线"
# =============================

def check_stream(url: str):
    if not (url.startswith("http://") or url.startswith("https://")):
        return (True, 0.0, url)
    try:
        headers = {
            "User-Agent": "VLC/3.0.18 LibVLC/3.0.18"
        }
        t0 = time.perf_counter()
        with requests.get(
            url,
            timeout=TIMEOUT,
            headers=headers,
            stream=True,
            allow_redirects=True
        ) as r:
            if not (200 <= r.status_code < 400):
                return (False, 999.0, url)
            next(r.iter_content(chunk_size=READ_BYTES), None)
            cost = time.perf_counter() - t0
            return (True, cost, url)
    except Exception:
        return (False, 999.0, url)


def fetch_text(url):
    try:
        resp = requests.get(url, timeout=TIMEOUT)
        resp.raise_for_status()
        raw_bytes = resp.content
        try:
            text = raw_bytes.decode("gb18030")
        except Exception:
            text = raw_bytes.decode("utf-8", errors="replace")
        return text
    except Exception as e:
        print(f"⚠️ 获取源失败 {url} , error:{e}")
        return ""


def parse_txt_content(content):
    """解析 #genre# tvbox txt格式"""
    groups_out = []
    current_group = None
    lines = content.splitlines()
    for line in lines:
        s = line.strip()
        if not s:
            continue
        if s.endswith(",#genre#"):
            gname = s.rsplit(",#genre#",1)[0].strip()
            current_group = {"group_name": gname, "items": []}
            groups_out.append(current_group)
            continue
        if current_group is not None and "," in s:
            name, url = s.split(",",1)
            name = name.strip()
            url = url.strip()
            current_group["items"].append((name, url))
    return groups_out


def parse_m3u_to_group(content, group_name):
    """解析M3U，全部频道封装成指定分组，输出[(name,url)]"""
    items = []
    lines = content.splitlines()
    pending_name = None
    for line in lines:
        s = line.strip()
        if not s:
            continue
        if s.startswith("#EXTM3U"):
            continue
        if s.startswith("#EXTINF"):
            # 逗号后面是频道名称
            if "," in s:
                pending_name = s.split(",",1)[1].strip()
            else:
                pending_name = None
            continue
        # 不是注释，视为流地址
        if not s.startswith("#") and s.startswith("http"):
            if pending_name:
                items.append((pending_name, s))
            pending_name = None
    if len(items) > 0:
        return [{"group_name": group_name, "items": items}]
    return []


def process_all_content(main_text, extra_text, dong_text):
    # M3U解析东方有线
    dong_groups = parse_m3u_to_group(dong_text, DONG_GROUP_NAME)
    # 解析主源txt
    main_groups = parse_txt_content(main_text)
    # 解析iptasd.txt，只选取指定分组
    extra_groups = parse_txt_content(extra_text)
    pick_extra = [g for g in extra_groups if g["group_name"] in NEED_GROUPS and len(g["items"])>0]

    # 顺序：东方有线【第一位】→主源全部分组→4K频道、轮播剧场
    all_groups = dong_groups + main_groups + pick_extra

    # 收集全部待测速url
    all_tasks = []
    for g in all_groups:
        for _name, url in g["items"]:
            all_tasks.append(url)

    delay_map = {}
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        task_map = {executor.submit(check_stream, u): u for u in all_tasks}
        for future in as_completed(task_map):
            url = task_map[future]
            ok, delay, _ = future.result()
            delay_map[url] = (ok, delay)

    final_lines = []
    for g in all_groups:
        alive_items = []
        for name, url in g["items"]:
            ok, d = delay_map.get(url, (False, 999.0))
            if ok:
                alive_items.append((d, name, url))
        if not alive_items:
            print(f"ℹ️分组【{g['group_name']}】全部失效，跳过输出")
            continue
        alive_items.sort(key=lambda x:x[0])
        final_lines.append(f'{g["group_name"]},#genre#')
        for d, name, url in alive_items:
            final_lines.append(f"{name},{url}")
    return "\n".join(final_lines)


def main():
    print(f"1.拉取主上游源：{SOURCE_URL}")
    main_text = fetch_text(SOURCE_URL)
    print(f"2.拉取iptasd.txt：{EXTRA_URL}")
    extra_text = fetch_text(EXTRA_URL)
    print(f"3.拉取M3U东方有线源：{DONG_URL}")
    dong_text = fetch_text(DONG_URL)

    print("🚀全部频道测速，过滤失效源，组内延迟排序")
    result_text = process_all_content(main_text, extra_text, dong_text)

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(result_text)
    print(f"✅处理完毕，输出：{OUTPUT_FILE}
