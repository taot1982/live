# -*- coding: utf-8 -*-
import re
# ========== 和仓库文件名严格对齐 ==========
ZB_FILE = "ZB.TXT"
IPTV_FILE = "iptv.txt"
IPASD_FILE = "iptasd.txt"
ZHIBO_FILE = "fixed_zhibo.txt"   # 新增源
OUTPUT = "live.txt"
# ============================================

def filter_all_lines(file_path):
    """iptv.txt：过滤，强制 CCTV5+体育赛事 紧跟在 CCTV5-体育 后面"""
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
    # 分离CCTV5+行
    cctv5_plus = None
    rest = []
    for l in out:
        if "CCTV5+体育赛事" in l:
            cctv5_plus = l
        else:
            rest.append(l)
    new_out = []
    for l in rest:
        new_out.append(l)
        # 碰到CCTV5-体育，立刻把CCTV5+塞在它后面
        if "CCTV5-体育" in l and cctv5_plus is not None:
            new_out.append(cctv5_plus)
            cctv5_plus = None
    # 兜底，如果没找到CCTV5-，放末尾
    if cctv5_plus is not None:
        new_out.append(cctv5_plus)
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
    try:
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
    except FileNotFoundError:
        print("⚠️ ZB.TXT 文件不存在，跳过ZB分组")
    except Exception as e:
        print(f"⚠️ ZB读取异常：{e}")
    return out

def extract_cctv_migu(file_path):
    """fixed_zhibo.txt：只提取【央视咪咕】整个分组（含分组头）"""
    out = []
    in_group = False
    try:
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
            # 分组头：央视咪咕,#genre#
            if line_strip == "央视咪咕,#genre#":
                in_group = True
                out.append(line_strip)
                continue
            # 遇到下一个分组头，退出该分组
            if line_strip.endswith(",#genre#") and in_group:
                in_group = False
                continue
            if in_group:
                out.append(line_strip)
        print(f"{file_path} 提取【央视咪咕】分组行数：{len(out)}")
    except FileNotFoundError:
        print(f"⚠️ 文件 {file_path} 不存在，跳过央视咪咕分组")
    return out


def main():
    # part1:iptv全部；part2:iptasd提取4K+轮播(包含东方有线分组)；part3:ZB.TXT；part4:新增央视咪咕分组
    part1 = filter_all_lines(IPTV_FILE)
    part2 = extract_4k_lunbo(IPASD_FILE)
    part4 = extract_cctv_migu(ZHIBO_FILE)   # 放在东方有线后面，即part2之后
    part3 = filter_zb(ZB_FILE)

    # 拼接顺序：iptv → 4K+轮播(含东方有线) →【央视咪咕】 → ZB.TXT
    final = part1 + part2 + part4 + part3

    with open(OUTPUT, "w", encoding="utf-8") as f:
        f.write("\n".join(final))
    print(f"\n✅ 合并完成！总条数：{len(final)}")


if __name__ == "__main__":
    main()
