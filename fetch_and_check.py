import requests

SOURCE_URL = "https://sttottv.ccwu.cc/ZB.TXT"
OUTPUT_FILE = "live.txt"

def main():
    try:
        resp = requests.get(SOURCE_URL, timeout=20)
        resp.raise_for_status()
        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            f.write(resp.text)
        print("拉取成功，写入 live.txt")
    except Exception as e:
        print(f"失败：{e}")

if __name__ == "__main__":
    main()
