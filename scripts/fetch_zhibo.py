# 暂停脚本，启用时注释下面这行
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import re

UPSTREAM_URL = "http://smzb.bypbwxx.top/zhibo/lvdou/zhibo.txt"
OUTPUT_PATH = "zhibo.txt"

def clean_text(text: str) -> str:
    # 和你fix.py保持一致的清洗逻辑
    text = text.replace("\ufeff", "")
    text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', "", text)
    return text

def main():
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    # 重试策略
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

        # 依次尝试编码
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

    except Exception as e:
        print(f"❌ 下载失败：{e}")
        text = ""

    text = clean_text(text)
    lines = text.splitlines()
    out_lines = []
    group_cnt = 0

    for line in lines:
        line = line.strip()
        if not line:
            out_lines.append("")
            continue

        if ",#genre#" in line:
            group_cnt += 1
            if group_cnt == 1:
                out_lines.append("央视咪咕,#genre#")
            else:
                out_lines.append(line)
        else:
            out_lines.append(line)

    result_content = "\n".join(out_lines)
    with open(OUTPUT_PATH, "w", encoding="utf-8", newline="") as f:
        f.write(result_content)

    print(f"✅ 处理完毕，输出文件：{OUTPUT_PATH}，识别分组总数：{group_cnt}")

if __name__ == "__main__":
    main()
