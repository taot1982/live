# -*- coding: utf-8 -*-
import os
import requests
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

# ========== 配置 ==========
SOURCE_URL = "https://shturl.cc/H30FXbcPYS07udKfh5Vj"
EXTRA_URL = "http://203.135.100.107:7681/iptasd.txt"

LOCAL_TXT_PATH = "uzi.txt"
LIVE1 = "live1.txt"
LIVE2 = "live2.txt"
OUTPUT = "live.txt"

TIMEOUT = 10
MAX_WORKERS = 8
READ_BYTES = 2048
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
                print(f"[片段预览] {repr(text[:300])}")
                return text
            except UnicodeDecodeError:
                continue
        return ""
    except Exception as e:
        print(f"[拉远程失败] {url} {e}")
        return ""


def parse_m3u_content(content, fallback_group):
    if not content:
        return []
    # 标准 #genre# / EXTINF 解析
    if content.lstrip().startswith("#EXTM3U"):
        groups = []
        items = []
        last_name = fallback_group
        lines = [line.strip() for line in content.splitlines() if line.strip()]
        for line in lines:
            if line.startswith("#EXTINF"):
                if "," in line:
                    last_name = line.split(",", 1)[1].strip()
            elif line.startswith("http"):
                items.append((last_name, line))
        if items:
            groups.append({"group_name": fallback_group, "items": items, "skip_test": False})
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

    # 如果标准解析为空：粗暴备用解析，全部塞进 fallback 分组
    if not groups:
        print("[备用解析触发，格式识别失败，走通用按行读取]")
        items = []
        for line in content.splitlines():
            s = line.strip()
            if s and "," in s and s.startswith(("http", "rtmp")):
                name, link = s.split(",", 1)
                items.append((name.strip(), link.strip()))
        if items:
            groups.append({"group_name": fallback_group, "items": items, "skip_test": False})
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

    g1 = parse_m3u_content(t1, "上游源一")
    g2 = parse_m3u_content(t2, "上游源二")

    all_groups = g1 + g2
    print(f"[解析后分组总数] {len(all_groups)}")
    if len(all_groups) == 0:
        print("【致命】两个上游全部解析不出频道！")

    url_set = set()
    for g in all_groups:
        if not g.get("skip_test"):
            for _, u in g["items"]:
                url_set.add(u)

    delay_map = {}
    if url_set:
        print(f"[测速总数] {len(url_set)}")
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
            fu = {ex.submit(check_stream, u): u for u in url_set}
            for fut in as_completed(fu):
                ok, cost, u = fut.result()
                delay_map[u] = (ok, cost)

    out_lines = []
    # 先输出测速存活，组内按延迟排序
    for g in all_groups:
        out_lines.append(f"{g['group_name']},#genre#")
        item_list = []
        for name, u in g["items"]:
            ok, d = delay_map.get(u, (False, 999))
            if ok:
                item_list.append((d, name, u))
        item_list.sort(key=lambda x: x[0])
        for d, name, u in item_list:
            out_lines.append(f"{name},{u}")

    # 兜底：测速后为空，输出原始全部
    if not out_lines and all_groups:
        print("[兜底触发：测速全部失败，写出原始源]")
        for g in all_groups:
            out_lines.append(f"{g['group_name']},#genre#")
            for name, u in g["items"]:
                out_lines.append(f"{name},{u}")

    # 终极兜底：连分组都拿不到，直接把原始文本原样写入
    if not out_lines:
        print("[终极兜底：解析失败，直接原样写入原始文本")
        raw_text = []
        if t1:
            raw_text.append(t1)
        if t2:
            raw_text.append(t2)
        out_lines = raw_text

    txt = "\n".join(out_lines)
    with open(LIVE2, "w", encoding="utf-8") as f:
        f.write(txt)
    print(f"[完成] {LIVE2}")


def merge():
    print("\n===== 合并 live1 + live2 -> live.txt =====")
    part1 = ""
    part2 = ""
    if os.path.exists(LIVE1):
        with open(LIVE1, "r", encoding="utf-8") as f:
            part1 = f.read().strip()
    if os.path.exists(LIVE2):
        with open(LIVE2, "r", encoding="utf-8") as f:
            part2 = f.read().strip()

    chunks = []
    if part1:
        chunks.append(part1)
    if part2:
        chunks.append(part2)
    final = "\n\n".join(chunks)
    with open(OUTPUT, "w", encoding="utf-8") as f:
        f.write(final)
    print(f"[完成] {OUTPUT}")


def main():
    build_live1()
    build_live2()
    merge()
    print("\n全部任务结束")


if __name__ == "__main__":
    main()
