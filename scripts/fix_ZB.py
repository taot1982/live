import requests
import re

# ===================== 配置区 =====================
# 替换成你的香港SCF中转链接（tag=zb）
SOURCE_URL = "https://sttottv.ccwu.cc/ZB.TXT"
OUTPUT_FILE = "ZB.TXT"
# ==================================================

def main():
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    resp = requests.get(SOURCE_URL, headers=headers, timeout=20)
    resp.raise_for_status()
    raw_text = resp.text

    # -------- 这里和 fix_iptasd.py 保持一致清洗流程 --------
    # 如果你后面拿到原版 fix_iptasd.py，把里面的过滤、去重、排序、正则替换
    # 代码直接粘贴到下面这块即可
    clean_text = raw_text

    # 保存成 ZB.TXT
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(clean_text)
    print(f"✅ {OUTPUT_FILE} 更新完成")

if __name__ == "__main__":
    main()
