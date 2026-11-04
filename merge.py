# -*- coding: utf-8 -*-
def read_iptv():
    with open("iptv.txt", "r", encoding="utf-8") as f:
        text = f.read()
    # 替换分组名称
    text = text.replace("吉林松原酒店 吉林联通", "东方有线")
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
        # 识别分组行
        if "#genre#" in line:
            current_group = line.replace("#genre#", "").strip()
            # 匹配目标分组：4k频道、轮播剧场
            if current_group in ["4k频道", "轮播剧场"]:
                out.append(line)
            continue
        # 当前分组是目标分组才收录频道
        if current_group in ["4k频道", "轮播剧场"]:
            out.append(line)
    return out

if __name__ == "__main__":
    part1 = read_iptv()
    part2 = read_iptasd()
    result = part1 + part2

    with open("live.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(result))

    print(f"✅完成：东方有线:{len(part1)}条，4k频道+轮播剧场:{len(part2)}条，合计{len(result)}条，输出live.txt")
