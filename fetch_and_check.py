import requests
import json

# ==========配置区==========
src_url = "http://203.135.100.107:7681/iptasd.txt"
target_groups = {"4K频道","轮播剧场"}
out_file = "config.json"
# =========================

def fetch_txt(url):
    resp = requests.get(url,timeout=15)
    # ✅重点：这个源是GBK编码！
    resp.encoding = "gbk"
    return resp.text

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
        name,url = line.rsplit(",",1)
        item = {
            "name":name.strip(),
            "url":url.strip(),
            "group":current_group
        }
        if current_group in target_groups:
            live2.append(item)
        else:
            live1.append(item)
    return live1,live2

if __name__ == "__main__":
    try:
        txt = fetch_txt(src_url)
        live1_list,live2_list = parse_content(txt)
        all_live = live1_list + live2_list
        output = {
            "live": all_live
        }
        with open(out_file,"w",encoding="utf-8") as f:
            json.dump(output,f,ensure_ascii=False,indent=2)
        print(f"✅处理完成：live1:{len(live1_list)}条，live2(4K+轮播剧场):{len(live2_list)}条，合计{len(all_live)}")
    except Exception as e:
        print(f"❌错误：{str(e)}")
