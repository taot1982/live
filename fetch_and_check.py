import requests
from concurrent.futures import ThreadPoolExecutor, as_completed

# ========= 配置区 =========
SOURCE_URL = "https://sttottv.ccwu.cc/ZB.TXT"
OUTPUT_FILE = "live.txt"
TIMEOUT = 8
MAX_WORKERS = 10
READ_BYTES = 2048  # 只读取开头一小段，不完整下载
# ===========================

def is_live_stream(url: str) -> bool:
    if not (url.startswith("http://") or url.startswith("https://")):
        return True
    try:
        headers = {
            "User-Agent": "VLC/3.0.18 LibVLC/3.0.18"
        }
        with requests.get(
            url,
            timeout=TIMEOUT,
            headers=headers,
            stream=True,
            allow_redirects=True
        ) as r:
            if not (200 <= r.status_code < 400):
                return False
            # 读取一小段就退出
            next(r.iter_content(chunk_size=READ_BYTES), None)
            return True
    except Exception:
        return False


def process_m3u(content: str):
    lines = content.splitlines()
    check_items = []
    output_header = []
    pending_extinf = None

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("#EXTINF"):
            pending_extinf = line
            continue
        if stripped.startswith("#"):
            output_header.append(line)
            continue
        if stripped.startswith("http"):
            check_items.append((pending_extinf, stripped))
            pending_extinf = None
            continue
        output_header.append(line)

    keep_idx = set()
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        task_map = {
            executor.submit(is_live_stream, url): i
            for i, (_, url) in enumerate(check_items)
        }
        for future in as_completed(task_map):
            idx = task_map[future]
            if future.result():
                keep_idx.add(idx)

    final = output_header.copy()
    for i, (extinf, url) in enumerate(check_items):
        if i in keep_idx:
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

    print("开始测速，GET 片段探测（降低误杀）")
    out_text = process_m3u(raw_text)

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(out_text)
    print(f"已保存到 {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
