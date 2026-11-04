# -*- coding: utf-8 -*-
import re

# ========== 和仓库文件名严格对齐 ==========
ZB_FILE = "ZB.TXT"
IPTV_FILE = "iptv.txt"
IPASD_FILE = "iptasd.txt"
OUTPUT = "live.txt"
# ============================================

def filter_all_lines(file_path):
    """iptv.txt：全部内容原样保留，分组顺序不变，过滤+文字替换，CCTV5+挪到 CCTV5-体育后面（包含url版本）"""
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
        line_strip = line_strip.replace("#类型：吉林松原酒店 吉林联通", "东方有线,#genre#")
        out.append(line_strip)

    cctv5_plus_line = None
    new_out = []
    for l in out:
        if l.startswith("CCTV5+,体育赛事,"):
            cctv5_plus_line = l
            continue
        new_out.append(l)
        if l.startswith("CCTV5-体育,") and cctv5_plus_line is not None:
            new_out.append(cctv5_plus_line)
            cctv5_plus_line = None
    if cctv5_plus_line is not None:
        new_out.append(cctv5_plus_line)

    print(f"{file_path} 保留行数：{len(new_out)}")
    return new_out

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


def filter_zb(file_path):
    """ZB.TXT：所有分组、频道顺序完全原样不动，只过滤指定行、文字替换"""
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
        # 分组标记 ,#genre# 这里保留！！ 不删掉分组栏，保证节目分组结构不变
        line_strip = line_strip.replace("吉林松原酒店 吉林联通", "东方有线")
        out.append(line_strip)
    print(f"{file_path} 保留行数：{len(out)}")
    return out


def main():
    # 整体拼接顺序：iptv.txt全部内容 → iptasd提取的4K+轮播 → ZB.TXT（分组、频道原样）
    part1 = filter_all_lines(IPTV_FILE)
    part2 = extract_4k_lunbo(IPASD_FILE)
    part3 = filter_zb(ZB_FILE)

    final = part1 + part2 + part3
    with open(OUTPUT, "w", encoding="utf-8") as f:
        f.write("\n".join(final))
    print(f"\n✅ 合并完成！总条数：{len(final)}")

if __name__ == "__main__":
    main()
