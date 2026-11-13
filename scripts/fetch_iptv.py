import os
import re
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

UPSTREAM_URL = "https://1525041261-lxsdafern4.ap-shanghai.tencentscf.com/?secret=badboytcl&url=2"
OUTPUT_PATH = "iptv.txt"

def process_channel_line(line):
    """处理频道行：返回处理后的行；若是SD频道返回None表示删除"""
    if not line.strip():
        return None
    # 分组行（#genre#）不做频道名处理，原样保留
    if "#genre#" in line:
        return line

    # 频道行格式：名称,url（按最后一个逗号拆分，避免URL里带逗号）
    if "," not in line:
        return line
    name, url = line.rsplit(",", 1)

    # 1. 删除带SD的频道（名称含 SD/sd 即整条剔除）
    if re.search(r"SD", name, re.IGNORECASE):
        return None

    # 2. 去掉名称中的 HD（大小写），去掉多余空格
    new_name = re.sub(r"HD", "", name, flags=re.IGNORECASE).strip()

    return f"{new_name},{url}"

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
        clean_lines = []
        dropped_sd = 0
        cctv1_first_removed = False
        shanghai_lines = []
        other_lines = []
        # 上海频道关键词，可自行增减
        shanghai_keywords = ["上海", "东方卫视", "上视", "纪实人文", "都市", "五星体育", "哈哈炫动"]

        for line in lines:
            line = line.rstrip("\r")
            processed = process_channel_line(line)
            if processed is None:
                dropped_sd += 1
                continue

            # 删除CCTV1第一个源
            if processed.startswith("CCTV1,") and not cctv1_first_removed:
                cctv1_first_removed = True
                continue

            # 区分上海频道 和 其他频道
            if "#genre#" not in processed:
                name_part = processed.split(",")[0]
                if any(k in name_part for k in shanghai_keywords):
                    shanghai_lines.append(processed)
                    continue
            other_lines.append(processed)

        # 合并：原有内容 + 新增【上海地方频道】分组
        final_lines = other_lines
        if shanghai_lines:
            final_lines.append("上海地方频道,#genre#")
            final_lines.extend(shanghai_lines)

        # 追加一行时间注释，每次都会变化，git识别变更，播放器忽略#注释
        from datetime import datetime
        time_mark = f"# AUTO_UPDATE_TIME: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        final_lines.append(time_mark)

        with open(OUTPUT_PATH, "w", encoding="utf-8", newline="") as f:
            f.write("\n".join(final_lines))
        print(f"✅ 成功更新 {OUTPUT_PATH}，剔除SD频道 {dropped_sd} 条，已删除CCTV1第一个源，上海频道独立分组")

    except Exception as e:
        print(f"⚠️ 拉取iptv源失败：{e}")
        print("⚠️ 保留原有iptv.txt，不覆盖，继续执行后续任务")

if __name__ == "__main__":
    main()
