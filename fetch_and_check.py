import requests
import concurrent.futures
import time
import re

# ===================== 配置区（只改这里）=====================
SCF_BASE = "https://1525041261-hd5hacihfc.ap-shanghai.tencentscf.com?token=202120785&url="
PUBLIC_PROXY = "https://proxy.yumus.cn/?url="
SOURCE_URL = "http://sttottv.ccwu.cc/ZB.txt"
EXTRA_URL = "http://203.135.100.107:7681/iptasd.txt"

OUTPUT_FILE = "live.m3u"
TIMEOUT = 6
TEST_BYTES = 2048  # 只读取少量数据，减少误杀
MAX_WORKERS = 12
# ============================================================

def fetch_with_fallback(raw_url):
    """优先走自己SCF，失败自动切公共中转"""
    try:
        u1 = SCF_BASE + raw_url
        r = requests.get(u1, timeout=TIMEOUT)
        if 200 <= r.status_code < 300:
            return r.content
    except Exception:
        pass
    try:
        u2 = PUBLIC_PROXY + raw_url
        r = requests.get(u2, timeout=TIMEOUT)
        if 200 <= r.status_code < 300:
            return r.content
    except Exception:
        pass
    return None

def fetch_text(url):
    print(f"[拉取] {url}")
    raw = fetch_with_fallback(url)
    if raw is None:
        print(f"[失败] {url} 两个中转都拉不到")
        return ""
    for enc in ("utf-8", "gb18030", "gbk", "latin-1"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return ""

def test_stream(url):
    """测速，返回 (url, delay)，失败delay=None"""
    st = time.time()
    try:
        resp = requests.get(url, timeout=TIMEOUT, stream=True)
        if resp.status_code != 200:
            return (url, None)
        # 只读一小段，不完整下载
        next(resp.iter_content(TEST_BYTES))
        delay = round(time.time() - st, 3)
        return (url, delay)
    except Exception:
        return (url, None)

def parse_m3u(text):
    """解析m3u，按 #EXTGRP 分组，保留分组顺序"""
    groups = []
    current_group_name = "默认组"
    current_items = []
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if line.startswith("#EXTGRP:"):
            # 保存上一组
            if current_items:
                groups.append((current_group_name, current_items))
                current_items = []
            current_group_name = line.replace("#EXTGRP:", "").strip()
            i += 1
            continue
        if line.startswith("#EXTINF:"):
            info_line = line
            i += 1
            if i >= len(lines):
                break
            url_line = lines[i].strip()
            if url_line and not url_line.startswith("#"):
                current_items.append((info_line, url_line))
            i += 1
            continue
        i += 1
    # 收尾最后一组
    if current_items:
        groups.append((current_group_name, current_items))
    return groups

def main():
    # 合并两个源文本
    text1 = fetch_text(SOURCE_URL)
    text2 = fetch_text(EXTRA_URL)
    all_text = text1 + "\n" + text2
    if not all_text.strip():
        print("所有源全部拉取失败！")
        return

    groups = parse_m3u(all_text)
    out_lines = ["#EXTM3U"]

    for g_name, items in groups:
        print(f"\n组：{g_name}，共 {len(items)} 个频道，开始测速")
        url_list = [u for _,u in items]
        # 并发测速
        result_map = {}
        with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
            futures = {ex.submit(test_stream, u):u for u in url_list}
            for fut in concurrent.futures.as_completed(futures):
                u, d = fut.result()
                result_map[u] = d
        # 过滤有效，组内按延迟从小到大排序，组顺序不变
        valid = []
        for info, u in items:
            d = result_map.get(u)
            if d is not None:
                valid.append((info, u, d))
        valid.sort(key=lambda x: x[2])
        # 写入本组
        out_lines.append(f"#EXTGRP:{g_name}")
        for info, u, d in valid:
            out_lines.append(info)
            out_lines.append(u)
        print(f"组【{g_name}】有效：{len(valid)}")

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(out_lines))
    print(f"\n✅ 完成，输出文件：{OUTPUT_FILE}")

if __name__ == "__main__":
    main()
