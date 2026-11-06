import requests

UPSTREAM_URL = "http://203.135.100.107:7681/iptasd.txt"
OUTPUT_PATH = "iptasd.txt"

def main():
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    resp = requests.get(UPSTREAM_URL, headers=headers, timeout=20)
    resp.raise_for_status()
    raw = resp.content

    # 依次尝试编码解析原始字节
    text = None
    for enc in ["utf-8", "gb18030", "gbk", "big5"]:
        try:
            text = raw.decode(enc)
            print(f"✅ 解析源使用编码: {enc}")
            break
        except Exception:
            continue
    if text is None:
        text = raw.decode("utf-8", errors="replace")

    lines = text.splitlines()
    # 直接原样处理，去除每行末尾多余空白
    clean_lines = [line.rstrip("\r") for line in lines]

    # 输出强制保存为 UTF‑8
    with open(OUTPUT_PATH, "w", encoding="utf-8", newline="") as f:
        f.write("\n".join(clean_lines))
    print(f"✅ 已生成 {OUTPUT_PATH}")

if __name__ == "__main__":
    main()
