#!/usr/bin/env python3
import requests

API_URL = "https://v0.ekuai.asia/tvbox/yy88live_343815.php"
UA = "okhttp/3.12.13"
TIMEOUT = 15
OUTPUT_FILE = "test.m3u"

def fetch_tvbox_source():
    headers = {
        "User-Agent": UA,
        "Accept": "application/json, text/plain, */*",
        "Referer": "https://v0.ekuai.asia/"
    }
    print(f"📡 GET 请求地址: {API_URL}")
    resp = requests.get(API_URL, headers=headers, timeout=TIMEOUT)
    print(f"📩 状态码: {resp.status_code}")
    print(f"📄 返回原文:\n---\n{resp.text}\n---")

    if resp.status_code != 200:
        print("⚠️ GET失败，尝试POST")
        resp = requests.post(API_URL, headers=headers, timeout=TIMEOUT)
        print(f"📩 POST状态码: {resp.status_code}")
        print(f"📄 POST返回原文:\n---\n{resp.text}\n---")
    return resp.text

def parse_and_save(raw):
    try:
        data = requests.json.loads(raw)
    except Exception as e:
        print(f"❌ JSON解析失败，原始内容不是json，无法生成m3u: {e}")
        return False

    lines = ["#EXTM3U"]
    lives = data.get("lives", [])
    print(f"📺 频道数量：{len(lives)}")
    for item in lives:
        name = item.get("name", "")
        url = item.get("url", "")
        if not name or not url:
            continue
        lines.append(f"#EXTINF:-1,{name}")
        lines.append(url)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"✅ 成功生成 {OUTPUT_FILE}")
    return True

if __name__ == "__main__":
    content = fetch_tvbox_source()
    parse_and_save(content)
