# -*- coding: utf-8 -*-
import os
import requests
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

# ========== 配置区 ==========
SOURCE_URL = "https://sttottv.ccwu.cc/ZB.TXT"
EXTRA_URL = "http://203.135.100.107:7681/iptasd.txt"
LOCAL_TXT_PATH = "uzi.txt"
OUTPUT_FILE = "live.txt"
TIMEOUT = 8
MAX_WORKERS = 10
READ_BYTES = 2048
NEED_GROUPS = ["4K频道", "轮播剧场"]
UZI_GROUP_NAME = "东方有线"
# =============================

def check_stream(url: str):
    if not (url.startswith("http://") or url.startswith("https://")):
        return (True, 0.0, url)
    headers = {
        "User-Agent": "VLC/3.0.18 LibVLC/3.0.18"
    }
    for attempt in range(2):
        try:
            t0 = time.perf_counter()
            with requests.get(
                url,
                timeout=TIMEOUT,
                headers=headers,
                stream=True,
                allow_redirects=True
            ) as r:
                if not (200 <= r.status_code < 400):
                    continue
                next(r.iter_content(chunk_size=READ_BYTES), None)
                cost = time.perf_counter() - t0
                return (True, cost, url)
        except Exception as e:
            print(f"[测速] 失败 {url} | {str(e)}")
            time.sleep(0.3)
    return (False, 999.0, url)


def fetch_text_auto_decode(url):
    print(f"[网络] 开始拉取：{url}")
    try:
        resp = requests.get(url, timeout=TIMEOUT)
        resp.raise_for_status()
        raw_bytes = resp.content
        enc_list = ["utf-8", "gb18030", "gbk", "latin-1"]
        for enc in enc_list:
            try:
                text = raw_bytes.decode(enc)
                print(f"[网络] {url} 编码识别成功：{enc}")
                return text
            except UnicodeDecodeError:
                continue
        print(f"[警告] {url} 全部编码解析失败")
        return ""
    except Exception as e:
        print(f"[网络] 获取源失败 {url} , error:{e}")
        return ""


def read_local_file(filepath):
    print(f"[本地] 读取文件：{filepath}")
    if not os.path.exists(filepath):
        print(f"[警告] 本地文件 {filepath} 不存在")
        return ""
    with open(filepath, "rb") as f:
        raw_bytes = f.read()
    enc_list = ["utf-8", "gb18030", "gbk", "latin-1"]
    for enc in enc_list:
        try:
            text = raw_bytes.decode(enc)
            print(f"[本地] {filepath}，编码：{enc}")
            return text
        except UnicodeDecodeError:
            continue
    print(f"[警告] 本地文件 {filepath} 解码失败")
    return ""


def normalize_uzi_content(raw_text):
    if not raw_text.strip():
        print("[uzi] uzi.txt 为空")
        return ""
    lines = [ln.strip() for ln in raw_text.splitlines() if ln.strip()]
    if any(",#genre#" in ln for ln in lines):
        print("[uzi] 检测：自带分组标记，无需修改")
        return raw_text
    print(f"[uzi] 检测：无分组标记，自动添加【{UZI_GROUP_NAME}】分组头")
    out = [f"{UZI_GROUP_NAME},#genre#"]
    out.extend(lines)
    return "\n".join(out)


def parse_txt_content(content):
    if not content.strip():
        return []
    groups_out = []
    current_group = None
    lines = content.splitlines()
    for line in lines:
        s = line.strip()
        if not s:
            continue
        if s.endswith(",#genre#"):
            gname = s.rsplit(",#genre#", 1)[0].strip()
            current_group = {"group_name": gname, "items": [], "skip_test": False}
            groups_out.append(current_group)
            continue
        if current_group is not None and "," in s:
            name, url = s.split(",", 1)
            name = name.strip()
            url = url.strip()
            current_group["items"].append((name, url))
    return groups_out


