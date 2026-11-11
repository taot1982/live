#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GitHub Actions 定时任务用：抓取上游 m3u 直播源 → 生成 TVBox / 影视仓 用的 live_tvbox.txt

特性：
  · 本次抓取没有「稳定源·阿里云服2」这一组时，自动沿用原文件里的这一组（位置也还原）
  · 抓取/解析失败不写文件，仓库里保留上一版好数据
"""

import argparse
import os
import re
import sys
import urllib.request
from datetime import datetime, timezone, timedelta

DEFAULT_URL = "https://dotv.tmxk.kdns.fr/live.m3u?key=LEON888"
UA = "okhttp/6.0"
OUT_NAME = "live_tvbox.txt"        # 若 workflow 里 git add 的是 live_tvbox_gw.txt，把这行改掉

DROP_NAMES = {"加入TG频道@tmxktg"}
DROP_GROUPS = {"📢 频道关注"}
DROP_GROUP_KEYWORDS = {"咪咕·体育"}

# 上游随机不下发这个组（同一地址连抓 5 次常有 3 次没有），本次缺了就沿用原文件里的
CARRY_OVER_KEYWORDS = ("稳定源",)


def fetch(url, timeout=25, proxy=None):
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
            cur = {"group": normalize_group(g.group(1) if g else ""), "name": name, "url": None}
            items.append(cur)
        elif not s.startswith("#"):
            if cur is not None and cur["url"] is None:
                cur["url"] = s
    return [
        i for i in items
        if i["url"] and i["name"]
        and i["name"] not in DROP_NAMES
        and i["group"] not in DROP_GROUPS
        and not any(k in i["group"] for k in DROP_GROUP_KEYWORDS)
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
    return [i for i in items if "组播" not in i["group"]] + \
           [i for i in items if "组播" in i["group"]]


def to_txt(items):
    out, gm = [], {}
    for i in items:
        gm.setdefault(i["group"], []).append(i)
    for g, lst in gm.items():
        out.append(f"{g},#genre#")
        out += [f"{i['name']},{i['url']}" for i in lst]
    return "\n".join(out) + "\n"


# ========== 新增：缺组时沿用原文件的那一组 ==========
def read_txt_groups(path):
    """读已有产物，切成 [{group, items:[(名, url)]}]，保留原顺序"""
    if not os.path.exists(path):
        return []
    groups, cur = [], None
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            for raw in f:
                s = raw.strip()
                if not s:
                    continue
                if s.endswith(",#genre#"):
                    cur = {"group": s[: -len(",#genre#")].strip(), "items": []}
                    groups.append(cur)
                elif cur is not None and "," in s:
                    n, u = s.split(",", 1)
                    if u.strip().lower().startswith("http"):
                        cur["items"].append((n.strip(), u.strip()))
    except Exception as e:
        print(f"[WARN] 读取原文件失败：{e}", file=sys.stderr)
    return groups


def carry_over(items, path):
    """本次没有的关键分组，从原文件补回来（按原文件里的位置插回）"""
    prev = read_txt_groups(path)
    have = {i["group"] for i in items}
    order = [i["group"] for i in items]
    for idx, g in enumerate(prev):
        name = g["group"]
        if name in have or not g["items"]:
            continue
        if not any(k in name for k in CARRY_OVER_KEYWORDS):
            continue
        pos = min(idx, len(order)) if order else 0
        items[pos:pos] = [{"group": name, "name": n, "url": u} for n, u in g["items"]]
        order.insert(pos, name)
        have.add(name)
        print(f"[CARRY] 本次上游没有下发「{name}」，已沿用原文件里的 {len(g['items'])} 条源",
              file=sys.stderr)
    return items


def write(path, text):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    os.replace(tmp, path)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default=os.environ.get("SOURCE_URL", DEFAULT_URL))
    ap.add_argument("--proxy", default=os.environ.get("SOURCE_PROXY", ""))
    ap.add_argument("--out", default=".")
    ap.add_argument("--file", default=OUT_NAME)
    ap.add_argument("--no-multicast", action="store_true")
    args = ap.parse_args()

    os.makedirs(args.out, exist_ok=True)
    out_path = os.path.join(args.out, args.file)

    try:
        text = fetch(args.url, proxy=args.proxy or None)
    except Exception as e:
        print(f"[ERROR] 抓取上游失败：{e}", file=sys.stderr)
        return 1

    items = dedup(parse_m3u(text))
    if not items:
        print("[ERROR] 解析结果为空，上游格式可能变了", file=sys.stderr)
        return 1

    # 缺组沿用：必须在筛组播之前做，这样沿用的是原文件里已经处理过的成品
    items = dedup(carry_over(items, out_path))

    if args.no_multicast:
        items = [i for i in items if "组播" not in i["group"]]
    items = reorder(items)

    write(out_path, to_txt(items))

    ts = datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d %H:%M:%S")
    gm = {}
    for i in items:
        gm[i["group"]] = gm.get(i["group"], 0) + 1
    stable = sum(n for g, n in gm.items() if "稳定源" in g)

    print(
        f"更新时间：{ts} (UTC+8)\n"
        f"频道数：{len(items)}\n"
        f"分组数：{len(gm)}\n"
        f"稳定源：{'%d 个频道' % stable if stable else '无（原文件里也没有）'}\n"
        f"输出：{out_path}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
