# -*- coding: utf-8 -*-
import os
import re

# ========== 配置（和仓库文件名严格对齐！） ==========
ZB_FILE = "ZB.TXT"
IPTV_FILE = "iptv.txt"
IPASD_FILE = "iptasd.txt"
OUTPUT = "live.txt"
# ==========================

def is_english_name(name: str) -> bool:
    return not re.search(r'[\u4e00-\u9fff]', name)

def load_dongfang():
    out = []
    print(f"读取 {IPTV_FILE}")
    with open(IPTV_FILE, "r", encoding="utf-8") as f:
        lines = f.readlines()
    for line in lines:
        line_strip = line.strip()
        if not line_strip:
            continue
        if line_strip.startswith("#by") or line_strip.startswith("#节目数量"):
            continue
        line_strip = line_strip.replace("吉林松原酒店 吉林联通", "东方有线")
        line_strip = line_strip.replace("#类型：", "")
        if "东方有线" in line_strip:
            out.append(line_strip)
    print(f"iptv 东方有线读取数量：{len(out)}")
    return out

def load_4k_lunbo():
    fourk_lunbo_out = []
    print(f"读取 {IPASD_FILE}")
    with open(IPASD_FILE, "r", encoding="utf-8") as f:
        lines = f.readlines()
    for line in lines:
        line_strip = line.strip()
        if not line_strip:
            continue
        if "更新时间" in line_strip:
            continue
        if line_strip.startswith("#by") or line_strip.startswith("#节目数量"):
            continue
        line_strip = line_strip.replace("#类型：", "")
        if "4K频道" in line_strip or "轮播剧场" in line_strip:
            fourk_lunbo_out.append(line_strip)
    print(f"iptasd 4K&轮播读取数量：{len(fourk_lunbo_out)}")
    return fourk_lunbo_out

def load_zb():
    cn_remote = []
    en_remote = []
    print(f"读取 {ZB_FILE}")
    with open(ZB_FILE, "r", encoding="utf-8") as f:
        lines = f.readlines()
    for line in lines:
        line = line.strip()
        if not line:
            continue
        if "更新时间" in line:
            continue
        if line.endswith(",#genre#"):
            continue
        if line.startswith("#") or "," not in line:
            continue
        name, url = line.split(",", 1)
        name = name.strip()
        url = url.strip()
        if is_english_name(name):
            en_remote.append(f"{name},{url}")
        else:
            cn_remote.append(f"{name},{url}")
    print(f"ZB中文：{len(cn_remote)}，英文：{len(en_remote)}")
    return cn_remote, en_remote

def main():
    dongfang_list = load_dongfang()
    fourk_lunbo_list = load_4k_lunbo()
    zb_cn, zb_en = load_zb()
    final = dongfang_list + fourk_lunbo_list + zb_cn + zb_en
    with open(OUTPUT, "w", encoding="utf-8") as f:
        f.write("\n".join(final))
    print(f"✅ 总条目：{len(final)}，写入live.txt")

if __name__ == "__main__":
    main()
