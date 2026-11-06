import requests
import os
import time

FETCH_URL = "https://1525041261-gl7b7quwot.ap-hongkong.tencentscf.com?secret=badboytcl"
OUTPUT_PATH = "ZB.TXT"
TIMEOUT = 30
RETRY_COUNT = 3

def main():
    print("===== 调试信息 =====")
    print("当前工作目录:", os.getcwd())
    print("待写入文件路径:", os.path.abspath(OUTPUT_PATH))

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    text_data = ""
    for i in range(RETRY_COUNT):
        try:
            resp = requests.get(FETCH_URL, headers=headers, timeout=TIMEOUT)
            print(f"第{i+1}次尝试，HTTP状态码: {resp.status_code}")
            resp.raise_for_status()
            text_data = resp.text
            print(f"✅ 接口拉取成功，内容长度：{len(text_data)}")
            break
        except requests.exceptions.RequestException as e:
            print(f"❌ 第{i+1}次请求失败：{e}")
            if i != RETRY_COUNT -1:
                time.sleep(2)

    # 强制写入文件，不管成功失败都生成ZB.TXT
    try:
        with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
            f.write(text_data)
        if os.path.exists(OUTPUT_PATH):
            print(f"✅ 文件写入完成，runner内已存在ZB.TXT")
        else:
            print("❌ 写入后文件仍然不存在！")
    except Exception as e:
        print(f"❌ 文件写入异常：{e}")

if __name__ == "__main__":
    main()
