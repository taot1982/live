# -*- coding: utf-8 -*-
import requests
import re
from concurrent.futures import ThreadPoolExecutor, as_completed

# ========== 配置 ==========
ZB_FILE = "ZB.TXT"
LOCAL_FILE = "iptv.txt"
OUTPUT = "live.txt"
TIMEOUT = 2
MAX_WORKERS = 8
BAD_LATENCY = 999.0
# ==========================

def is_english_name(name: str) -> bool:
    """判断是否纯英文频道名"""
    return not re.search(r'[\u4e00-\u9fff]', name)

def test_url_latency(url: str) -> tuple[str, float]:
    """测速，返回url和延迟，失败=999"""
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
    """读取iptv.txt + 原有过滤替换"""
    local_out = []
    with open(LOCAL_FILE, "r", encoding="utf-8") as f:
        lines = f.readlines()
    for line in lines:
        line_strip = line.strip()
        if not line_strip:
            continue
        if line_strip.startswith("#by") or line_strip.startswith("#节目数量"):
            continue
        # 原有替换规则
        line_strip = line_strip.replace("吉林松原酒店 吉林联通", "东方有线,#genre#")
        line_strip = line_strip.replace("#类型：", "")
        local_out.append(line_strip)
    return local_out

def load_zb():
    """读取本地仓库ZB.TXT，过滤更新时间行，同频道多源测速排序，丢弃测速失败源，保留原始频道顺序"""
    channel_map = {}
    order_list = []
    with open(ZB_FILE, "r", encoding="utf-8") as f:
        lines = f.readlines()
    for line in lines:
        line = line.strip()
        # 跳过空行、普通注释、更新时间行
        if not line:
            continue
        # 匹配更新时间：包含“更新时间”的注释行直接删掉
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
            for future in as_completed(task):
                u, lat = future.result()
                url_lat.append((lat, u))
        # 按延迟从小到大排序
        url_lat.sort(key=lambda x: x[0])
        # 只保留测速成功的源，丢弃latency=999的失败源
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
    # 写入，一行一条，无空行
    with open(OUTPUT, "w", encoding="utf-8") as f:
        f.write("\n".join(final))
    print(f"✅ 完成：本地{len(local_data)} + ZB中文{len(zb_cn)} + ZB英文{len(zb_en)} = {len(final)}")

if __name__ == "__main__":
    main()
