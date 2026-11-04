# -*- coding: utf-8 -*-
def read_iptv():
    with open("iptv.txt", "r", encoding="utf-8") as f:
        lines = f.readlines()
    new_lines = []
    for line in lines:
        line_strip = line.strip()
        # 跳过空行、#by、#节目数量
        if not line_strip or line_strip.startswith("#by") or line_strip.startswith("#节目数量"):
            continue
        # 替换内容
        line = line.replace("吉林松原酒店 吉林联通", "东方有线,#genre#")
        line = line.replace("#类型：", "")
        # 去掉首尾空白，只保留有效内容，末尾加换行
        new_lines.append(line_strip + "\n")
    return new_lines
    
def read_iptasd():
    out = []
    current_group = ""
    with open("iptasd.txt", "r", encoding="utf-8") as f:
        lines = f.read().splitlines()

    for line in lines:
        line = line.strip()
        if not line:
            continue
        if "#genre#" in line:
            current_group = line.replace("#genre#", "").strip()
            if "4K频道" in current_group or "轮播剧场" in current_group:
                out.append(line)
            continue
        if "4K频道" in current_group or "轮播剧场" in current_group:
            out.append(line)
    return out

if __name__ == "__main__":
    part1 = read_iptv()
    part2 = read_iptasd()
    result = part1 + part2
    # 过滤掉空行，防止解析翻车
    result = [x for x in result if x.strip()]

    with open("live.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(result))

    print(f"✅完成：东方有线:{len(part1)}条，4K频道+轮播剧场:{len(part2)}条，合计{len(result)}条，输出live.txt")
