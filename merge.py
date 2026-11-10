# -*- coding: utf-8 -*-
"""
多源直播源合并 → live.txt
源文件：ZB.TXT / iptv.txt / iptasd.txt / live_tvbox.txt / shiptv.txt
"""
import re

# ========== 和仓库文件名严格对齐 ==========
ZB_FILE = "ZB.TXT"
IPTV_FILE = "iptv.txt"
IPASD_FILE = "iptasd.txt"
TVBOX_FILE = "live_tvbox.txt"
SHIPTV_FILE = "shiptv.txt"     # 上海频道源文件
OUTPUT = "live.txt"
# ========================================

# CCTV5+ 的频道名写法不统一：CCTV5+体育赛事 / CCTV5+ 体育赛事 / CCTV5+,体育赛事
# 统一用「行首 CCTV5+」判断，别再拿完整名称做 in 判断
CCTV5_PLUS_RE = re.compile(r"^\s*CCTV5\+")

# ZB.TXT 里要整组剔除的分组（分组头含这些关键字即丢弃，组内频道一并不要）
ZB_DROP_GROUPS = ("央视频", "咪咕央卫", "测试频道")


def read_lines(file_path):
    """统一读文件：兼容 BOM 与 GBK（Windows 存的 ZB.TXT 常见），读不到返回 None"""
    for enc in ("utf-8-sig", "utf-8", "gb18030"):
        try:
            with open(file_path, "r", encoding=enc) as f:
                return f.read().splitlines()
        except UnicodeDecodeError:
            continue
        except FileNotFoundError:
            return None
    print(f"⚠️ {file_path} 编码无法识别（试过 utf-8 / gb18030）")
    return None


def is_noise(line_strip):
    """三类噪声行：更新时间、#by、#节目数量"""
    if "更新时间" in line_strip:
        return True
    return line_strip.startswith("#by") or line_strip.startswith("#节目数量")


def filter_all_lines(file_path):
    """iptv.txt：过滤噪声行，强制 CCTV5+体育赛事 紧跟在 CCTV5-体育 后面"""
    lines = read_lines(file_path)
    if lines is None:
        print(f"⚠️ 文件 {file_path} 不存在，跳过 iptv 分组")
        return []

    out = []
    for line in lines:
        line_strip = line.strip()
        if not line_strip:
            continue
        if is_noise(line_strip):
            continue
        if line_strip.endswith(",#genre#"):
            continue
        line_strip = line_strip.replace("#类型：吉林松原酒店 吉林联通", "东方有线,#genre#")
        out.append(line_strip)

    # 分离 CCTV5+ 行
    cctv5_plus = None
    rest = []
    for l in out:
        if CCTV5_PLUS_RE.match(l):
            cctv5_plus = l
        else:
            rest.append(l)

    new_out = []
    for l in rest:
        new_out.append(l)
        # 碰到 CCTV5-体育，立刻把 CCTV5+ 塞在它后面
        if "CCTV5-体育" in l and cctv5_plus is not None:
            new_out.append(cctv5_plus)
            cctv5_plus = None
    # 兜底：没找到 CCTV5-体育 就放末尾，不丢频道
    if cctv5_plus is not None:
        new_out.append(cctv5_plus)

    print(f"{file_path} 保留行数：{len(new_out)}")
    return new_out


def extract_oriental_and_4k(file_path):
    """iptasd.txt：拆出 东方有线 / 4K频道 / 轮播剧场 三块内容（含分组头）"""
    lines = read_lines(file_path)
    if lines is None:
        print(f"⚠️ 文件 {file_path} 不存在，跳过 4K/轮播 分组")
        return [], []

    orient_block, other_block = [], []
    in_orient = in_other = False

    for line in lines:
        line_strip = line.strip()
        if not line_strip:
            continue
        if is_noise(line_strip):
            continue

        if line_strip.endswith(",#genre#"):
            in_orient = in_other = False
            if "东方有线" in line_strip:
                in_orient = True
                orient_block.append(line_strip)
            elif "4K频道" in line_strip or "轮播剧场" in line_strip:
                in_other = True
                other_block.append(line_strip)
            continue

        if in_orient:
            orient_block.append(line_strip)
        if in_other:
            other_block.append(line_strip)

    print(f"{file_path} 东方有线：{len(orient_block)} 行，4K+轮播：{len(other_block)} 行")
    return orient_block, other_block


