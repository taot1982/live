# -*- coding: utf-8 -*-
import re

# ========== 文件名称 和仓库严格对齐 ==========
ZB_FILE = "ZB.TXT"
IPTV_FILE = "iptv.txt"
IPASD_FILE = "iptasd.txt"
OUTPUT = "live.txt"
# ============================================

def filter_all_lines(file_path):
    """iptv.txt：全部内容原样保留，分组顺序不变，过滤+文字替换"""
    out = []
    with open(file_path, "r", encoding="utf-8") as f:
        lines = f.readlines()
    for line in lines:
        line_strip = line.strip()
        if not line_strip:
            continue
        if "更新时间" in line_strip:
            continue
        if line_strip.startswith("#by") or line_strip.startswith("#节目数量"):
            continue
        if line_strip.endswith(",#genre#"):
            continue
        line_strip = line_strip.replace("吉林松原酒店 吉林联通", "东方有线,#genre#")
        out.append(line_strip)
    print(f"{file_path} 保留行数：{len(out)}")
    return out


def extract_4k_lunbo(file_path):
    """iptasd.txt：只提取【4K频道】、【轮播剧场】分组内内容，保持文件原生顺序"""
    out = []
    in_target_group = False
    with open(file_path, "r", encoding="utf-8") as f:
        lines = f.readlines()
    for line in lines:
        line_strip = line.strip()
        if not line_strip:
            continue
        if "更新时间" in line_strip:
            continue
        if line_strip.startswith("#by") or line_strip.startswith("#节目数量"):
            continue
        # 遇到分组标记
        if line_strip.endswith(",#genre#"):
            # 判断是否是目标分组
            if "4K频道" in line_strip or "轮播剧场" in line_strip:
                in_target_group = True
                out.append(line_strip)
            else:
                in_target_group = False
            continue
        # 在目标分组内，就保留该行
        if in_target_group:
            line_strip = line_strip.replace("吉林松原酒店 吉林联通", "东方有线")
            out.append(line_strip)
    print(f"{file_path} 提取4K频道+轮播剧场行数：{len(out)}")
    return out


def split_zb_cn_en(file_path):
    """ZB.TXT：中文内容在前，英文频道全部挪到ZB的末尾，各自内部顺序不变"""
    cn_part = []
    en_part = []
    with open(file_path, "r", encoding="utf-8") as f:
        lines = f.readlines()
    for line in lines:
        line_strip = line.strip()
        if not line_strip:
            continue
        if "更新时间" in line_strip:
            continue
        if line_strip.startswith("#by") or line_strip.startswith("#节目数量"):
            continue
        if line_strip.endswith(",#genre#"):
            # 分组标题判断中英文
            if re.search(r'[\u4e00-\u9fff]', line_strip):
                cn_part.append(line_strip)
            else:
                en_part.append(line_strip)
            continue
        line_strip = line_strip.replace("吉林松原酒店 吉林联通", "东方有线")
        # 判断是否包含中文
        if re.search(r'[\u4e00-\u9fff]', line_strip):
            cn_part.append(line_strip)
        else:
            en_part.append(line_strip)
    zb_out = cn_part + en_part
    print(f"{file_path} 中文{len(cn_part)}行，英文{len(en_part)}行，合并后{len(zb_out)}行")
    return zb_out


def main():
    # 整体拼接顺序：iptv.txt全部内容 → iptasd提取的4K+轮播 → ZB中文在前、英文在后
    part1 = filter_all_lines(IPTV_FILE)
    part2 = extract_4k_lunbo(IPASD_FILE)
    part3 = split_zb_cn_en(ZB_FILE)

    final = part1 + part2 + part3
    with open(OUTPUT, "w", encoding="utf-8") as f:
        f.write("\n".join(final))
    print(f"\n✅ 合并完成！总条数：{len(final)}")

if __name__ == "__main__":
    main()
