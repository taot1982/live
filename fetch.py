import requests
import time

TARGET_URL = "https://iptv.ekuai.asia/fengyun.php?id=103&s=11"
OUTPUT_FILE = "test.m3u"

def main():
    sess = requests.Session()
    # 模拟APP/云影空蒙的UA，这个源会校验UA
    headers = {
        "User-Agent": "oklive/1.0 (Linux; Android; TVBox)",
        "Accept": "*/*",
        "Referer": "https://iptv.ekuai.asia/"
    }
    try:
        print(f"开始请求：{TARGET_URL}")
        resp = sess.get(TARGET_URL, headers=headers, timeout=20, allow_redirects=True)
        print(f"状态码: {resp.status_code}")
        print(f"最终跳转地址: {resp.url}")

        content = resp.text.strip()
        # 简单判断是否拿到m3u8源
        if "#EXTM3U" in content or ".m3u8" in content:
            with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
                f.write(content)
            print(f"✅ 成功写入 {OUTPUT_FILE}")
        else:
            print("❌ 返回内容不是有效m3u，原始返回：")
            print(content)
    except Exception as e:
        print(f"请求异常：{e}")
        time.sleep(3)

if __name__ == "__main__":
    main()
