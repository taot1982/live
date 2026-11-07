import requests
import re

def main():
    url = "http://smzb.bypbwxx.top/zhibo/lvdou/zhibo.txt"
    output_path = "zhibo.txt"

    # 【和你 fix.py 一致的乱码修复逻辑】
    def clean_text(text: str) -> str:
        text = text.replace("\ufeff", "")
        text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', "", text)
        return text

    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        resp = requests.get(url, headers=headers, timeout=30)
        resp.raise_for_status()
        raw_content = resp.text
    except Exception as e:
        print(f"❌ 下载源文件失败：{e}")
        raw_content = ""

    raw_content = clean_text(raw_content)
    lines = raw_content.splitlines()
    out_lines = []
    group_cnt = 0

    for line in lines:
        line = line.strip()
        if not line:
            out_lines.append("")
            continue

        # 判断分组标记 ,#genre#
        if ",#genre#" in line:
            group_cnt += 1
            # 第二个分组，强制改成 央视咪咕
            if group_cnt == 2:
                out_lines.append("央视咪咕,#genre#")
            else:
                out_lines.append(line)
        else:
            # 频道行全部原样保留，不改动频道名和链接
            out_lines.append(line)

    result = "\n".join(out_lines)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(result)

    print(f"✅ 处理完毕，输出文件：{output_path}，总共识别分组数量：{group_cnt}")

if __name__ == "__main__":
    main()
