import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

UPSTREAM_URL = "http://203.135.100.107:7681/iptasd.txt"
OUTPUT_PATH = "iptasd.txt"

def main():
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    # 配置重试策略
    session = requests.Session()
    retry_strategy = Retry(
        total=3,
        backoff_factor=1,
        status_forcelist=[500, 502, 503, 504]
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("http://", adapter)

    try:
        resp = session.get(UPSTREAM_URL, headers=headers, timeout=15)
        resp.raise_for_status()
        raw = resp.content

        text = None
        for enc in ["utf-8", "gb18030", "gbk", "big5"]:
            try:
                text = raw.decode(enc)
                print(f"✅ 解析源使用编码: {enc}")
                break
            except Exception:
                continue
        if text is None:
            text = raw.decode("utf-8", errors="replace")

        lines = text.splitlines()
        clean_lines = [line.rstrip("\r") for line in lines]

        with open(OUTPUT_PATH, "w", encoding="utf-8", newline="") as f:
            f.write("\n".join(clean_lines))
        print(f"✅ 成功更新 {OUTPUT_PATH}")

    except Exception as e:
        print(f"⚠️ 拉取 iptasd.txt 失败：{e}")
        print("⚠️  保留原有文件，不覆盖，任务继续往下执行")

if __name__ == "__main__":
    main()
