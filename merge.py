# -*- coding: utf-8 -*-
import requests
import re
from concurrent.futures import ThreadPoolExecutor, as_completed, TimeoutError

# ========== 配置 ==========
ZB_FILE = "ZB.TXT"
LOCAL_FILE = "iptv.txt"
OUTPUT = "live.txt"
TIMEOUT = 1.2
MAX_WORKERS = 4
POOL_TIMEOUT = 10
BAD_LATENCY = 999.0
# ==========================

def is_english_name(name: str) -> bool:
    return not re.search(r'[\u4e00-\u9fff]', name)

def test_url_latency(url: str) -> tuple[str, float]:
    try:
        r = requests.get(url, timeout=(0.8, TIMEOUT))
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
        if not line_strip:
            continue
        if line_strip.startswith("#by") or line_strip.startswith("#节目数量"):
            continue
        line_strip = line_strip.replace("吉林松原酒店 吉林联通", "东方有线,#genre#")
        line_strip = line_strip.replace("#类型：", "")
        local_out.append(line_strip)
    return local_out

def load_zb():
    channel_map = {}
    order_list = []
    with open(ZB_FILE, "r", encoding="utf-8") as f:
        lines = f.readlines()
    for line in lines:
        line = line.strip()
        if not line:
            continue
        if "更新时间" in line:
            continue
        if line.startswith("#") or "," not in line:
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
            try:
                for future in as_completed(task, timeout=POOL_TIMEOUT):
                    u, lat = future.result()
                    url_lat.append((lat, u))
            except TimeoutError:
                pass
        url_lat.sort(key=lambda x: x[0])
        for lat, u in url_lat:
            if lat >= BAD_LATENCY:
                continue
            row = f"{ch_name},{u}"
            if is_english_name(ch_name):
                en_remote.append(row)
            else:
                cn_remote.append(row)
    return cn_remote, en_remote

def main():
    local_data = load_local_lines()
    zb_cn, zb_en = load_zb()
    final = local_data + zb_cn + zb_en
    with open(OUTPUT, "w", encoding="utf-8") as f:
        f.write("\n".join(final))
    print(f"✅ 完成：本地{len(local_data)} + ZB中文{len(zb_cn)} + ZB英文{len(zb_en)} = {len(final)}")

if __name__ == "__main__":
    main()
