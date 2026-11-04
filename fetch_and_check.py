import requests
import json

# ==========配置区==========
# 远程源，github runner大概率无法访问；失败建议把文件存仓库，改为读取本地文件 open("iptasd.txt","r",encoding="utf‑8")
src_url = "http://203.135.100.107:7681/iptasd.txt"
# 需要提取的分组名称（匹配#genre#后面的文字）
target_groups = {"4K频道","轮播剧场"}
out_file = "config.json"
# =========================

def fetch_txt(url):
    resp = requests.get(url,timeout=15)
    # 源实际返回是utf‑8（你上面抓取内容是utf‑8，不是gbk）
    resp.encoding = "utf‑8"
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
    txt = fetch_txt(src_url)
    live1_list,live2_list = parse_content(txt)
    # 整合输出：live1在前，live2追加在后面，完整给影视仓使用
    all_live = live1_list + live2_list
    output = {
        "live": all_live
    }
    with open(out_file,"w",encoding="utf‑8") as f:
        json.dump(output,f,ensure_ascii=False,indent=2)
    print(f"处理完成：live1:{len(live1_list)}条，live2(4K+轮播剧场):{len(live2_list)}条，合计{len(all_live)}")
