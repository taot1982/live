#!/usr/bin/env python3
# main.py
import requests
import json

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
    print(f"📡 请求地址: {API_URL}")
    resp = requests.get(API_URL, headers=headers, timeout=TIMEOUT)
    print(f"📩 状态码: {resp.status_code}")
    print(f"📄 返回原文:\n{resp.text}")
    data = resp.json()
    return data

def json2m3u(data):
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
    return "\n".join(lines)

if __name__ == "__main__":
    try:
        source_data = fetch_tvbox_source()
        m3u_text = json2m3u(source_data)
        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            f.write(m3u_text)
        print(f"✅ 成功生成 {OUTPUT_FILE}")
    except Exception as e:
        print(f"❌ 失败: {str(e)}")
        raise