def filter_zb(file_path):
    """ZB.TXT：分组结构原样保留，只过滤噪声行；央视频/咪咕央卫/测试频道 三个分组整组剔除"""
    lines = read_lines(file_path)
    if lines is None:
        print(f"⚠️ ZB.TXT 文件不存在，跳过 ZB 分组")
        return []

    out = []
    in_drop_group = False
    dropped = []

    for line in lines:
        line_strip = line.strip()
        if not line_strip:
            continue
        if is_noise(line_strip):
            continue

        # 分组头：判断是否属于要剔除的分组，是则整组（含分组头）跳过
        if line_strip.endswith(",#genre#"):
            in_drop_group = any(k in line_strip for k in ZB_DROP_GROUPS)
            if in_drop_group:
                dropped.append(line_strip.replace(",#genre#", ""))
                continue
            out.append(line_strip)
            continue

        if in_drop_group:
            continue

        line_strip = line_strip.replace("吉林松原酒店 吉林联通", "东方有线")
        out.append(line_strip)

    print(f"{file_path} 保留行数：{len(out)}" + (f"，剔除分组：{'、'.join(dropped)}" if dropped else ""))
    return out


def extract_cctv_migu(file_path):
    """live_tvbox.txt：只提取前 3 个整个分组（含分组头），其余丢弃"""
    lines = read_lines(file_path)
    if lines is None:
        print(f"⚠️ 文件 {file_path} 不存在，跳过前三分组")
        return []

    out = []
    in_group = False
    group_count = 0

    for line in lines:
        line_strip = line.strip()
        if not line_strip:
            continue
        if is_noise(line_strip):
            continue

        if line_strip.endswith(",#genre#"):
            if group_count < 3:
                group_count += 1
                in_group = True
                out.append(line_strip)
                continue
            break   # 第 3 个分组已收完，后面的不要

        if in_group:
            out.append(line_strip)

    print(f"{file_path} 提取前 {group_count} 个分组行数：{len(out)}")
    return out


def extract_shanghai(file_path):
    """shiptv.txt：提取【上海频道】整个分组（含分组头）"""
    lines = read_lines(file_path)
    if lines is None:
        print(f"⚠️ 文件 {file_path} 不存在，跳过上海频道分组")
        return []

    out = []
    in_group = False

    for line in lines:
        line_strip = line.strip()
        if not line_strip:
            continue
        if is_noise(line_strip):
            continue

        if line_strip == "上海频道,#genre#":
            in_group = True
            out.append(line_strip)
            continue
        if line_strip.endswith(",#genre#") and in_group:
            in_group = False
            continue
        if in_group:
            out.append(line_strip)

    print(f"{file_path} 提取【上海频道】分组行数：{len(out)}")
    return out


def main():
    part1 = filter_all_lines(IPTV_FILE)
    orient_block, other_block = extract_oriental_and_4k(IPASD_FILE)
    part_sh = extract_shanghai(SHIPTV_FILE)
    part4 = extract_cctv_migu(TVBOX_FILE)     # ← 原来误写成未定义的 ZHIBO_FILE
    part3 = filter_zb(ZB_FILE)

    # iptv.txt 里由「#类型：…」转换出的「东方有线,#genre#」与 iptasd.txt 的东方有线分组重名，
    # TVBox 会显示成两个同名分组。这里去掉后者多余的分组头，让它并进第一个东方有线分组。
    if orient_block and orient_block[0] == "东方有线,#genre#" and "东方有线,#genre#" in part1:
        orient_block = orient_block[1:]

    # ✅ 顺序：iptv → 东方有线 → 上海频道 → 4K频道+轮播剧场 → 前三个分组 → ZB.TXT
    final = part1 + orient_block + part_sh + other_block + part4 + part3

    with open(OUTPUT, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(final) + "\n")

    print(f"\n✅ 合并完成！总条数：{len(final)}")
    print(f"输出文件：{OUTPUT}")


if __name__ == "__main__":
    main()
