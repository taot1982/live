import requests
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

# ========= 配置区 =========
SOURCE_URL = "https://sttottv.ccwu.cc/ZB.TXT"
OUTPUT_FILE = "live.txt"
TIMEOUT = 8
MAX_WORKERS = 10
READ_BYTES = 2048
# ===========================

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


def process_m3u(content: str):
    lines = content.splitlines()

    # 结构：
    # meta_lines：不属于任何流的注释、头部
    # groups：[{ "meta": [], "items": [(extinf, url)] }]
    groups = []
    current_group_meta = []
    current_group_items = []
    pending_extinf = None

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("#EXTINF"):
            pending_extinf = line
            continue
        if stripped.startswith("#"):
            # 如果是分组标记，作为分组元信息，开启新分组
            if stripped.startswith("#EXTGRP") and (current_group_meta or current_group_items):
                groups.append({
                    "meta": current_group_meta,
                    "items": current_group_items
                })
                current_group_meta = []
                current_group_items = []
            current_group_meta.append(line)
            continue
        if stripped.startswith("http"):
            current_group_items.append((pending_extinf, stripped))
            pending_extinf = None
            continue
        current_group_meta.append(line)

    # 压入最后一组
    if current_group_meta or current_group_items:
        groups.append({
            "meta": current_group_meta,
            "items": current_group_items
        })

    # 全部链接并发测速
    all_tasks = []
    for g in groups:
        for _, url in g["items"]:
            all_tasks.append(url)

    delay_map = {}
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        task_map = {executor.submit(check_stream, u): u for u in all_tasks}
        for future in as_completed(task_map):
            url = task_map[future]
            ok, delay, _ = future.result()
            delay_map[url] = (ok, delay)

    final = []
    for g in groups:
        final.extend(g["meta"])
        # 本组过滤存活，并且组内按延迟升序
        alive = []
        for extinf, url in g["items"]:
            ok, d = delay_map.get(url, (False, 999))
            if ok:
                alive.append((d, extinf, url))
        alive.sort(key=lambda x: x[0])
        for d, extinf, url in alive:
            if extinf:
                final.append(extinf)
            final.append(url)

    return "\n".join(final)


def main():
    print(f"拉取上游：{SOURCE_URL}")
    try:
        resp = requests.get(SOURCE_URL, timeout=20)
        resp.raise_for_status()
        raw_text = resp.text
    except Exception as e:
        print(f"拉上游失败：{e}")
        return

    print("测速：组内按延迟排序，分组顺序保持不变")
    out_text = process_m3u(raw_text)

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(out_text)
    print(f"已保存到 {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
