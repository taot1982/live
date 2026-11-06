import requests

# 配置
FETCH_URL = "https://1525041261-gl7b7quwot.ap-hongkong.tencentscf.com?secret=badboytcl"
OUTPUT_PATH = "ZB.TXT"  # 输出到项目根目录
TIMEOUT = 30

def main():
    headers = {
        "User‑Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    try:
        resp = requests.get(FETCH_URL, headers=headers, timeout=TIMEOUT)
        resp.raise_for_status()  # 4xx/5xx抛出HTTPError
    except requests.exceptions.RequestException as e:
        print(f"❌【内容获取失败】URL:{FETCH_URL}，错误信息：{str(e)}")
        return

    # 请求成功，尝试解析文本并写入本地文件
    try:
        text_data = resp.text
        with open(OUTPUT_PATH, "w", encoding="utf‑8") as f:
            f.write(text_data)
        print(f"✅ ZB.TXT 更新完成，输出路径：{OUTPUT_PATH}，返回内容长度：{len(text_data)}")
    except Exception as e:
        print(f"❌【响应解析/写入失败】输出文件:{OUTPUT_PATH}，错误信息：{str(e)}")
        return


if __name__ == "__main__":
    main()
