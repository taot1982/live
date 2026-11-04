# -*- coding: utf-8 -*-
def read_iptv():
    with open("iptv.txt", "r", encoding="utf-8") as f:
        text = f.read()
    text = text.replace("吉林松原酒店 吉林联通", "东方有线")
    return text.splitlines()

def read_iptasd():
    lines_out = []
    # 改用 gb18030，errors="replace" 遇到异常字符不崩溃
    with open("iptasd.txt", "r", encoding="gb18030", errors="replace") as f:
        lines = f.read().splitlines()
    current_group = ""
    for line in lines:
        line = line.strip()
        if not line:
            continue
        if "#genre#" in line:
            current_group = line.replace("#genre#", "").strip()
            continue
        if current_group in ["4K频道", "轮播剧场"]:
            lines_out.append(line)
    return lines_out

if __name__ == "__main__":
    iptv_lines = read_iptv()
    iptasd_lines = read_iptasd()

    all_lines = []
    all_lines.extend(iptv_lines)
    all_lines.extend(iptasd_lines)

    with open("live.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(all_lines))

    print(f"✅完成：iptv:{len(iptv_lines)}条，4K+轮播:{len(iptasd_lines)}条，合计{len(all_lines)}条，输出live.txt")
