# -*- coding: utf-8 -*-
import re

INPUT_FILE = "iptasd.txt"
OUTPUT_FILE = "shiptv.txt"
TARGET_GROUP = "上海频道1"
NEW_GROUP = "上海频道"
PREFIX = "http://47.99.202.156"

def main():
    lines = []
    with open(INPUT_FILE, "r", encoding="utf-8") as f:
        lines = [line.rstrip("\n") for line in f]

    in_target_group = False
    out_lines = []

    for line in lines:
        # 分组标记：xxx,#genre#
        if line.endswith(",#genre#"):
            group_name = line.split(",#genre#")[0]
            if group_name == TARGET_GROUP:
                in_target_group = True
                out_lines.append(f"{NEW_GROUP},#genre#")
            else:
                in_target_group = False
            continue

        if in_target_group:
            # 频道行格式：频道名,url
            if "," in line:
                name, url = line.split(",", 1)
                if url.startswith(PREFIX):
                    out_lines.append(line)

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        for l in out_lines:
            f.write(l + "\n")
    print(f"✅ 完成，已输出 {OUTPUT_FILE}")

if __name__ == "__main__":
    main()
