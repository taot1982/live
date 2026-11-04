import requests
import concurrent.futures
import time
import re

# ===================== 配置区（这里已经填好你的中转链接） =====================
source_list = [
    "http://1525041261-hd5hacihfc.ap-shanghai.tencentscf.com?key=202120785&url=https://sttottv.ccwu.cc/ZB.TXT",
    "http://1525041261-hd5hacihfc.ap-shanghai.tencentscf.com?key=202120785&url=http://203.135.100.107:7681/iptasd.txt"
]
OUTPUT_FILE = "live.txt"
TEST_TIMEOUT = 15          # 和云函数超时保持一致
CONCURRENCY = 8            # 并发测速数量
READ_BYTES = 2048          # 只读取少量数据，减少误杀
# =============================================================================

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

def test_stream(url):
    """测速，返回 (url, delay, ok)，低误杀模式"""
    try:
        start = time.time()
        r = requests.get(url, headers=headers, timeout=TEST_TIMEOUT, stream=True)
        r.raise_for_status()
        # 只读取一小段，不完整拉流
        next(r.iter_content(chunk_size=READ_BYTES))
        delay = time.time() - start
        return (url, delay, True)
    except Exception:
        return (url, 999.9, False)

def parse_m3u(raw_text):
    """解析m3u，按 #EXTGRP 分组，保留分组顺序"""
    group_list = []
    current_group = None
    item_buffer = []
    lines = raw_text.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if not line:
            i += 1
            continue
        if line.startswith("#EXTGRP:"):
            # 新分组
            if current_group is not None and item_buffer:
                group_list.append({"name": current_group, "items": item_buffer})
            current_group = line.replace("#EXTGRP:", "").strip()
            item_buffer = []
            i += 1
            continue
        if line.startswith("#EXTINF:"):
            # 一个频道块：#EXTINF + url
            if i+1 >= len(lines):
                i += 1
                continue
            url_line = lines[i+1].strip()
            if url_line and not url_line.startswith("#"):
                item_buffer.append({"inf": line, "url": url_line})
            i += 2
            continue
        i += 1
    # 收尾最后一组
    if current_group is not None and item_buffer:
        group_list.append({"name": current_group, "items": item_buffer})
    return group_list

def main():
    all_raw = ""
    # 拉取所有上游源
    for src in source_list:
        try:
            resp = requests.get(src, headers=headers, timeout=TEST_TIMEOUT)
            resp.raise_for_status()
            all_raw += resp.text + "\n"
        except Exception as e:
            print(f"拉取上游失败 {src} : {e}")

    groups = parse_m3u(all_raw)
    if not groups:
        print("警告：没有解析到任何频道分组！检查云函数返回内容")
        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            f.write("#EXTM3U\n")
        return

    # 收集所有url，批量测速
    all_urls = []
    url_map = {}
    for g in groups:
        for it in g["items"]:
            u = it["url"]
            all_urls.append(u)
            url_map[u] = it

    url_result = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=CONCURRENCY) as executor:
        future_map = {executor.submit(test_stream, u): u for u in all_urls}
        for fut in concurrent.futures.as_completed(future_map):
            u, delay, ok = fut.result()
            url_result[u] = {"delay": delay, "ok": ok}

    # 输出m3u，分组顺序不变，组内按延迟升序排序
    out_lines = ["#EXTM3U"]
    for g in groups:
        out_lines.append(f"#EXTGRP:{g['name']}")
        # 过滤有效，组内按延迟排序
        valid_items = [it for it in g["items"] if url_result[it["url"]]["ok"]]
        valid_items.sort(key=lambda x: url_result[x["url"]]["delay"])
        for it in valid_items:
            out_lines.append(it["inf"])
            out_lines.append(it["url"])

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(out_lines))
    print(f"完成！输出 {OUTPUT_FILE}")

if __name__ == "__main__":
    main()
