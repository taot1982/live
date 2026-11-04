# -*- coding: utf-8 -*-
def read_iptv():
    with open("iptv.txt", "r", encoding="utf-8") as f:
        text = f.read()
    # 替换文字
    text = text.replace("吉林松原酒店 吉林联通", "东方有线")
    # 如果你想要【东方有线】作为分类行，格式：东方有线,#genre#
    # 也就是把这一行单独变成分类标记
    text = text.replace("东方有线", "东方有线,#genre#")
    return text.splitlines()

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
