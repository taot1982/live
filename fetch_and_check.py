# -*- coding: utf-8 -*-
import os
import requests
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

# ========== 配置 ==========
# 如果这两个源已经失效，换成你可用的上游
SOURCE_URL = "http://sttottv.ccwu.cc/ZB.TXT"
EXTRA_URL = "http://203.135.100.107:7681/iptasd.txt"

LOCAL_TXT_PATH = "uzi.txt"
LIVE1 = "live1.txt"
LIVE2 = "live2.txt"
OUTPUT = "live.txt"

TIMEOUT = 10
MAX_WORKERS = 8
READ_BYTES = 2048
# 如果不需要过滤分组，可以把这个清空列表 NEED_GROUPS = []
NEED_GROUPS = []
UZI_GROUP_NAME = "东方有线"
REPLACE_OLD_TEXT = "吉林松原酒店 吉林联通"
REPLACE_NEW_TEXT = "东方有线"
# ==========================


def check_stream(url: str):
    if not (url.startswith("http://") or url.startswith("https://")):
        return (True, 0.0, url)
    headers = {"User-Agent": "VLC/3.0.18 LibVLC/3.0.18"}
    for _ in range(2):
        try:
            t0 = time.perf_counter()
            with requests.get(
                url, timeout=TIMEOUT, headers=headers,
                stream=True, allow_redirects=True
            ) as r:
                if not (200 <= r.status_code < 400):
                    continue
                next(r.iter_content(chunk_size=READ_BYTES), None)
                cost = time.perf_counter() - t0
                return (True, cost, url)
        except Exception as e:
            print(f"[测速] {url} -> {e}")
            time.sleep(0.2)
    return (False, 999.0, url)


def fetch_text(url):
    print(f"[拉远程] {url}")
    try:
        resp = requests.get(url, timeout=TIMEOUT)
        resp.raise_for_status()
        raw = resp.content
        for enc in ("utf-8", "gb18030", "gbk", "latin-1"):
            try:
                text = raw.decode(enc)
                print(f"[获取成功] {url} 长度：{len(text)}")
                return text
            except UnicodeDecodeError:
                continue
        return ""
    except Exception as e:
        print(f"[拉远程失败] {url} {e}")
        return ""


def parse_m3u_content(content, group_name):
    if not content:
        return []
    if content.lstrip().startswith("#EXTM3U"):
        groups = []
        items = []
        last_name = "未知"
        lines = [line.strip() for line in content.splitlines() if line.strip()]
        for line in lines:
            if line.startswith("#EXTINF"):
                if "," in line:
                    last_name = line.split(",", 1)[1].strip()
            elif line.startswith("http"):
                items.append((last_name, line))
        if items:
            groups.append({"group_name": group_name, "items": items, "skip_test": False})
        return groups

    groups = []
    current = None
    for line in content.splitlines():
        s = line.strip()
        if s.endswith(",#genre#"):
            g = s.rsplit(",#genre#", 1)[0].strip()
            current = {"group_name": g, "items": [], "skip_test": False}
            groups.append(current)
        elif current and "," in s and not s.startswith("#"):
            n, u = s.split(",", 1)
            current["items"].append((n.strip(), u.strip()))
    return groups


def build_live1():
    print("\n===== 生成 live1.txt（本地 uzi） =====")
    if not os.path.exists(LOCAL_TXT_PATH):
        print("[警告] uzi.txt 不存在，live1 为空")
        with open(LIVE1, "w", encoding="utf-8") as f:
            f.write("")
        return

    with open(LOCAL_TXT_PATH, "rb") as f:
        raw = f.read()
    text = ""
    for enc in ("utf-8", "gb18030", "gbk", "latin-1"):
        try:
            text = raw.decode(enc)
            break
        except Exception:
            continue

    text = text.replace(REPLACE_OLD_TEXT, REPLACE_NEW_TEXT)

    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    out = [f"{UZI_GROUP_NAME},#genre#"]
    for ln in lines:
        if not ln.endswith(",#genre#"):
            out.append(ln)
    result = "\n".join(out)
    with open(LIVE1, "w", encoding="utf-8") as f:
        f.write(result)
    print(f"[完成] {LIVE1}，已完成文本替换")


def build_live2():
    print("\n===== 生成 live2.txt（远程源） =====")
    t1 = fetch_text(SOURCE_URL)
    t2 = fetch_text(EXTRA_URL)

    g1 = parse_m3u_content(t1, "主源频道")
    g2 = parse_m3u_content(t2, "附加频道")

    
