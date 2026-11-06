import requests

# ===================== 配置区 =====================
SOURCE_URL = "https://1525041261-gl7b7quwot.ap-hongkong.tencentscf.com?secret=badboytcl"
OUTPUT_FILE = "ZB.TXT"
# ==================================================

def main():
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    try:
        resp = requests.get(SOURCE_URL, headers=headers, timeout=30)
        resp.raise_for_status()
        raw_text = resp.text
        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            f.write(raw_text)
        print(f"✅ {OUTPUT_FILE} 更新完成")
    except Exception as e:
        print(f"❌ 获取ZB.TXT失败：{e}")

if __name__ == "__main__":
    main()
