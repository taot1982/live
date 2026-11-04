# -*- coding: utf-8 -*-
import requests
import re
from concurrent.futures import ThreadPoolExecutor, as_completed

# 配置
SRC_URL = "https://sttottv.ccwu.cc/ZB.TXT"
TIMEOUT = 2
MAX_WORKERS = 8
OUTPUT = "live.txt"
LOCAL_FILE = "iptv.txt"

def is_english_name(name: str) -> bool:
    return not re.search(r'[\u4e00-\u9fff]', name)

def test_url_latency(url: str) -> tuple[str, float]:
    try:
        r = requests.get(url, timeout=(1.2, TIMEOUT), stream=True)
        if r.status_code == 200:
            latency = r.elapsed.total_seconds()
        else:
            latency = 999.0
    except Exception:
        latency = 999.0
    return url, latency

def load_local_lines():
    local_out = []
    with open(LOCAL_FILE, "r", encoding="utf-8") as f:
        lines = f.readlines()
    for line in lines:
        line_strip = line.strip()
        if not line_strip or line_strip.startswith("#by") or line_strip.startswith("#节目数量"):
            continue
        line = line.replace("吉林松原酒店 吉林联通", "东方有线,#genre#")
        line = line.replace("#类型：", "")
        local_out.append(line.strip())
    return local_out

def fetch_remote():
    resp = requests.get(SRC_URL, timeout=8)
    resp.encoding = "utf-8"
    lines = resp.text.splitlines()
    channel_map = {}
    order_list = []
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#") or "," not in line:
            continue
        name, url = line.split(",", 1)
        name = name.strip()
        url = url.strip()
        if name not in channel_map:
            channel_map[name] = []
            order_list.append(name)
        channel_map[name].append(url)
    cn_remote = []
    en_remote = []
    for ch_name in order_list:
        url_list = channel_map[ch_name]
        url_lat = []
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as exe:
            task = {exe.submit(test_url_latency, u): u for u in url_list}
            for future in as_completed(task):
                u, lat = future.result()
                url_lat.append((lat, u))
        url_lat.sort(key=lambda x: x[0])
        for lat, u in url_lat:
            row = f"{ch_name},{u}"
            if is_english_name(ch_name):
                en_remote.append(row)
            else:
                cn_remote.append(row)
    return cn_remote, en_remote

def main():
    local_data = load_local_lines()
    remote_cn, remote_en = fetch_remote()
    final = local_data + remote_cn + remote_en
    with open(OUTPUT, "w", encoding="utf-8") as f:
        f.write("\n".join(final) + "\n")
    print(f"✅ 完成：本地{len(local_data)} + 远程中文{len(remote_cn)} + 远程英文{len(remote_en)} = {len(final)}")

if __name__ == "__main__":
    main()
