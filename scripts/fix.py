import requests

# 你的上游源地址
UPSTREAM_URL = "http://smzb.bypbwxx.top/zhibo/lvdou/zhibo.txt"
OUTPUT_PATH = "fixed_zhibo.txt"

def fix_bad_utf8_gbk(s: str) -> str:
    try:
        raw = s.encode("gbk")
        return raw.decode("utf-8")
    except Exception:
        return s

def main():
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    resp = requests.get(UPSTREAM_URL, headers=headers, timeout=15)
    raw_bytes = resp.content
    bad_text = raw_bytes.decode("gbk", errors="replace")
    fixed_text = fix_bad_utf8_gbk(bad_text)

    with open(OUTPUT_PATH, "w", encoding="utf-8", newline="") as f:
        f.write(fixed_text)
    print(f"✅ 已生成 {OUTPUT_PATH}")

if __name__ == "__main__":
    main()