def parse_m3u_content(content, default_group_name="未命名分组"):
    if not content.strip():
        return []
    lines = [x.strip() for x in content.splitlines() if x.strip()]
    items = []
    last_title = None
    for line in lines:
        if line.startswith("#EXTINF:"):
            if "," in line:
                last_title = line.split(",", 1)[1].strip()
            else:
                last_title = "未知频道"
        elif line.startswith("http://") or line.startswith("https://"):
            if last_title:
                items.append((last_title, line))
                last_title = None
    if items:
        return [{"group_name": default_group_name, "items": items, "skip_test": False}]
    return []


def auto_parse_source(content, guess_group):
    if not content:
        return []
    if content.lstrip().startswith("#EXTM3U"):
        print(f"[解析] 识别为 M3U 格式：{guess_group}")
        return parse_m3u_content(content, guess_group)
    else:
        print(f"[解析] 识别为传统 ,#genre# txt：{guess_group}")
        return parse_txt_content(content)


def render_groups(groups, delay_map):
    final_lines = []
    for g in groups:
        skip_test = g.get("skip_test", False)
        if skip_test:
            alive_items = [(0.0, name, url) for name, url in g["items"]]
        else:
            alive_items = []
            for name, url in g["items"]:
                ok, d = delay_map.get(url, (False, 999.0))
                if ok:
                    alive_items.append((d, name, url))
        if not alive_items:
            print(f"[渲染] 分组【{g['group_name']}】无可用频道，跳过")
            continue
        alive_items.sort(key=lambda x: x[0])
        final_lines.append(f"{g['group_name']},#genre#")
        for d, name, url in alive_items:
            final_lines.append(f"{name},{url}")
    return "\n".join(final_lines)


def process_all_content(main_text, extra_text, normalized_uzi):
    print("[合并] 开始解析 uzi 分组，标记免测速")
    dong_groups = parse_txt_content(normalized_uzi)
    for g in dong_groups:
        g["skip_test"] = True

    print("[合并] 解析主源、附加源")
    main_groups = auto_parse_source(main_text, "主源频道")
    extra_groups = auto_parse_source(extra_text, "附加频道")
    pick_extra = [g for g in extra_groups if g["group_name"] in NEED_GROUPS and len(g["items"]) > 0]

    all_groups = dong_groups + main_groups + pick_extra

    test_url_set = set()
    for g in all_groups:
        if g.get("skip_test") is True:
            continue
        for _name, url in g["items"]:
            test_url_set.add(url)

    print(f"[测速] 待检测链接数量：{len(test_url_set)}")
    delay_map = {}
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        future2url = {executor.submit(check_stream, u): u for u in test_url_set}
        for fut in as_completed(future2url):
            ok, cost, url = fut.result()
            delay_map[url] = (ok, cost)

    out_text = render_groups(all_groups, delay_map)
    return out_text


def main():
    # 【第一步：优先处理 uzi.txt，顺序前置】
    print("===== 阶段 1：处理本地 uzi.txt =====")
    raw_uzi = read_local_file(LOCAL_TXT_PATH)
    normalized_uzi = normalize_uzi_content(raw_uzi)

    if normalized_uzi:
        with open(LOCAL_TXT_PATH, "w", encoding="utf-8") as fw:
            fw.write(normalized_uzi)
        print("[uzi] 标准化内容已回写 uzi.txt")

    # 【第二步：再拉取两个远程源】
    print("\n===== 阶段 2：拉取远程源 =====")
    main_txt = fetch_text_auto_decode(SOURCE_URL)
    extra_txt = fetch_text_auto_decode(EXTRA_URL)

    # 【第三步：整合、测速、渲染输出】
    print("\n===== 阶段 3：整合全部源 =====")
    result = process_all_content(main_txt, extra_txt, normalized_uzi)

    if not result.strip():
        print("[兜底] 测速后全部为空，输出标准化 uzi")
        result = normalized_uzi

    with open(OUTPUT_FILE, "w", encoding="utf-8") as fw:
        fw.write(result)
    print(f"\n[完成] 结果写入 {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
