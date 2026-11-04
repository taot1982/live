import requests
import concurrent.futures
import time
import re

# ===================== 配置区（只改这里）=====================
SCF_BASE = "https://1525041261-hd5hacihfc.ap-shanghai.tencentscf.com?token=202120785&url="
PUBLIC_PROXY = "https://proxy.yumus.cn/?url="
SOURCE_URL = "https://sttottv.ccwu.cc/ZB.TXT"
EXTRA_URL = "http://203.135.100.107:7681/iptasd.txt"

OUTPUT_FILE = "live.m3u"
TIMEOUT = 6
TEST_BYTES = 2048  # 只读取少量数据，减少误杀
MAX_WORKERS = 12
# ============================================================

def fetch_with_fallback(raw_url):
    """优先走自己SCF，失败自动切公共中转"""
    try:
        u1 = SCF_BASE + raw_url
        r = requests.get(u1, timeout=TIMEOUT)
        if 200 <= r.status_code < 300:
            return r.content
    except Exception:
        pass
    try:
        u2 = PUBLIC_PROXY + raw_url
        r = requests.get(u2, timeout=TIMEOUT)
        if 200 <= r.status_code < 300:
            return r.content
    except Exception:
        pass
    return None

def fetch_text(url):
    print(f"[拉取] {url}")
    raw = fetch_with_fallback(url)
    if raw is None:
        print(f"[失败] {url} 两个中转都拉不到")
        return ""
    for enc in ("utf-8", "gb18030", "gbk", "latin-1"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return ""

def test_stream(url):
    """测速，返回 (url, delay)，失败delay=None"""
    st = time.time()
    try:
        resp = requests.get(url, timeout=TIMEOUT, stream=True)
        if resp.status_code != 200:
            return (url, None)
        # 只读一小段，不完整下载
        next(resp.iter_content(TEST_BYTES))
        delay = round(time.time() - st, 3)
        return (url, delay)
    except Exception:
        return (url, None)

def parse_m3u(text):
    """
    按 #EXTGRP 分组，同一个频道名称归为一组
    返回结构：[ (分组名, 频道名, [(info行, url)] ) ]
    保持【分组顺序、频道先后顺序不变】，仅同频道多个源内部按延迟排序
    """
    groups = []
    current_group_name = "默认组"
    # key:频道名称，value:[(info_line, url)]
    chan_dict = {}
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if line.startswith("#EXTGRP:"):
            # 保存上一个分组
            if chan_dict:
                for ch_name, items in chan_dict.items():
                    groups.append((current_group_name, ch_name, items))
            chan_dict = {}
            current_group_name = line.replace("#EXTGRP:", "").strip()
            i += 1
            continue
        if line.startswith("#EXTINF:"):
            info_line = line
            # 提取频道名称 ,后面的内容
            if "," in info_line:
                ch_name = info_line.split(",",1)[1].strip()
            else:
                ch_name = "未知频道"
            i += 1
            if i >= len(lines):
                break
            url_line = lines[i].strip()
            if url_line and not url_line.startswith("#"):
                if ch_name not in chan_dict:
                    chan_dict[ch_name] = []
                chan_dict[ch_name].append((info_line, url_line))
            i += 1
            continue
        i += 1
    # 收尾最后一组
    if chan_dict:
        for ch_name, items in chan_dict.items():
            groups.append((current_group_name, ch_name, items))
    return groups

def main():
    # 合并两个源文本
    text1 = fetch_text(SOURCE_URL)
    text2 = fetch_text(EXTRA_URL)
    all_text = text1 + "\n" + text2
    if not all_text.strip():
        print("所有源全部拉取失败！")
        return

    group_list = parse_m3u(all_text)
    if not group_list:
        print("没有解析到频道！")
        return

    out_lines = ["#EXTM3U"]
    all_urls = []
    # 先收集全部待测速url
    for g_name, ch_name, items in group_list:
        for _,u in items:
            all_urls.append(u)

    # 批量测速
    result_map = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
        futures = {ex.submit(test_stream, u):u for u in all_urls}
        for fut in concurrent.futures.as_completed(futures):
            u, d = fut.result()
            result_map[u] = d

    # 遍历：分组顺序不变、频道顺序不变；同一个频道内多个源，存活的按延迟从小到大排序
    last_group = None
    for g_name, ch_name, items in group_list:
        if g_name != last_group:
            out_lines.append(f"#EXTGRP:{g_name}")
            last_group = g_name
        # 过滤有效源，带上延迟
        valid_items = []
        for info, u in items:
            d = result_map.get(u)
            if d is not None:
                valid_items.append((info, u, d))
        # 同频道内部，按延迟排序
        valid_items.sort(key=lambda x: x[2])
        # 写入
        for info, u, d in valid_items:
            out_lines.append(info)
            out_lines.append(u)

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(out_lines))
    print(f"\n✅ 完成：分组顺序、频道顺序保持原样；同一频道多条源按延迟排序，失效源剔除")

if __name__ == "__main__":
    main()
