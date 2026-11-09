# -*- coding: utf-8 -*-
from datetime import datetime

INPUT_FILE = "iptasd.txt"
OUTPUT_FILE = "shiptv.txt"
TARGET_GROUP = "上海频道1"
NEW_GROUP = "上海频道,#genre#"
PREFIX = "http://47.99.202.156"

def main():
    lines = []
    with open(INPUT_FILE, "r", encoding="utf-8") as f:
        lines = [line.rstrip("\n") for line in f]

    in_target_group = False
    out_lines = []

    # 写入更新时间注释（放在最顶部）
    now_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    out_lines.append(f"# 更新时间: {now_time}")

    for line in lines:
        if line.endswith(",#genre#"):
            group_name = line.split(",#genre#")[0]
            if group_name == TARGET_GROUP:
                in_target_group = True
                out_lines.append(NEW_GROUP)
            else:
                in_target_group = False
            continue

        if in_target_group:
            if "," in line:
                name, url = line.split(",", 1)
                if url.startswith(PREFIX):
                    out_lines.append(line)

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        for l in out_lines:
            f.write(l + "\n")
    print(f"✅ 完成，已输出 {OUTPUT_FILE}，更新时间：{now_time}")

if __name__ == "__main__":
    main()
