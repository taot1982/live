import requests

UPSTREAM_URL = "http://smzb.bypbwxx.top/zhibo/lvdou/zhibo.txt"
OUTPUT_PATH = "fixed_zhibo.txt"


def fix_encoding(text: str) -> str:
    """尝试按常见编码修复中文乱码"""
    # 1. 先尝试按 GB18030 处理，兼容 GBK 和 GB2312
    try:
        return text.encode("gb18030").decode("utf-8")
    except Exception:
        pass

    # 2. 如果还是乱码，尝试按 GBK 修复
    try:
        return text.encode("gbk").decode("utf-8")
    except Exception:
        pass

    # 3. 尝试按 BIG5 修复
    try:
        return text.encode("big5").decode("utf-8")
    except Exception:
        pass

    # 4. 都失败则返回原文
    return text


def clean_line(line: str) -> str:
    """修复单行中文，并去掉多余空字符"""
    line = line.strip()
    if not line:
        return line

    # 如果包含英文链接，只修复前面的中文频道名部分
    if "http://" in line or "https://" in line:
        parts = line.split(",", 1)
        if len(parts) == 2:
            name, url = parts
            name = fix_encoding(name)
            return f"{name},{url}"

    return fix_encoding(line)


def main():
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    resp = requests.get(UPSTREAM_URL, headers=headers, timeout=20)
    resp.raise_for_status()

    # 关键：不再模拟 GBK 乱码，直接尝试多种编码读取
    raw = resp.content

    # 按优先级尝试解码
    text = None
    for encoding in ["utf-8", "gb18030", "gbk", "big5"]:
        try:
            text = raw.decode(encoding)
            print(f"✅ 使用编码: {encoding}")
            break
        except Exception:
            continue

    if text is None:
        text = raw.decode("utf-8", errors="replace")

    # 逐行修复
    lines = text.splitlines()
    fixed_lines = [clean_line(line) for line in lines]

    # 统一输出为 UTF-8
    with open(OUTPUT_PATH, "w", encoding="utf-8", newline="") as f:
        f.write("\n".join(fixed_lines))

    print(f"✅ 已生成 {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
