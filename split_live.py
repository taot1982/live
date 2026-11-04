import json

# ==========配置区==========
local_file = "iptasd.txt"
target_groups = {"4K频道","轮播剧场"}
out_file = "config.json"
# =========================

def load_txt(filepath):
    with open(filepath, "r", encoding="gbk") as f:
        return f.read()

def parse_content(text):
    live1 = []
    live2 = []
    current_group = "default"
    lines = text.splitlines()
    for line in lines:
        line = line.strip()
        if not line:
            continue
        if "#genre#" in line:
            current_group = line.replace("#genre#","").strip()
            continue
        if "," not in line:
            continue
        name, url = line.rsplit(",", 1)
        item = {
            "name": name.strip(),
            "url": url.strip(),
            "group": current_group
        }
        if current_group in target_groups:
            live2.append(item)
        else:
            live1.append(item)
    return live1, live2

if __name__ == "__main__":
    txt = load_txt(local_file)
    live1_list, live2_list = parse_content(txt)
    all_live = live1_list + live2_list
    output = {
        "live": all_live
    }
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print(f"✅处理完成：live1:{len(live1_list)}条，live2(4K+轮播剧场):{len(live2_list)}条，合计{len(all_live)}")
