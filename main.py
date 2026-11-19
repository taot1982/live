#!/usr/bin/env python3
# main.py
# 目标源：https://v0.ekuai.asia/tvbox/yy88live_343815.php
# 模拟TVBox(影视仓)请求，解析并输出 test.m3u
import requests
import json

# ========== 配置 ==========
API_URL = "https://v0.ekuai.asia/tvbox/yy88live_343815.php"
UA = "okhttp/5.0.0-alpha.14"  # TVBox影视仓固定UA
TIMEOUT = 15
OUTPUT_FILE = "test.m3u"
# ==========================

def fetch_tvbox_source():
    headers = {
        "User-Agent": UA,
        "Accept": "application/json, text/plain, */*"
    }
    resp = requests.get(API_URL, headers=headers, timeout=TIMEOUT)
    resp.raise_for_status()
    data = resp.json()
    return data

def json2m3u(data):
    lines = ["#EXTM3U"]
    lives = data.get("lives", [])
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
        print(f"✅ 成功生成 {OUTPUT_FILE}，频道数量：{len(source_data.get('lives', []))}")
    except Exception as e:
        print(f"❌ 获取源失败: {str(e)}")
        raise
