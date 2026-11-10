#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GitHub Actions 定时任务用：抓取上游 m3u 直播源 → 转成 TVBox / 影视仓 可用的文件

输出（仓库根目录，UTF-8 无 BOM）：
  live_tvbox.txt     全量（含运营商内网组播，组播分组排在最后）
  live_stats.txt     本次运行统计（频道数、分组数、时间）

用法：
  python3 tvbox_gen.py                       # 用默认源
  SOURCE_URL="https://.../live.m3u?key=x" python3 tvbox_gen.py
  python3 tvbox_gen.py --url "..." --out .
"""

import argparse
import os
import re
import sys
import urllib.request
from datetime import datetime, timezone, timedelta

DEFAULT_URL = "https://dotv.tmxk.kdns.fr/live.m3u?key=LEON888"
UA = "okhttp/6.0"

# 上游夹带的推广/公告频道，一律丢弃
DROP_NAMES = {"加入TG频道@tmxktg"}
DROP_GROUPS = {"📢 频道关注"}

# 「昨天11-09 / 今天11-10 / 明天11-11」这类按日期命名的分组，
# 去掉日期后分组名才稳定，否则每天 TVBox 里都多出三个新分组
DATE_TAIL = re.compile(r"(昨天|今天|明天)\s*\d{1,2}-\d{1,2}")


def fetch(url, timeout=25, proxy=None):
    """默认直连（不走系统代理）；需要时可用 --proxy 显式指定，如 http://127.0.0.1:7890"""
    handlers = []
    if proxy:
        handlers.append(urllib.request.ProxyHandler({"http": proxy, "https": proxy}))
    else:
        handlers.append(urllib.request.ProxyHandler({}))
    opener = urllib.request.build_opener(*handlers)
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
    with opener.open(req, timeout=timeout) as r:
        raw = r.read()
    for enc in ("utf-8", "gb18030"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", "ignore")


def normalize_group(g):
    g = DATE_TAIL.sub(lambda m: m.group(1), g)
    return g.strip() or "其他"


def parse_m3u(text):
    items, cur = [], None
    for raw in text.splitlines():
        s = raw.strip()
        if not s:
            continue
        if s.startswith("#EXTINF"):
            g = re.search(r'group-title="([^"]*)"', s)
            logo = re.search(r'tvg-logo="([^"]*)"', s)
            name = s.rsplit(",", 1)[-1].strip() if "," in s else ""
            cur = {
                "group": normalize_group(g.group(1) if g else ""),
                "logo": logo.group(1) if logo else "",
                "name": name,
                "url": None,
            }
            items.append(cur)
        elif not s.startswith("#"):
            if cur is not None and cur["url"] is None:
                cur["url"] = s
    return [
        i
        for i in items
        if i["url"]
        and i["name"]
        and i["name"] not in DROP_NAMES
        and i["group"] not in DROP_GROUPS
        and "," not in i["name"]
    ]


def dedup(items):
    seen, out = set(), []
    for i in items:
        k = (i["group"], i["name"], i["url"])
        if k in seen:
            continue
        seen.add(k)
        out.append(i)
    return out


def reorder(items):
    """组播分组挪到最后（内网 IGMP 源，公网环境多半播不动，放前面只会碍事）"""
    return [i for i in items if "组播" not in i["group"]] + [
        i for i in items if "组播" in i["group"]
    ]


def group_map(items):
    gm = {}
    for i in items:
        gm.setdefault(i["group"], []).append(i)
    return gm


def to_txt(items):
    out = []
    for g, lst in group_map(items).items():
        out.append(f"{g},#genre#")
        out += [f"{i['name']},{i['url']}" for i in lst]
    return "\n".join(out) + "\n"


def to_m3u(items):
    out = ["#EXTM3U"]
    for i in items:
        out.append(
            f'#EXTINF:-1 tvg-name="{i["name"]}" tvg-logo="{i["logo"]}" '
            f'group-title="{i["group"]}",{i["name"]}'
        )
        out.append(i["url"])
    return "\n".join(out) + "\n"


def write(path, text):
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default=os.environ.get("SOURCE_URL", DEFAULT_URL))
    ap.add_argument("--proxy", default=os.environ.get("SOURCE_PROXY", ""))
    ap.add_argument("--out", default=".")
    args = ap.parse_args()

    os.makedirs(args.out, exist_ok=True)

    try:
        text = fetch(args.url, proxy=args.proxy or None)
    except Exception as e:
        print(f"[ERROR] 抓取上游失败：{e}", file=sys.stderr)
        return 1   # 失败就不覆盖已有文件，保证仓库里始终是上一次的好数据

    items = reorder(dedup(parse_m3u(text)))
    if not items:
        print("[ERROR] 解析结果为空，上游格式可能变了", file=sys.stderr)
        return 1

    gw = [i for i in items if "组播" not in i["group"]]

    write(os.path.join(args.out, "live_tvbox.txt"), to_txt(items))

    ts = datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d %H:%M:%S")
    stats = (
        f"更新时间：{ts} (UTC+8)\n"
        f"全量频道：{len(items)}\n"
        f"公网频道：{len(gw)}\n"
        f"分组数：{len(group_map(items))}\n"
    )
    write(os.path.join(args.out, "live_stats.txt"), stats)
    print(stats.strip())
    return 0


if __name__ == "__main__":
    sys.exit(main())
