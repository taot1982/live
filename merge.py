# -*- coding: utf-8 -*-
import re
# ========== 和仓库文件名严格对齐 ==========
ZB_FILE = "ZB.TXT"
IPTV_FILE = "iptv.txt"
IPASD_FILE = "iptasd.txt"
ZHIBO_FILE = "zhibo.txt"
SHIPTV_FILE = "shiptv.txt"  # 新增：上海频道源文件
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


def extract_oriental_and_4k(file_path):
    """
    拆分：
    orient_block：东方有线分组内容
    other_block：4K频道、轮播剧场分组内容
    """
    orient_block = []
    other_block = []
    in_orient = False
    in_other = False
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
            in_orient = False
            in_other = False
            if "东方有线" in line_strip:
                in_orient = True
                line_strip = line_strip.replace("吉林松原酒店 吉林联通", "东方有线")
                orient_block.append(line_strip)
            elif "4K频道" in line_strip or "轮播剧场" in line_strip:
                in_other = True
                line_strip = line_strip.replace("吉林松原酒店 吉林联通", "东方有线")
                other_block.append(line_strip)
            continue

        if in_orient:
            line_strip = line_strip.replace("吉林松原酒店 吉林联通", "东方有线")
            orient_block.append(line_strip)
        if in_other:
            line_strip = line_strip.replace("吉林松原酒店 吉林联通", "东方有线")
            other_block.append(line_strip)

    print(f"{file_path} 东方有线：{len(orient_block)} 行，4K+轮播：{len(other_block)} 行")
    return orient_block, other_block


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
    """zhibo.txt：只提取【央视咪咕】整个分组（含分组头）"""
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

def extract_shanghai(file_path):
    """shiptv.txt：提取【上海频道】整个分组（含分组头）"""
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
            # 分组头：上海频道,#genre#
            if line_strip == "上海频道,#genre#":
                in_group = True
                out.append(line_strip)
                continue
            # 遇到下一个分组头，停止读取
            if line_strip.endswith(",#genre#") and in_group:
                in_group = False
                continue
            if in_group:
                out.append(line_strip)
        print(f"{file_path} 提取【上海频道】分组行数：{len(out)}")
    except FileNotFoundError:
        print(f"⚠️ 文件 {file_path} 不存在，跳过上海频道分组")
    return out


def main():
    part1 = filter_all_lines(IPTV_FILE)
    orient_block, other_block = extract_oriental_and_4k(IPASD_FILE)
    part_sh = extract_shanghai(SHIPTV_FILE)
    part4 = extract_cctv_migu(ZHIBO_FILE)
    part3 = filter_zb(ZB_FILE)

    # ✅ 最终顺序：iptv → 东方有线 → 上海频道 → 4K频道+轮播剧场 → 央视咪咕 → ZB.TXT
    final = part1 + orient_block + part_sh + other_block + part4 + part3

    with open(OUTPUT, "w", encoding="utf-8") as f:
        f.write("\n".join(final))
    print(f"\n✅ 合并完成！总条数：{len(final)}")


if __name__ == "__main__":
    main()
