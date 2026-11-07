import os
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

UPSTREAM_URL = "http://a.u9c.cn/5P1He0"
OUTPUT_PATH = "iptv.txt"

def main():
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    session = requests.Session()
    retry_strategy = Retry(
        total=3,
        backoff_factor=1,
        status_forcelist=[500,502,503,504,429]
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("http://", adapter)
    session.mount("https://", adapter)

    try:
        resp = session.get(UPSTREAM_URL, headers=headers, timeout=(8,15))
        resp.raise_for_status()
        raw = resp.content

        text = None
        # 依次尝试编码解析原始字节
        for enc in ["utf-8", "gb18030", "gbk", "big5"]:
            try:
                text = raw.decode(enc)
                print(f"✅ iptv源解析编码: {enc}")
                break
            except Exception:
                continue
        if text is None:
            text = raw.decode("utf-8", errors="replace")

        lines = text.splitlines()
        clean_lines = [line.rstrip("\r") for line in lines]

        # 追加一行时间注释，每次都会变化，git识别变更，播放器忽略#注释
        from datetime import datetime
        time_mark = f"# AUTO_UPDATE_TIME: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        clean_lines.append(time_mark)

        with open(OUTPUT_PATH, "w", encoding="utf-8", newline="") as f:
            f.write("\n".join(clean_lines))
        print(f"✅ 成功更新 {OUTPUT_PATH}，已写入更新标记")

    except Exception as e:
        print(f"⚠️ 拉取iptv源失败：{e}")
        print("⚠️ 保留原有iptv.txt，不覆盖，继续执行后续任务")

if __name__ == "__main__":
    main()
