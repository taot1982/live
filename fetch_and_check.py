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
            print("测速失败 {} | {}".format(url, str(e)))
            time.sleep(0.3)
    return (False, 999.0, url)


def fetch_text_auto_decode(url):
    try:
        resp = requests.get(url, timeout=TIMEOUT)
        resp.raise_for_status()
        raw_bytes = resp.content
        enc_list = ["utf-8", "gb18030", "gbk", "latin-1"]
        for enc in enc_list:
            try:
                text = raw_bytes.decode(enc)
                print("源 {} 使用编码：{}".format(url, enc))
                return text
            except UnicodeDecodeError:
                continue
        print("警告：{} 全部编码解析失败".format(url))
        return ""
    except Exception as e:
        print("获取源失败 {} , error:{}".format(url, e))
        return ""


def read_local_file(filepath):
    if not os.path.exists(filepath):
        print(f"警告：本地文件 {filepath} 不存在，跳过该分组")
        return ""
    with open(filepath, "rb") as f:
        raw_bytes = f.read()
    enc_list = ["utf-8", "gb18030", "gbk", "latin-1"]
    for enc in enc_list:
        try:
            text = raw_bytes.decode(enc)
            print(f"本地文件 {filepath}，编码：{enc}")
            return text
        except UnicodeDecodeError:
            continue
    print(f"警告：本地文件 {filepath} 解码失败")
    return ""


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


def parse_plain_txt_to_group(content, group_name):
    if not content.strip():
        return []
    items = []
    lines = content.splitlines()
    for line in lines:
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        if "," in s:
            name, url = s.split(",", 1)
            name = name.strip()
            url = url.strip()
            items.append((name, url))
    if len(items) > 0:
        return [{"group_name": group_name, "items": items, "skip_test": True}]
    return []


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
            print("分组【{}】无可用频道，跳过输出".format(g["group_name"]))
            continue
        alive_items.sort(key=lambda x: x[0])
        final_lines.append("{},#genre#".format(g["group_name"]))
        for d, name, url in alive_items:
            final_lines.append("{},{}".format(name, url))
    return "\n".join(final_lines)


def process_all_content(main_text, extra_text, uzi_text):
    # 东方有线放在最前面
    dong_groups = parse_plain_txt_to_group(uzi_text, UZI_GROUP_NAME)
    main_groups = parse_txt_content(main_text)
    extra_groups = parse_txt_content(extra_text)
    pick_extra = [g for g in extra_groups if g["group_name"] in NEED_GROUPS and len(g["items"]) > 0]

    all_groups = dong_groups + main_groups + pick_extra

    test_url_set = set()
    for g in all_groups:
        if g.get("skip_test") is True:
            continue
        for _name, url in g["items"]:
            test_url_set.add(url)
    all_tasks = list(test_url_set)

    delay_map = {}
    if all_tasks:
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            task_map = {executor.submit(check_stream, u): u for u in all_tasks}
            for future in as_completed(task_map):
                url = task_map[future]
                ok, delay, _ = future.result()
                delay_map[url] = (ok, delay)

    result = render_groups(all_groups, delay_map)
    return result


def main():
    out_dir = os.path.dirname(OUTPUT_FILE)
    if out_dir and not os.path.exists(out_dir):
        os.makedirs(out_dir, exist_ok=True)

    print("1.拉取主上游源：{}".format(SOURCE_URL))
    main_text = fetch_text_auto_decode(SOURCE_URL)
    print("2.拉取 iptasd.txt：{}".format(EXTRA_URL))
    extra_text = fetch_text_auto_decode(EXTRA_URL)
    print("3.读取本地 uzi.txt → 分组名：东方有线")
    uzi_text = read_local_file(LOCAL_TXT_PATH)

    print("开始处理：东方有线免测速，排在首位；其余分组测速过滤")
    result_text = process_all_content(main_text, extra_text, uzi_text)

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(result_text)
    print("处理完毕，输出：live.txt")


if __name__ == "__main__":
    main()
