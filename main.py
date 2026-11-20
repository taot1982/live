#!/usr/bin/env python3
import requests
import time

API_URL = "https://v0.ekuai.asia/tvbox/yy88live_343815.php"
UA = "okhttp/3.12.13"
TIMEOUT = 15
OUTPUT_FILE = "test.m3u"
MAX_RETRY = 2

def fetch_tvbox_source():
    # 使用Session维持Cookie会话，重点！
    sess = requests.Session()
    headers = {
        "User-Agent": UA,
        "Accept": "application/json, text/plain, */*",
        "Referer": "https://v0.ekuai.asia/"
    }
    for attempt in range(MAX_RETRY + 1):
        try:
            print(f"📡 第 {attempt+1} 次请求")
            # allow_redirects=True 跟随302跳转，session自动携带cookie
            resp = sess.get(API_URL, headers=headers, timeout=TIMEOUT, allow_redirects=True)
            print(f"📩 最终状态码: {resp.status_code}")
            print(f"🍪 当前会话Cookie: {sess.cookies.get_dict()}")
            print(f"📄 返回内容前500字符:\n---\n{resp.text[:500]}\n---")
            if resp.status_code == 200 and len(resp.text.strip()) > 0:
                return resp.json()
        except Exception as e:
            print(f"⚠️ 尝试失败：{e}")
            time.sleep(2)
    raise Exception("多次请求后依然无法获取有效JSON数据")

def json2m3u(data):
    lines = ["#EXTM3U"]
    lives = data.get("lives", [])
    print(f"📺 读取到频道数量：{len(lives)}")
    if len(lives) == 0:
        raise Exception("返回json内lives数组为空，没有频道")
    for item in lives:
        name = item.get("name", "").strip()
        url = item.get("url", "").strip()
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
        print(f"❌ 采集失败: {str(e)}")
        # 失败不覆盖旧文件，直接退出报错
        raise
