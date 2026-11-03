import requests
import re
import time
from typing import List, Tuple

# ===================== 配置区 =====================
SOURCE_URL = "https://sttottv.ccwu.cc/ZB.TXT"
OUTPUT_FILE = "live.txt"
TIMEOUT = 8
USER_AGENT = "Mozilla/5.0 (Android; TV) AppleWebKit/537.36"
SKIP_CHECK = False
# ==================================================

def test_m3u8(url: str) -> bool:
    try:
        headers = {"User-Agent": USER_AGENT}
        r = requests.head(url, headers=headers, timeout=TIMEOUT, allow_redirects=True)
        if r.status_code == 200:
            return True
        r2 = requests.get(url, headers=headers, timeout=TIMEOUT, stream=True, allow_redirects=True)
        return r2.status_code == 200
    except Exception:
        return False

def fetch_remote_source() -> str:
    resp = requests.get(SOURCE_URL, timeout=20)
    resp.raise_for_status()
    text = resp.text
    if text.startswith("\ufeff"):
        text = text[1:]
    return text

def parse_lines(raw: str) -> List[Tuple[str, str]]:
    out = []
    lines = raw.splitlines()
    for line in lines:
        line = line.strip()
        if not line:
            continue
        if ",#genre#" in line:
            group_name = line.rsplit(",#genre#", 1)[0].strip()
            out.append((group_name, "#genre#"))
            continue
        parts = line.split(",", 1)
        if len(parts) != 2:
            continue
        name, link = parts
        name = name.strip()
        link = link.strip()
        out.append((name, link))
    return out

def main():
    try:
        raw_text = fetch_remote_source()
    except Exception as e:
        print(f"⚠️ 上游源拉取失败：{e}，保留旧文件")
        return

    items = parse_lines(raw_text)
    result_lines = []
    total = len([i for _, v in items if v != "#genre#"])
    alive = 0

    for name, val in items:
        if val == "#genre#":
            result_lines.append(f"{name},#genre#")
            continue
        url = val
        if SKIP_CHECK:
            result_lines.append(f"{name},{url}")
            alive += 1
            continue
        if test_m3u8(url):
            result_lines.append(f"{name},{url}")
            alive += 1
            print(f"✅ {name}")
        else:
            print(f"❌ 失效：{name}")
        time.sleep(0.15)

    seen = set()
    final = []
    for ln in result_lines:
        if ln not in seen:
            seen.add(ln)
            final.append(ln)

    with open(OUTPUT_FILE, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(final) + "\n")

    print(f"\n完成：总频道 {total}，存活 {alive}，写入 {OUTPUT_FILE}")

if __name__ == "__main__":
    main()
