#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GitHub Actions 定时任务用：抓取上游 m3u 直播源 → 生成 TVBox / 影视仓 用的 live_tvbox_gw.txt

输出（单个文件，UTF-8 无 BOM）：
  live_tvbox_gw.txt    「分组,#genre#」+「频道名,url」标准直播源格式
                       （含各省运营商地方组播分组；已剔除咪咕体育按日切分的临时赛事流）

用法：
  python3 tvbox_gen.py                       # 用默认源
  SOURCE_URL="https://.../live.m3u?key=x" python3 tvbox_gen.py
  python3 tvbox_gen.py --url "..." --out .
  python3 tvbox_gen.py --no-multicast        # 只要公网源，剔除运营商地方组播分组
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

# 咪咕体育按「昨天/今天/明天」切分的赛事临时流：分组天天增殖、内容是一次性比赛回放，
# 没有保留价值，整组丢弃
DROP_GROUP_KEYWORDS = {"咪咕·体育"}


def fetch(url, timeout=25, proxy=None):
    """默认直连（不走系统代理变量）；需要时用 --proxy 显式指定，如 http://127.0.0.1:7890"""
    if proxy:
        handlers = [urllib.request.ProxyHandler({"http": proxy, "https": proxy})]
    else:
        handlers = [urllib.request.ProxyHandler({})]
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
    return g.strip() or "其他"


def parse_m3u(text):
    items, cur = [], None
    for raw in text.splitlines():
        s = raw.strip()
        if not s:
            continue
        if s.startswith("#EXTINF"):
            g = re.search(r'group-title="([^"]*)"', s)
            name = s.rsplit(",", 1)[-1].strip() if "," in s else ""
            cur = {
                "group": normalize_group(g.group(1) if g else ""),
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
        and not any(k in i["group"] for k in DROP_GROUP_KEYWORDS)
        and "," not in i["name"]   # txt 格式用逗号分隔，频道名不能带英文逗号
    ]


def dedup(items):
    """同分组+同名+同链接去重；同名不同链接（多服务器）保留，TVBox 会依次尝试"""
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


def to_txt(items):
    out, gm = [], {}
    for i in items:
        gm.setdefault(i["group"], []).append(i)
    for g, lst in gm.items():
        out.append(f"{g},#genre#")
        out += [f"{i['name']},{i['url']}" for i in lst]
    return "\n".join(out) + "\n"


def write(path, text):
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default=os.environ.get("SOURCE_URL", DEFAULT_URL))
    ap.add_argument("--proxy", default=os.environ.get("SOURCE_PROXY", ""))
    ap.add_argument("--out", default=".")
    ap.add_argument("--no-multicast", action="store_true",
                    help="剔除分组名含「组播」的运营商内网源，只留公网源（默认保留组播）")
    args = ap.parse_args()

    os.makedirs(args.out, exist_ok=True)

    try:
        text = fetch(args.url, proxy=args.proxy or None)
    except Exception as e:
        print(f"[ERROR] 抓取上游失败：{e}", file=sys.stderr)
        return 1   # 失败就不写文件，仓库里保留上一次的好数据

    items = dedup(parse_m3u(text))
    if not items:
        print("[ERROR] 解析结果为空，上游格式可能变了", file=sys.stderr)
        return 1

    # 默认保留运营商地方组播（各市/省本地频道，只有组播链路上有），需要纯公网源时才加 --no-multicast
    if args.no_multicast:
        items = [i for i in items if "组播" not in i["group"]]
    items = reorder(items)

    out_path = os.path.join(args.out, "live_tvbox_gw.txt")
    write(out_path, to_txt(items))

    ts = datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d %H:%M:%S")
    print(
        f"更新时间：{ts} (UTC+8)\n"
        f"频道数：{len(items)}\n"
        f"分组数：{len({i['group'] for i in items})}\n"
        f"输出：{out_path}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
