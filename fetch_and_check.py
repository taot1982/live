import requests
import concurrent.futures
import time
import re
import sys
import warnings
warnings.filterwarnings("ignore")

# 修复日志编码
sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

# ===================== 配置区 =====================
source_list = [
    "http://203.135.100.107:7681/iptasd.txt",
    "https://sttottv.ccwu.cc/ZB.TXT"
]
OUTPUT_FILE = "live.txt"
TEST_TIMEOUT = 4
FETCH_SOURCE_TIMEOUT = 20
FETCH_MAX_RETRY = 3
CONCURRENCY = 4
READ_BYTES = 2048
# 尝试的编码顺序
TRY_ENCODINGS = ["gbk", "gb2312", "utf-8"]
# ==================================================

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}


def fetch_with_retry(url, max_retry=3, timeout=20):
    last_exception = None
    for attempt in range(1, max_retry + 1):
        try:
            resp = requests.get(url, headers=headers, timeout=timeout, verify=False)
            if 500 <= resp.status_code < 600:
                print(f"[上游重试 {attempt}/{max_retry}] {url} status={resp.status_code}")
                time.sleep(1.5)
                continue
            resp.raise_for_status()
            return resp
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
            last_exception = e
            print(f"[上游重试 {attempt}/{max_retry}] {url} 网络异常: {str(e)}")
            time.sleep(1.5)
        except Exception as e:
            last_exception = e
            print(f"[上游放弃不再重试] {url} : {str(e)}")
            break
    raise last_exception


def get_text_auto_decode(resp):
    """自动尝试编码解码，解决GBK乱码"""
    raw_bytes = resp.content
    for enc in TRY_ENCODINGS:
        try:
            text = raw_bytes.decode(enc)
            print(f"✅ 编码识别成功：{enc}")
            return text
        except UnicodeDecodeError:
            continue
    # 全部失败兜底：替换无法解析字符
    print(f"⚠️ 全部编码尝试失败，使用replace兜底解码")
    return raw_bytes.decode("utf-8", errors="replace")


def test_stream(url):
    try:
        start = time.time()
        r = requests.get(url, headers=headers, timeout=TEST_TIMEOUT, stream=True, verify=False)
        r.raise_for_status()
        next(r.iter_content(chunk_size=READ_BYTES))
        delay = time.time() - start
        return (url, delay, True)
    except Exception:
        return (url, 999.9, False)


def txt_to_m3u(raw_text):
    lines = raw_text.splitlines()
    current_group = "默认组"
    out = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        # 清洗特殊异常符号
        line = line.replace('\u2011', '-')
        line = line.replace('\ufffd', '')
        if line.endswith(",#genre#"):
            current_group = line.replace(",#genre#", "").strip()
            continue
        sp = line.split(",")
        if len(sp)>=2:
            ch_name = sp[0].strip()
            ch_url = sp[1].strip()
            if ch_url.startswith("http"):
                out.append(f'#EXTINF:-1 group-title="{current_group}",{ch_name}')
                out.append(ch_url)
    return "\n".join(out)


def parse_standard_m3u(raw_text):
    result = []
    lines = raw_text.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if not line:
            i += 1
            continue
        if line.startswith("#EXTINF:"):
            if i + 1 >= len(lines):
                i += 1
                continue
            url_line = lines[i+1].strip()
            if url_line.startswith("http"):
                grp_match = re.search(r'group-title="([^"]+)"', line)
                group_name = grp_match.group(1) if grp_match else "默认组"
                result.append({
                    "group": group_name,
                    "inf": line,
                    "url": url_line
                })
            i += 2
            continue
        i += 1
    return result


def main():
    all_m3u_raw = ""
    ok_source_count = 0

    for src in source_list:
        print(f"\n===== 开始拉取上游源: {src} =====")
        try:
            resp = fetch_with_retry(src, max_retry=FETCH_MAX_RETRY, timeout=FETCH_SOURCE_TIMEOUT)
            text = get_text_auto_decode(resp)
            if text.lstrip().startswith("#EXTM3U"):
                m3u_content = text
            else:
                m3u_content = "#EXTM3U\n" + txt_to_m3u(text)
            all_m3u_raw += m3u_content + "\n"
            ok_source_count += 1
            print(f"✅ 上游拉取&转换成功")
        except Exception as e:
            print(f"❌ 上游【完全失败】 {src} : {str(e)}")
            continue

    print(f"\n汇总：成功拉取上游数量 {ok_source_count}/{len(source_list)}")
    if not all_m3u_raw.strip():
        print("❌ 全部上游都拉取失败！输出空m3u模板")
        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            f.write("#EXTM3U\n")
        return

    channel_list = parse_standard_m3u(all_m3u_raw)
    if not channel_list:
        print("⚠️ 警告：解析后没有得到任何频道！检查上游返回内容")
        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            f.write("#EXTM3U\n")
        return
    print(f"解析得到频道总条目: {len(channel_list)}")

    url_map = {item["url"]: item for item in channel_list}
    url_result = {}

    # 线程池超时保护
    with concurrent.futures.ThreadPoolExecutor(max_workers=CONCURRENCY) as executor:
        future_map = {executor.submit(test_stream, u): u for u in url_map.keys()}
        for fut in concurrent.futures.as_completed(future_map, timeout=120):
            try:
                u, delay, ok = fut.result()
                url_result[u] = {"delay": delay, "ok": ok}
            except concurrent.futures.TimeoutError:
                u = future_map[fut]
                url_result[u] = {"delay": 999.9, "ok": False}
                print(f"⏱ 测速任务超时，标记失效：{u}")

    group_order = []
    group_bucket = {}
    for ch in channel_list:
        g = ch["group"]
        if g not in group_bucket:
            group_order.append(g)
            group_bucket[g] = []
        group_bucket[g].append(ch)

    out_lines = ["#EXTM3U"]
    valid_total = 0
    for gname in group_order:
        items = group_bucket[gname]
        valid = [it for it in items if url_result[it["url"]]["ok"]]
        valid.sort(key=lambda x: url_result[x["url"]]["delay"])
        for it in valid:
            out_lines.append(it["inf"])
            out_lines.append(it["url"])
            valid_total += 1

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(out_lines))
    print(f"\n✅ 处理完成，输出文件：{OUTPUT_FILE}")
    print(f"✅ 输出有效频道数量：{valid_total}")


if __name__ == "__main__":
    main()
