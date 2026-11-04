# -*- coding: utf-8 -*-
import requests
import re
from concurrent.futures import ThreadPoolExecutor, as_completed, TimeoutError

# ========== 配置 ==========
ZB_FILE = "ZB.TXT"
IPTV_FILE = "iptv.txt"
IPASD_FILE = "iptasd.txt"
OUTPUT = "live.txt"
TIMEOUT = 1.2
MAX_WORKERS = 4
POOL_TIMEOUT = 10
BAD_LATENCY = 999.0
# ==========================

def is_english_name(name: str) -> bool:
    return not re.search(r'[\u4e00-\u9fff]', name)

def need_speed_test(name: str) -> bool:
    """只对CCTV、卫视测速"""
    name_upper = name.upper()
    return "CCTV" in name_upper or "卫视" in name

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

def load_dongfang():
    # 从iptv.txt读取东方有线
    out = []
    with open(IPTV_FILE, "r", encoding="utf-8") as f:
        lines = f.readlines()
    for line in lines:
        line_strip = line.strip()
        if not line_strip:
            continue
        if line_strip.startswith("#by") or line_strip.startswith("#节目数量"):
            continue
        line_strip = line_strip.replace("吉林松原酒店 吉林联通", "东方有线,#genre#")
        line_strip = line_strip.replace("#类型：", "")
        if "东方有线" in line_strip:
            out.append(line_strip)
    return out

def load_4k_lunbo():
    # 从iptasd.txt读取4K频道、轮播剧场
    fourk = []
    lunbo = []
    with open(IPASD_FILE, "r", encoding="utf-8") as f:
        lines = f.readlines()
    for line in lines:
        line_strip = line.strip()
        if not line_strip:
            continue
        if line_strip.startswith("#by") or line_strip.startswith("#节目数量"):
            continue
        line_strip = line_strip.replace("#类型：", "")
        if "4K频道" in line_strip:
            fourk.append(line_strip)
        elif "轮播剧场" in line_strip:
            lunbo.append(line_strip)
    return fourk, lunbo

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
        if is_english_name(ch_name):
            # 英文频道，不测速，放最后
            for u in url_list:
                en_remote.append(f"{ch_name},{u}")
            continue

        if need_speed_test(ch_name):
            # CCTV / 卫视：测速，丢弃失败源，按延迟排序
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
                cn_remote.append(f"{ch_name},{u}")
        else:
            # 其他中文频道：不测速，原样保留
            for u in url_list:
                cn_remote.append(f"{ch_name},{u}")
    return cn_remote, en_remote

def main():
    dongfang_list = load_dongfang()
    fourk_list, lunbo_list = load_4k_lunbo()
    zb_cn, zb_en = load_zb()
    # 最终顺序：东方有线 → 4K频道 → 轮播剧场 → ZB中文 → ZB英文
    final = dongfang_list + fourk_list + lunbo_list + zb_cn + zb_en
    with open(OUTPUT, "w", encoding="utf-8") as f:
        f.write("\n".join(final))
    print(f"✅ 完成：东方有线{len(dongfang_list)} + 4K{len(fourk_list)} + 轮播{len(lunbo_list)} + ZB中文{len(zb_cn)} + ZB英文{len(zb_en)} = {len(final)}")

if __name__ == "__main__":
    main()
