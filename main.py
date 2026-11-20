#!/usr/bin/env python3
import requests
import time

API_URL = "https://v0.ekuai.asia/tvbox/yy88live_343815.php"
UA = "okhttp/3.12.13"
TIMEOUT = 15
OUTPUT_FILE = "test.m3u"
MAX_RETRY = 2

def fetch_tvbox_source():
    sess = requests.Session()
    headers = {
        "User-Agent": UA,
        "Accept": "*/*",
        "Referer": "https://v0.ekuai.asia/"
    }
    for attempt in range(MAX_RETRY + 1):
        try:
            print(f"📡 第 {attempt+1} 次请求")
            resp = sess.get(API_URL, headers=headers, timeout=TIMEOUT, allow_redirects=True)
            print(f"📩 最终状态码: {resp.status_code}")
            print(f"🍪 当前会话Cookie: {sess.cookies.get_dict()}")
            print(f"📄 返回内容前500字符:\n---\n{resp.text[:500]}\n---")

            if resp.status_code != 200:
                raise Exception(f"状态码异常 {resp.status_code}")
            raw = resp.text.strip()
            if not raw:
                raise Exception("返回内容为空")
            return raw
        except Exception as e:
            print(f"⚠️ 尝试失败：{e}")
            time.sleep(2)
    raise Exception("多次请求后依然无法获取数据")


def parse_content(raw_text):
    # 判断：直接是m3u播放列表
    if raw_text.startswith("#EXTM3U"):
        print("✅ 识别：直接返回M3U格式，无需JSON解析")
        return raw_text
    # 判断：标准tvbox json
    try:
        import json
        data = json.loads(raw_text)
        lines = ["#EXTM3U"]
        lives = data.get("lives", [])
        print(f"📺 JSON模式，读取频道数量：{len(lives)}")
        if len(lives) == 0:
            raise Exception("lives数组为空")
        for item in lives:
            name = item.get("name", "").strip()
            url = item.get("url", "").strip()
            if not name or not url:
                continue
            lines.append(f"#EXTINF:-1,{name}")
            lines.append(url)
        return "\n".join(lines)
    except json.JSONDecodeError:
        raise Exception("返回内容既不是标准TVBox JSON，也不是合法#EXTM3U")


if __name__ == "__main__":
    try:
        raw = fetch_tvbox_source()
        m3u_result = parse_content(raw)
        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            f.write(m3u_result)
        print(f"✅ 成功生成 {OUTPUT_FILE}")
    except Exception as e:
        print(f"❌ 采集失败: {str(e)}")
        raise
