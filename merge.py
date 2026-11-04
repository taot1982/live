# -*- coding: utf-8 -*-
import re

# ========== 配置 ==========
ZB_FILE = "ZB.TXT"
IPTV_FILE = "iptv.txt"
IPASD_FILE = "iptasd.txt"
OUTPUT = "live.txt"
# ==========================

def is_english_name(name: str) -> bool:
    return not re.search(r'[\u4e00-\u9fff]', name)

def load_dongfang():
    """从iptv.txt读取东方有线，保留原文顺序"""
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
    """从iptasd.txt读取，保留文件原有顺序，过滤更新时间行"""
    fourk_lunbo_out = []
    with open(IPASD_FILE, "r", encoding="utf-8") as f:
        lines = f.readlines()
    for line in lines:
        line_strip = line.strip()
        if not line_strip:
            continue
        # 去除更新时间行
        if "更新时间" in line_strip:
            continue
        if line_strip.startswith("#by") or line_strip.startswith("#节目数量"):
            continue
        line_strip = line_strip.replace("#类型：", "")
        if "4K频道" in line_strip or "轮播剧场" in line_strip:
            fourk_lunbo_out.append(line_strip)
    return fourk_lunbo_out

def load_zb():
    """读取ZB.TXT，保留原有顺序；过滤更新时间，英文频道挪到末尾"""
    cn_remote = []
    en_remote = []
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
    return cn_remote, en_remote

def main():
    dongfang_list = load_dongfang()
    fourk_lunbo_list = load_4k_lunbo()
    zb_cn, zb_en = load_zb()
    # 整体顺序：东方有线 → iptasd里4K+轮播（原序） → ZB中文（原序） → ZB英文
    final = dongfang_list + fourk_lunbo_list + zb_cn + zb_en
    with open(OUTPUT, "w", encoding="utf-8") as f:
        f.write("\n".join(final))
    print(f"✅ 完成：东方有线{len(dongfang_list)} + 4K&轮播{len(fourk_lunbo_list)} + ZB中文{len(zb_cn)} + ZB英文{len(zb_en)} = {len(final)}")

if __name__ == "__main__":
    main()
