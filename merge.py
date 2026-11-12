# -*- coding: utf-8 -*-
"""
多源直播源合并 → live.txt
本机文件：ZB.TXT / iptv.txt / iptasd.txt / live_tvbox.txt / shiptv.txt
远端订阅：贵州电信组播 txt（GitHub raw，抓不到时回退本地缓存 gz_cctv.txt）
"""
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor

# ========== 和仓库文件名严格对齐 ==========
ZB_FILE = "ZB.TXT"
IPTV_FILE = "iptv.txt"
IPASD_FILE = "iptasd.txt"
TVBOX_FILE = "live_tvbox.txt"
SHIPTV_FILE = "shiptv.txt"     # 上海频道源文件
OUTPUT = "live.txt"
# ========================================

# 贵州电信组播源（央视+卫视），取 CCTV-1 之后的部分，改名为「高清央视卫视」
GZ_URL = ("https://raw.githubusercontent.com/q1017673817/iptvz/refs/heads/main/%E7%BB%84%E6%92%AD_%E5%8C%97%E4%BA%AC%E8%81%94%E9%80%9A.txt")
GZ_CACHE = "gz_cctv.txt"       # 抓取失败时的本地兜底文件
GZ_GROUP_NAME = "超高清·央视卫视"
GZ_UA = "okhttp/6.0"

# CCTV5+ 的频道名写法不统一：CCTV5+体育赛事 / CCTV5+ 体育赛事 / CCTV5+,体育赛事
# 统一用「行首 CCTV5+」判断，别再拿完整名称做 in 判断
CCTV5_PLUS_RE = re.compile(r"^\s*CCTV5\+")

# 从 CCTV-1 开始保留（(?!\d) 避免把 CCTV-10~17 误当成 CCTV-1）
CCTV1_RE = re.compile(r"^CCTV-?1(?!\d)")

# ZB.TXT 里要整组剔除的分组：分组名「等于或以其开头」才丢（组内频道一并不要）
ZB_DROP_GROUPS = ("央视频", "咪咕·央视", "咪咕央卫", "测试频道")
# 名字相近但必须保留的分组（「央视频道」前缀撞「央视频」，不写这里就会被误删）
ZB_KEEP_GROUPS = ("央视频道",)

# live_tvbox.txt 里只保留这些分组（白名单，前缀匹配），凑满 3 组为止
# 用白名单而不是黑名单：黑名单挡一组，补齐逻辑就会把下一组拉进来，永远堵不完
TVBOX_KEEP_GROUPS = ("稳定源·", "央视频·")
# 上游稳定源组名带版本号（…服2 / …服1 会变），输出统一改名为固定名，避免每天分组名乱跳
TVBOX_RENAME = {"稳定源": "稳定源·阿里云服"}
# 上游 m3u 被墙时，本地 live_tvbox.txt 就抓不到「稳定源·阿里云服2」。
# 填你 GitHub 仓库里 Actions 产物的 raw 地址（海外跑，能抓到），按顺序尝试，命中为止。
# 例：["https://raw.githubusercontent.com/<用户名>/<仓库>/main/live_tvbox_gw.txt",
#      "https://cdn.jsdelivr.net/gh/<用户名>/<仓库>@main/live_tvbox_gw.txt"]
TVBOX_REMOTE_URLS = [
    # "https://raw.githubusercontent.com/q1017673817/iptv/main/live_tvbox_gw.txt",
]

# 上游随机不下发稳定源组时用它上次的成果兜底，保证 live.txt 里这组不会凭空消失
STABLE_CACHE = "stable_group_cache.txt"

# ========== 跨组匹配 + 测速排序 ==========
# 从 live_tvbox.txt 这 4 个地方组播组里取源，匹配进 live.txt 的下面 2 个分组
MATCH_SOURCE_GROUPS = ("山东电信", "河南电信", "重庆联通", "河北联通")
MATCH_TARGET_GROUPS = ("央视频道", "卫视频道")

# ========== 港澳台源并入 live.txt ==========
# 从 live_hongkong.txt 这 2 个分组取源，并入 live.txt 的指定分组：
#   同名频道 → 源归到同一行（多条源按测速排序、剔除不通的）
#   新频道   → 追加到该分组末尾（同样按测速排序、剔除不通的）
# ========== 输出前分组改名 ==========
# 只改「分组头」的显示名，不动组内频道；在跨组匹配/测速/港澳台并入全部做完之后才执行，
# 所以 MATCH_TARGET_GROUPS 等逻辑仍然按原组名（央视频道 / 卫视频道）工作。
GROUP_RENAME_OUT = {
    "央视频道": "备用·央视频道",
    "卫视频道": "备用·卫视频道",
}

HK_FILE = "live_hongkong.txt"
HK_MERGE_GROUPS = ("台湾·四季台湾", "繁体·🔮港澳台直播")
HK_TARGET_GROUP = "新闻频道"

SPEED_TIMEOUT = 6.0        # 单条源测速超时（秒）；宁可多等也别误杀慢但能播的源
SPEED_WORKERS = 32         # 并发线程数（上限）
# 同一主机最多同时测几条：港台源常常几十条指向同一个 IP:端口，
# 一口气并发过去对方会限流/握手排队，全部超时被误判成死源（四季台湾整组曾因此全灭）
SPEED_PER_HOST = 4
SPEED_HOST_CONCURRENCY = 8   # 同时处理几台主机（× SPEED_PER_HOST ≈ 32 条并发）
SPEED_UA = "okhttp/6.0"
SPEED_DROP_DEAD = True     # True=剔除测速无响应的源
SPEED_DROP_DEAD_CHANNEL = True   # True=某频道所有源都不通时，连频道标题一起删；False=保留原标题源一条

# 兼顾电信/联通：两条线路各跑一次，测速结果存成 json，第二次会自动合并
# 用法：python3 merge_sources.py --net dx   （上海电信宽带下跑）
#       python3 merge_sources.py --net lt   （上海联通宽带下跑，会自动读上一步的 dx 结果）
SPEED_REPORT_DIR = "speed_reports"
SPEED_NET_TAGS = {"dx": "电信", "lt": "联通"}

# ========== 指定分组强制 User-Agent ==========
SHANGHAI_UA = ("AppleCoreMedia/1.0.0.15F79 (iPhone; U; CPU OS 11_4 like Mac OS X; zh_cn)")
UA_GROUPS = {"上海频道": SHANGHAI_UA}

# UA 输出方式：
#   "proxy" → live.txt 里该组地址改写成中转地址，由 shanghai_ua_proxy.py 注入 UA（最保险，
#             因为 TVBox 的 txt 不认 |User-Agent=，会把整串当 URL 发出去导致播不了）
#   "m3u"   → live.txt 不动，另出 live_ua.m3u（带 #EXTVLCOPT:http-user-agent=）
#   "pipe"  → 行尾追加 |User-Agent=...（多数 TVBox 不支持，仅部分 diyp 类客户端可用）
#   "off"   → 不处理
# UA 输出方式："off" = 不处理（上海频道的 UA 需求已取消）
# 需要重启时可改回 "proxy"（配合 shanghai_ua_proxy.py）或 "m3u"（另出 live_ua.m3u）
UA_MODE = "off"
UA_M3U_FILE = "live_ua.m3u"
# proxy 模式下 TVBox 要能访问到这台机器；可用环境变量 UA_PROXY_BASE 覆盖
UA_PROXY_BASE = os.environ.get("UA_PROXY_BASE", "http://192.168.1.100:8090")

# CCTV 名称后面允许出现的描述词，用于把「CCTV-1 综合」和「CCTV1」认成同一个台
# 不在表里的（如 CCTV4欧洲 / CCTV4美洲）不参与归一，避免把不同频道认成同一个
CCTV_REST_OK = {
    "", "综合", "财经", "综艺", "中文国际", "体育", "体育赛事", "电影",
    "国防军事", "电视剧", "纪录", "科教", "戏曲", "新闻", "少儿", "音乐",
    "农业农村", "社会与法", "高清", "频道", "高清综合", "新闻频道",
}


def zb_should_drop(group_name):
    """判断 ZB 的分组名是否要整组剔除：白名单优先，再按前缀匹配"""
    group_name = group_name.strip()
    if group_name in ZB_KEEP_GROUPS:
        return False
    return any(group_name.startswith(k) for k in ZB_DROP_GROUPS)


def fetch_text(url, timeout=25):
    """直连抓文本（不走系统代理变量），失败返回 None"""
    try:
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        req = urllib.request.Request(url, headers={"User-Agent": GZ_UA, "Accept": "*/*"})
        with opener.open(req, timeout=timeout) as r:
            raw = r.read()
    except Exception as e:
        print(f"⚠️ 抓取远端源失败：{e}")
        return None

    for enc in ("utf-8-sig", "utf-8", "gb18030"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return None


def read_lines(file_path):
    """统一读文件：兼容 BOM 与 GBK（Windows 存的 ZB.TXT 常见），读不到返回 None"""
    for enc in ("utf-8-sig", "utf-8", "gb18030"):
        try:
            with open(file_path, "r", encoding=enc) as f:
                return f.read().splitlines()
        except UnicodeDecodeError:
            continue
        except FileNotFoundError:
            return None
    print(f"⚠️ {file_path} 编码无法识别（试过 utf-8 / gb18030）")
    return None


def is_noise(line_strip):
    """三类噪声行：更新时间、#by、#节目数量"""
    if "更新时间" in line_strip:
        return True
    return line_strip.startswith("#by") or line_strip.startswith("#节目数量")


def filter_all_lines(file_path):
    """iptv.txt：过滤噪声行，强制 CCTV5+体育赛事 紧跟在 CCTV5-体育 后面"""
    lines = read_lines(file_path)
    if lines is None:
        print(f"⚠️ 文件 {file_path} 不存在，跳过 iptv 分组")
        return []

    out = []
    for line in lines:
        line_strip = line.strip()
        if not line_strip:
            continue
        if is_noise(line_strip):
            continue
        if line_strip.endswith(",#genre#"):
            continue
        line_strip = line_strip.replace("#类型：吉林松原酒店 吉林联通", "东方有线,#genre#")
        out.append(line_strip)

    # 分离 CCTV5+ 行
    cctv5_plus = None
    rest = []
    for l in out:
        if CCTV5_PLUS_RE.match(l):
            cctv5_plus = l
        else:
            rest.append(l)

    new_out = []
    for l in rest:
        new_out.append(l)
        # 碰到 CCTV5-体育，立刻把 CCTV5+ 塞在它后面
        if "CCTV5-体育" in l and cctv5_plus is not None:
            new_out.append(cctv5_plus)
            cctv5_plus = None
    # 兜底：没找到 CCTV5-体育 就放末尾，不丢频道
    if cctv5_plus is not None:
        new_out.append(cctv5_plus)

    print(f"{file_path} 保留行数：{len(new_out)}")
    return new_out


def extract_oriental_and_4k(file_path):
    """iptasd.txt：拆出 东方有线 / 4K频道 / 轮播剧场 三块内容（含分组头）"""
    lines = read_lines(file_path)
    if lines is None:
        print(f"⚠️ 文件 {file_path} 不存在，跳过 4K/轮播 分组")
        return [], []

    orient_block, other_block = [], []
    in_orient = in_other = False

    for line in lines:
        line_strip = line.strip()
        if not line_strip:
            continue
        if is_noise(line_strip):
            continue

        if line_strip.endswith(",#genre#"):
            in_orient = in_other = False
            if "东方有线" in line_strip:
                in_orient = True
                orient_block.append(line_strip)
            elif "4K频道" in line_strip or "轮播剧场" in line_strip:
                in_other = True
                other_block.append(line_strip)
            continue

        if in_orient:
            orient_block.append(line_strip)
        if in_other:
            other_block.append(line_strip)

    print(f"{file_path} 东方有线：{len(orient_block)} 行，4K+轮播：{len(other_block)} 行")
    return orient_block, other_block


def filter_zb(file_path):
    """ZB.TXT：分组结构原样保留，只过滤噪声行；央视频/咪咕央卫/测试频道 三个分组整组剔除"""
    lines = read_lines(file_path)
    if lines is None:
        print(f"⚠️ ZB.TXT 文件不存在，跳过 ZB 分组")
        return []

    out = []
    in_drop_group = False
    dropped = []

    for line in lines:
        line_strip = line.strip()
        if not line_strip:
            continue
        if is_noise(line_strip):
            continue

        # 分组头：判断是否属于要剔除的分组，是则整组（含分组头）跳过
        if line_strip.endswith(",#genre#"):
            group_name = line_strip.replace(",#genre#", "").strip()
            in_drop_group = zb_should_drop(group_name)
            if in_drop_group:
                dropped.append(group_name)
                continue
            out.append(line_strip)
            continue

        if in_drop_group:
            continue

        line_strip = line_strip.replace("吉林松原酒店 吉林联通", "东方有线")
        out.append(line_strip)

    print(f"{file_path} 保留行数：{len(out)}" + (f"，剔除分组：{'、'.join(dropped)}" if dropped else ""))
    return out


def parse_tvbox_groups(lines):
    """把 txt 切成分组块：[{"name": 分组名, "rows": [频道行...]}]"""
    groups, cur = [], None
    for line in lines:
        s = line.strip()
        if not s or is_noise(s):
            continue
        if s.endswith(",#genre#"):
            cur = {"name": s[: -len(",#genre#")].strip(), "rows": []}
            groups.append(cur)
            continue
        if cur is not None:
            cur["rows"].append(s)
    return groups


def fetch_stable_group_from_remote():
    """
    本地 live_tvbox.txt 缺稳定源组时，从 GitHub 上的 Actions 产物里捞
    （Actions 跑在海外，能访问被墙的 dotv 域名，所以它的产物里有这组）
    TVBOX_REMOTE_URLS 里按顺序尝试，命中就返回 {"name","rows"}
    """
    for url in TVBOX_REMOTE_URLS:
        print(f"本地缺稳定源，尝试远端产物：{url}")
        txt = fetch_text(url)
        if not txt:
            continue
        for g in parse_tvbox_groups(txt.splitlines()):
            if "稳定源" in g["name"] and g["rows"]:
                print(f"远端取到稳定源分组「{g['name']}」：{len(g['rows'])} 个频道")
                return g
        print(f"   该地址里没有稳定源分组")
    return None


def tvbox_should_keep(group_name):
    """
    白名单判断：先把空格和各种间隔点去掉再比前缀，
    这样「稳定源·阿里云服2」「稳定源 阿里云服2」「稳定源-阿里云服2」都能命中；
    而「央卫·央视频道」去掉分隔符后是「央卫央视频道」，不会误判成央视频。
    """
    flat = re.sub(r"[\s·・•.．_\-]+", "", group_name)
    return any(flat.startswith(re.sub(r"[\s·・•.．_\-]+", "", k)) for k in TVBOX_KEEP_GROUPS)


def save_stable_cache(rows):
    """把本次拿到的稳定源分组存一份，供上游不下发时兜底"""
    try:
        with open(STABLE_CACHE, "w", encoding="utf-8", newline="\n") as f:
            f.write(f"{TVBOX_RENAME['稳定源']},#genre#\n" + "\n".join(rows) + "\n")
        print(f"稳定源已缓存：{STABLE_CACHE}（{len(rows)} 个频道）")
    except Exception as e:
        print(f"⚠️ 稳定源缓存写入失败：{e}")


def load_stable_cache():
    """读缓存，返回频道行（不含分组头），没有则返回 None"""
    lines = read_lines(STABLE_CACHE)
    if not lines:
        return None
    rows = [l.strip() for l in lines if l.strip() and not l.strip().endswith(",#genre#")]
    return rows or None


def check_tvbox_groups(file_path):
    """--check 诊断：把 live_tvbox.txt 里的分组名、行数、字符码点全打出来"""
    lines = read_lines(file_path)
    if lines is None:
        print(f"⚠️ 读不到 {file_path}")
        return
    print(f"诊断 {file_path}：共 {len(lines)} 行")

    groups, cur = [], None
    for line in lines:
        s = line.strip()
        if not s:
            continue
        if s.endswith(",#genre#"):
            cur = {"name": s[: -len(",#genre#")], "rows": []}
            groups.append(cur)
            continue
        if cur is not None:
            cur["rows"].append(s)

    for g in groups:
        keep = tvbox_should_keep(g["name"])
        mark = "保留" if keep else "跳过"
        print(f"  [{mark}] {g['name']!r}  {len(g['rows'])} 个频道")

    if not any("稳定源" in g["name"] for g in groups):
        print("  ⚠️ 整个文件里没有含「稳定源」字样的分组")
        for raw in lines:
            if "稳定" in raw or "阿里云" in raw:
                print(f"     疑似相关行：{raw.strip()!r}")
                break


def tvbox_out_group_name(name):
    """上游分组名 → 输出分组名（稳定源带版本号时统一改写）"""
    for kw, fixed in TVBOX_RENAME.items():
        if kw in name:
            return fixed
    return name


def extract_cctv_migu(file_path):
    """
    live_tvbox.txt：从白名单分组里取 3 组，稳定源优先
    —— 先把所有分组切成块，再按「稳定源· 在前，央视频· 在后」的顺序挑，
       这样上游把稳定源排到第 4、第 5 位时也不会被 3 组上限挤掉。
    白名单外的分组（咪咕·* / 央卫·* / 国内·* / 各地组播）一律跳过。
    """
    lines = read_lines(file_path)
    if lines is None:
        print(f"⚠️ 文件 {file_path} 不存在，跳过前三分组")
        return []

    # 1. 切成 [{name, rows}]
    groups = parse_tvbox_groups(lines)

    # 2. 筛白名单
    hits = [g for g in groups if tvbox_should_keep(g["name"])]
    if not hits:
        print(f"⚠️ {file_path} 里没有白名单分组（{'、'.join(TVBOX_KEEP_GROUPS)}），跳过")
        print(f"   文件现有分组：{'、'.join(g['name'] for g in groups[:12])}")
        return []

    # 3. 稳定源优先，其余按原顺序补足 3 组（改名后去重，防止两个稳定源组撞名）
    primary = [g for g in hits if "稳定源" in g["name"]]
    others = [g for g in hits if "稳定源" not in g["name"]]
    chosen, chosen_names = [], set()
    for g in primary + others:
        out_name = tvbox_out_group_name(g["name"])
        if out_name in chosen_names:
            continue
        chosen_names.add(out_name)
        chosen.append((g, out_name))
        if len(chosen) == 3:
            break

    # 3.1 本地没有稳定源 → 先试 GitHub 远端产物，再试本地缓存
    if not primary and TVBOX_REMOTE_URLS:
        remote = fetch_stable_group_from_remote()
        if remote:
            primary = [remote]
            chosen.insert(0, (remote, tvbox_out_group_name(remote["name"])))

    if not primary:
        cache_rows = load_stable_cache()
        if cache_rows:
            chosen.insert(0, ({"name": TVBOX_RENAME["稳定源"], "rows": cache_rows}, TVBOX_RENAME["稳定源"]))
            print(f"⚠️ {file_path} 里本次没有「稳定源·…」分组（上游被墙/未下发），"
                  f"已用本地缓存 {STABLE_CACHE} 兜底（{len(cache_rows)} 个频道，可能不是最新）")
        else:
            print(f"⚠️ {file_path} 里本次没有「稳定源·…」分组，又拿不到远端产物、也没有缓存，"
                  f"已用 {'、'.join(n for _g, n in chosen)} 顶上")
            print(f"   解决办法：把 GitHub 仓库里 live_tvbox_gw.txt 的 raw 地址填进 TVBOX_REMOTE_URLS")
    else:
        # 拿到了就刷新缓存，供下次抽风时用
        save_stable_cache(primary[0]["rows"])

    # 4. 拼输出（分组名按 TVBOX_RENAME 统一改写）
    out = []
    for g, out_name in chosen:
        if out_name != g["name"]:
            print(f"分组改名：{g['name']} → {out_name}")
        out.append(f"{out_name},#genre#")
        out.extend(g["rows"])

    skipped = [g["name"] for g in groups if g not in [c[0] for c in chosen]]
    print(f"{file_path} 提取 {len(chosen)} 个分组：{'、'.join(n for _g, n in chosen)}，"
          f"行数：{len(out)}")
    if skipped:
        print(f"   跳过分组：{'、'.join(skipped)}")
    return out


def extract_shanghai(file_path):
    """shiptv.txt：提取【上海频道】整个分组（含分组头）"""
    lines = read_lines(file_path)
    if lines is None:
        print(f"⚠️ 文件 {file_path} 不存在，跳过上海频道分组")
        return []

    out = []
    in_group = False

    for line in lines:
        line_strip = line.strip()
        if not line_strip:
            continue
        if is_noise(line_strip):
            continue

        if line_strip == "上海频道,#genre#":
            in_group = True
            out.append(line_strip)
            continue
        if line_strip.endswith(",#genre#") and in_group:
            in_group = False
            continue
        if in_group:
            out.append(line_strip)

    print(f"{file_path} 提取【上海频道】分组行数：{len(out)}")
    return out


def extract_gaoqing_cctv():
    """
    远端贵州电信组播源：删掉 CCTV-1 以上的贵州地方频道，
    只留 CCTV-1 起的央视+卫视部分，分组改名「高清央视卫视」
    先抓远端，抓不到就用本地缓存 GZ_CACHE
    """
    text = fetch_text(GZ_URL)

    if text is not None:
        lines = text.splitlines()
        # 抓到就顺手写一份本地缓存，下次断网/限流也能用
        try:
            with open(GZ_CACHE, "w", encoding="utf-8", newline="\n") as f:
                f.write("\n".join(lines) + "\n")
        except Exception as e:
            print(f"⚠️ 写本地缓存失败：{e}")
        source = "远端"
    else:
        lines = read_lines(GZ_CACHE)
        if lines is None:
            print(f"⚠️ 远端抓取失败且无本地缓存 {GZ_CACHE}，跳过{GZ_GROUP_NAME}分组")
            return []
        source = "本地缓存"

    out = []
    started = False
    for line in lines:
        line_strip = line.strip()
        if not line_strip or is_noise(line_strip):
            continue
        if line_strip.endswith(",#genre#"):
            continue          # 原分组头丢弃，后面统一换成新分组名
        if not started:
            if CCTV1_RE.match(line_strip):
                started = True
            else:
                continue      # CCTV-1 以上的地方频道，全部不要
        out.append(line_strip)

    if not out:
        print(f"⚠️ {source}源里没找到 CCTV-1，跳过{GZ_GROUP_NAME}分组")
        return []

    print(f"贵州电信源（{source}）提取行数：{len(out)} → 分组改名「{GZ_GROUP_NAME}」")
    return [f"{GZ_GROUP_NAME},#genre#"] + out


def ch_key(name):
    """
    频道名归一化，用于跨组匹配：
      「CCTV-1 综合」「CCTV1」「CCTV-1综合」 → CCTV1
      「CCTV5+ 体育赛事」「CCTV5+」          → CCTV5+
      「湖南卫视」「湖南卫视高清」            → 湖南卫视
    不在 CCTV_REST_OK 里的（CCTV4欧洲/美洲）保持原样，不会被误合并。
    """
    s = name.strip().upper()
    s = re.sub(r"[\s\-·_]+", "", s)
    for sfx in ("高清", "超清", "蓝光"):
        if s.endswith(sfx):
            s = s[: -len(sfx)]
            break
    m = re.match(r"^CCTV(\d{1,2})(\+)?(.*)$", s)
    if m:
        num, plus, rest = m.group(1), m.group(2), m.group(3)
        if rest in CCTV_REST_OK:
            return "CCTV%d%s" % (int(num), "+" if plus else "")
        return "RAW:" + s
    return s


def collect_match_pool(file_path):
    """从 live_tvbox.txt 的 4 个地方组播组里收集 {频道key: [(名称, url), ...]}"""
    lines = read_lines(file_path)
    if lines is None:
        print(f"⚠️ 文件 {file_path} 不存在，跳过跨组匹配")
        return {}

    pool = {}
    cur = None
    for line in lines:
        s = line.strip()
        if not s or is_noise(s):
            continue
        if s.endswith(",#genre#"):
            cur = s[: -len(",#genre#")]
            continue
        if not cur or not any(cur.startswith(g) for g in MATCH_SOURCE_GROUPS):
            continue
        if "," not in s:
            continue
        name, url = s.split(",", 1)
        url = url.strip()
        if not url.lower().startswith("http"):
            continue
        pool.setdefault(ch_key(name), []).append((name.strip(), url))

    # 同一频道下重复 URL 去重（河南电信这类组里同一节目常有两个落地 IP）
    uniq_pool = {}
    for k, items in pool.items():
        seen, uniq = set(), []
        for name, url in items:
            if url in seen:
                continue
            seen.add(url)
            uniq.append((name, url))
        uniq_pool[k] = uniq

    total = sum(len(v) for v in uniq_pool.values())
    print(f"{file_path} 地方组播池：{len(uniq_pool)} 个频道 / {total} 条源"
          f"（来源：{'、'.join(MATCH_SOURCE_GROUPS)}）")
    return uniq_pool


SPEED_RETRY = 2            # 每条源最多测几次，取最快的一次（抖动大的源不至于被误杀）
SPEED_PROBE_BYTES = 2048   # 实际读多少字节，用于判断“能不能播”
# 返回这些开头的不是流，是网页/错误页 → 当死源
SPEED_BAD_BODY = (b"<!doctype", b"<html", b"<?xml", b"<head", b"<body", b"<error", b"not found")
# 每条线路可选的独立代理（有联通代理时，一次跑完两条线）：SPEED_PROXY_DX / SPEED_PROXY_LT
SPEED_PROXY = {"dx": os.environ.get("SPEED_PROXY_DX", ""),
               "lt": os.environ.get("SPEED_PROXY_LT", "")}
_CURRENT_PROXY = None      # 由 main 按 --net 设置


def _probe_once(url, timeout, proxy):
    """测一次：返回 (耗时, 是否像真流)；连不上返回 (None, False)"""
    if proxy:
        handlers = [urllib.request.ProxyHandler({"http": proxy, "https": proxy})]
    else:
        handlers = [urllib.request.ProxyHandler({})]
    opener = urllib.request.build_opener(*handlers)
    req = urllib.request.Request(url, headers={
        "User-Agent": SPEED_UA,
        "Accept": "*/*",
        "Range": f"bytes=0-{SPEED_PROBE_BYTES - 1}",
    })
    t0 = time.time()
    try:
        with opener.open(req, timeout=timeout) as r:
            ttfb = time.time() - t0
            head = r.read(SPEED_PROBE_BYTES)
            ctype = (r.headers.get("Content-Type") or "").lower()
    except Exception:
        return None, False

    if head[:1] == b"\x1f\x8b":                 # gzip 压缩的肯定是网页
        return ttfb, False
    if "text/html" in ctype:
        return ttfb, False
    low = head[:64].strip().lower()
    if any(low.startswith(m) for m in SPEED_BAD_BODY):
        return ttfb, False
    if not head:                                # 200 但一个字节都没有
        return ttfb, False
    return ttfb, True


def probe_speed(url, timeout=SPEED_TIMEOUT):
    """
    判断一条源“能不能播”并给出耗时：
      首字节到达 + 前 2KB 确实是流数据（不是网页/错误页）才算能播
      最多测 SPEED_RETRY 次，取最快的一次
      能播返回耗时（秒），不能播返回 None
    """
    best = None
    for _ in range(max(1, SPEED_RETRY)):
        ttfb, ok = _probe_once(url, timeout, _CURRENT_PROXY)
        if not ok:
            continue
        best = ttfb if best is None else min(best, ttfb)
        if best <= 0.5:            # 已经很快，不用再测
            break
    return best


def _host_of(url):
    try:
        return (urllib.parse.urlparse(url).hostname or url).lower()
    except Exception:
        return url


def probe_all(urls):
    """
    并发测速，返回 {url: 秒数或 None}
    按主机分组限流：同一主机最多 SPEED_PER_HOST 条同时在测，
    避免几十条源打向同一个 IP:端口时对方限流导致集体超时误判。
    """
    result = {}
    if not urls:
        return result

    by_host = {}
    for u in urls:
        by_host.setdefault(_host_of(u), []).append(u)

    def _one_host(host_urls):
        out = {}
        with ThreadPoolExecutor(max_workers=min(SPEED_PER_HOST, len(host_urls))) as ex:
            for u, cost in zip(host_urls, ex.map(probe_speed, host_urls)):
                out[u] = cost
        return out

    with ThreadPoolExecutor(max_workers=SPEED_HOST_CONCURRENCY) as ex:
        for part in ex.map(_one_host, list(by_host.values())):
            result.update(part)
    return result


def save_speed_report(tag, speeds):
    """
    把本次测速结果合并进 speed_reports/<tag>.json
    —— 一次运行里会有两轮测速（央卫跨组匹配、港澳台并入），这里必须累加，
       直接覆盖会导致前一轮的结果丢失，双线路合并时误判成死源。
    """
    if not tag:
        return
    try:
        os.makedirs(SPEED_REPORT_DIR, exist_ok=True)
        path = os.path.join(SPEED_REPORT_DIR, f"{tag}.json")
        merged = {}
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    merged = json.load(f).get("urls", {}) or {}
            except Exception:
                merged = {}
        merged.update(speeds)
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"tag": tag, "time": time.strftime("%Y-%m-%d %H:%M:%S"),
                       "urls": merged}, f, ensure_ascii=False)
        print(f"测速报告已合并保存：{path}（线路：{SPEED_NET_TAGS.get(tag, tag)}，"
              f"累计 {len(merged)} 条）")
    except Exception as e:
        print(f"⚠️ 测速报告保存失败：{e}")


def load_speed_reports():
    """读取 speed_reports/*.json，返回 {tag: {url: 秒数或 None}}"""
    reports = {}
    if not os.path.isdir(SPEED_REPORT_DIR):
        return reports
    for fn in sorted(os.listdir(SPEED_REPORT_DIR)):
        if not fn.endswith(".json"):
            continue
        tag = fn[:-5]
        try:
            with open(os.path.join(SPEED_REPORT_DIR, fn), "r", encoding="utf-8") as f:
                reports[tag] = json.load(f).get("urls", {})
        except Exception as e:
            print(f"⚠️ 测速报告 {fn} 读取失败：{e}")
    return reports


def merged_speed_of(url, reports, current_tag):
    """
    合并多条线路的测速结论：
      任一条线路能通 → 保留，取最快的那条耗时作为排序依据
      所有测过的线路都不通 → None（剔除）
      没测过的 → 很大值（保留但排后面）
    """
    vals = []
    for tag, data in reports.items():
        if url in data:
            vals.append((tag, data[url]))
    if not vals:
        return float("inf")
    alive = [v for _t, v in vals if v is not None]
    if not alive:
        return None
    best = min(alive)
    if current_tag:
        cur = [v for t, v in vals if t == current_tag and v is not None]
        if cur:
            best = min(best, cur[0] * 0.95)   # 当前线路的源略微优先，避免每次都挑到另一条线的最佳
    return best


def match_and_speed_sort(lines, current_tag=None):
    """
    把 live_tvbox 地方组播组里的源，按频道名匹配进「央视频道」「卫视频道」两组，
    保持原有的频道顺序，只把每个频道自己的多条源按测速结果重排（快的在前）。
    测不通的源直接剔除；电信/联通两条线路任一能通即保留。
    """
    pool = collect_match_pool(TVBOX_FILE)
    if not pool:
        return lines

    # 1. 定位目标分组的行区间 [头行, 下一组头行)
    ranges, start = [], None
    for i, l in enumerate(lines):
        s = l.strip()
        if not s.endswith(",#genre#"):
            continue
        if start is not None:
            ranges.append((start, i))
            start = None
        if s[: -len(",#genre#")] in MATCH_TARGET_GROUPS:
            start = i
    if start is not None:
        ranges.append((start, len(lines)))

    if not ranges:
        print("⚠️ live.txt 里没有「央视频道 / 卫视频道」分组，跳过跨组匹配与测速")
        return lines

    # 2. 逐频道组装备选源
    plans = {}          # 行号 -> 该频道排好序后的多条源
    urls_to_probe = set()
    hit_channels = 0
    hit_sources = 0
    for gs, ge in ranges:
        for i in range(gs + 1, ge):
            s = lines[i].strip()
            if "," not in s:
                continue
            name, url = s.split(",", 1)
            name, url = name.strip(), url.strip()
            if not url.lower().startswith("http"):
                continue

            cands = [(name, url)]
            extra = pool.get(ch_key(name), [])
            if extra:
                hit_channels += 1
                hit_sources += len(extra)
                cands.extend(extra)

            seen, uniq = set(), []
            for _n, u in cands:
                if u in seen:
                    continue
                seen.add(u)
                uniq.append((_n, u))
            plans[i] = uniq
            urls_to_probe.update(u for _n, u in uniq)

    if not plans:
        print("⚠️ 目标分组里没有可测速的频道行，跳过")
        return lines

    # 3. 并发测速（本次线路）
    print(f"测速中：{len(urls_to_probe)} 条源，超时 {SPEED_TIMEOUT}s，并发 {SPEED_WORKERS} ...")
    t0 = time.time()
    speeds = probe_all(sorted(urls_to_probe))
    ok = sum(1 for v in speeds.values() if v is not None)
    fail = len(speeds) - ok
    print(f"测速完成：可用 {ok} 条 / 失败 {fail} 条，耗时 {time.time() - t0:.1f}s")
    save_speed_report(current_tag, speeds)

    # 3.1 合并电信/联通多条线路的测速结论
    reports = load_speed_reports()
    if current_tag:
        reports[current_tag] = speeds
    if len(reports) > 1:
        tags = "、".join(SPEED_NET_TAGS.get(t, t) for t in reports)
        print(f"双线路合并：已载入 {tags} 共 {len(reports)} 份测速结果")
    else:
        only = SPEED_NET_TAGS.get(next(iter(reports), ""), "未知")
        print(f"⚠️ 目前只有【{only}】一份测速结果，只覆盖单条线路："
              f"仅在另一条线路可用的源会被当作不通剔除。")
        print(f"   要真正兼顾上海电信 + 上海联通，请在另一条宽带下再跑一次 "
              f"（--net {'lt' if only == '电信' else 'dx'}），结果会自动合并。")

    # 4. 每个频道内部按速度排序：两条线路都不通的源剔除，快的在前
    all_dead_channels = []
    dropped_dead = 0
    only_dx = only_lt = both = 0

    for i, cands in plans.items():
        name = lines[i].split(",", 1)[0].strip()

        scored, dead = [], []
        for c in cands:
            v = merged_speed_of(c[1], reports, current_tag) if len(reports) > 1 \
                else (speeds.get(c[1]) if speeds.get(c[1]) is not None else None)
            if v is None:
                dead.append(c)
            else:
                scored.append((c, v))
                if len(reports) > 1:
                    dx = reports.get("dx", {}).get(c[1])
                    lt = reports.get("lt", {}).get(c[1])
                    if dx is not None and lt is not None:
                        both += 1
                    elif dx is not None:
                        only_dx += 1
                    elif lt is not None:
                        only_lt += 1

        dropped_dead += len(dead)
        if not scored:
            # 全线都不通：默认把频道标题也删掉；SPEED_DROP_DEAD_CHANNEL=False 时才保留原源一条
            all_dead_channels.append(name)
            if SPEED_DROP_DEAD_CHANNEL:
                plans[i] = []                      # 空列表 = 整行删除
                continue
            if SPEED_DROP_DEAD:
                scored = [(cands[0], float("inf"))]
                dropped_dead -= 1
            else:
                scored = [(c, float("inf")) for c in cands]

        scored.sort(key=lambda cv: cv[1])
        plans[i] = [f"{name},{u}" for (c, _v) in scored for u in [c[1]]]

    # 5. 回填，频道顺序不动，只替换每个频道自己的行
    out, i = [], 0
    while i < len(lines):
        if i in plans:
            out.extend(plans[i])
            i += 1
        else:
            out.append(lines[i])
            i += 1

    print(f"跨组匹配：{hit_channels} 个频道命中 {hit_sources} 条地方组播源，已按速度重排")
    if len(reports) > 1:
        print(f"双线路覆盖：双通 {both} 条 / 仅电信 {only_dx} 条 / 仅联通 {only_lt} 条（都保留）")
    if SPEED_DROP_DEAD:
        print(f"剔除无响应源：{dropped_dead} 条")
    if all_dead_channels:
        how = "已整条删除（标题+源）" if SPEED_DROP_DEAD_CHANNEL else "已保留原标题源一条"
        print(f"以下 {len(all_dead_channels)} 个频道所有源都无响应，{how}："
              f"{'、'.join(all_dead_channels)}")
    return out


def hk_key(name):
    """
    港澳台频道名归一化（在 ch_key 基础上再放宽）：
      「翡翠台4K(字幕)」「翡翠台4K（字幕）」「翡翠台HD」 → 翡翠台
      「鳳凰中文」「凤凰中文」保持各自（不做繁简转换）
    """
    s = ch_key(name)
    s = re.sub(r"\s*[（(][^）)]*[）)]\s*$", "", s)     # 去掉末尾括号注释
    s = re.sub(r"(?i)(4K|8K|HD|FHD|高清|超清|蓝光)$", "", s)
    return s


def collect_hk_pool(file_path):
    """从 live_hongkong.txt 的指定分组里取源，返回 {归一化频道名: [(原名, url), ...]}"""
    lines = read_lines(file_path)
    if lines is None:
        return {}
    pool = {}
    for g in parse_tvbox_groups(lines):
        if g["name"] not in HK_MERGE_GROUPS:
            continue
        for row in g["rows"]:
            if "," not in row:
                continue
            name, url = row.split(",", 1)
            name, url = name.strip(), url.strip()
            if not name or not url.lower().startswith("http"):
                continue
            pool.setdefault(hk_key(name), []).append((name, url))
    return pool


def score_of(url, speeds, reports, current_tag):
    """
    单条源的综合耗时：
      多线路 → 交给 merged_speed_of 合并
      单线路 → 测过且失败返回 None（死源）；测过成功返回耗时；没测过返回 inf（保留但排后面）
    """
    if len(reports) > 1:
        return merged_speed_of(url, reports, current_tag)
    if url in speeds:
        v = speeds[url]
        return v if v is not None else None
    return float("inf")


def check_hk():
    """
    诊断用：--hk-check
    逐个分组打印港澳台源的存活情况，用来看清「频道没并进来」到底是上游源死了，还是脚本没匹配上。
    """
    lines = read_lines(HK_FILE)
    if lines is None:
        print(f"⚠️ 找不到 {HK_FILE}，先在本地生成一份（hongkong_gen.py 或 update.py --hk）")
        return
    groups = {g["name"]: g for g in parse_tvbox_groups(lines)}

    for gname in HK_MERGE_GROUPS:
        g = groups.get(gname)
        if not g:
            # 分组名对不上时，列出文件里真实的分组名，方便改配置
            near = [n for n in groups if any(k in n for k in ("台湾", "台灣", "港澳", "港台"))]
            print(f"❌ 没有「{gname}」分组；文件里相近的分组：{'、'.join(near) if near else '无'}")
            continue

        chans = {}
        for row in g["rows"]:
            if "," not in row:
                continue
            n, u = row.split(",", 1)
            n, u = n.strip(), u.strip()
            if u.lower().startswith("http"):
                chans.setdefault(n, []).append(u)

        urls = sorted({u for v in chans.values() for u in v})
        print(f"\n[{gname}] {len(chans)} 个频道 / {len(urls)} 条源，测速中…")
        sp = probe_all(urls)
        alive = {u for u, v in sp.items() if v is not None}
        dead_chan = [n for n, us in chans.items() if not any(u in alive for u in us)]
        ok = sum(1 for u in urls if u in alive)
        print(f"  源存活 {ok} / {len(urls)}；频道有可用源 {len(chans) - len(dead_chan)} / {len(chans)}")
        if dead_chan:
            print(f"  全死频道（{len(dead_chan)} 个，会被整条丢弃）：{'、'.join(dead_chan)}")
        # 抽样看几条死源，判断是 404 网页还是连不上
        dead_urls = [u for u in urls if u not in alive][:3]
        for u in dead_urls:
            print(f"    死源示例：{u}")


def merge_hk_into_news(lines, current_tag=None):
    """
    把 live_hongkong.txt 的「台湾·四季台湾」「繁体·🔮港澳台直播」并入 live.txt 的「新闻频道」：
      · 不测速、不筛源，所有源原样保留
      · 同名频道（按归一化名）归到同一行，新源接在原有源后面
      · 顺序：原有频道保持原顺序 → 台湾频道 → 港澳频道（HK_MERGE_GROUPS 的顺序即优先级）
    """
    src = read_lines(HK_FILE)
    if src is None:
        print(f"⚠️ 没读到港澳台源（{HK_FILE} 不存在），跳过并入")
        return lines

    groups = {g["name"]: g for g in parse_tvbox_groups(src)}

    # 1. 按组优先级收集：同 key 的频道合并源，记录它属于台湾(rank 0) 还是港澳(rank 1)
    pool, order = {}, []
    for rank, gname in enumerate(HK_MERGE_GROUPS):
        g = groups.get(gname)
        if not g:
            near = [n for n in groups if any(k in n for k in ("台湾", "台灣", "港澳", "港台"))]
            print(f"⚠️ {HK_FILE} 里没有「{gname}」分组"
                  + (f"，相近的有：{'、'.join(near)}" if near else "")
                  + "，跳过该组")
            continue
        for row in g["rows"]:
            if "," not in row:
                continue
            name, url = row.split(",", 1)
            name, url = name.strip(), url.strip()
            if not name or not url.lower().startswith("http"):
                continue
            key = hk_key(name)
            if not key:
                continue
            ent = pool.get(key)
            if ent is None:
                ent = {"name": name, "urls": [], "rank": rank}
                pool[key] = ent
                order.append(key)
            if url not in ent["urls"]:
                ent["urls"].append(url)

    if not pool:
        print(f"⚠️ 没读到港澳台源（{HK_FILE} 缺失或分组名对不上），跳过并入")
        return lines

    taiwan = [k for k in order if pool[k]["rank"] == 0]
    hk = [k for k in order if pool[k]["rank"] == 1]
    print(f"港澳台源：{len(pool)} 个频道 / {sum(len(v['urls']) for v in pool.values())} 条源"
          f"（台湾 {len(taiwan)} 个、港澳 {len(hk)} 个）")

    # 2. 定位目标分组
    gs = None
    for i, l in enumerate(lines):
        s = l.strip()
        if s.endswith(",#genre#") and s[: -len(",#genre#")].strip() == HK_TARGET_GROUP:
            gs = i
            break
    if gs is None:
        print(f"⚠️ live.txt 里没有「{HK_TARGET_GROUP}」分组，已在末尾新建该组")
        lines = list(lines) + [f"{HK_TARGET_GROUP},#genre#"]
        gs = len(lines) - 1

    ge = gs + 1
    while ge < len(lines) and not lines[ge].strip().endswith(",#genre#"):
        ge += 1

    # 3. 组内原有频道（顺序原样保留）
    rows = []
    for i in range(gs + 1, ge):
        s = lines[i].strip()
        if not s or "," not in s:
            continue
        name, url = s.split(",", 1)
        name, url = name.strip(), url.strip()
        if url.lower().startswith("http"):
            rows.append([name, [url]])

    # 4. 同名归并：港台源接到同 key 的原有频道后面
    hit_channels = hit_sources = 0
    used = set()
    for row in rows:
        key = hk_key(row[0])
        ent = pool.get(key)
        if not ent or key in used:
            continue
        used.add(key)
        added = 0
        for u in ent["urls"]:
            if u not in row[1]:
                row[1].append(u)
                added += 1
        if added:
            hit_channels += 1
            hit_sources += added

    # 5. 新频道：台湾在前，港澳在后（各自按文件里的原始顺序）
    new_blocks = []
    for k in taiwan + hk:
        if k in used:
            continue
        used.add(k)
        new_blocks.append([pool[k]["name"], pool[k]["urls"]])

    out_existing = [f"{n},{u}" for n, us in rows for u in us]
    out_new = [f"{n},{u}" for n, us in new_blocks for u in us]

    # 6. 回填
    lines = lines[:gs] + [f"{HK_TARGET_GROUP},#genre#"] + out_existing + out_new + lines[ge:]

    print(f"港澳台并入「{HK_TARGET_GROUP}」：同名频道 {hit_channels} 个（并入 {hit_sources} 条源），"
          f"新增频道 {len(new_blocks)} 个（台湾 {len([b for b in new_blocks if hk_key(b[0]) in taiwan])} 个、"
          f"港澳 {len([b for b in new_blocks if hk_key(b[0]) in hk])} 个），未测速、未筛源")
    return lines


def apply_group_rename(lines):
    """
    最后一步：把分组头的名字换掉（组内频道与顺序都不变）。
    换名只影响 live.txt 的显示，不影响前面按原组名做的匹配。
    """
    out, renamed = [], []
    for line in lines:
        s = line.strip()
        if s.endswith(",#genre#"):
            name = s[: -len(",#genre#")].strip()
            new = GROUP_RENAME_OUT.get(name)
            if new:
                out.append(f"{new},#genre#")
                renamed.append(f"{name} → {new}")
                continue
        out.append(line)
    if renamed:
        print("分组改名：" + "、".join(renamed))
    return out


def apply_group_ua(lines):
    """
    给 UA_GROUPS 里指定的分组强制 User-Agent：
      pipe 模式：该组每行改成「名称,url|User-Agent=...」
      m3u  模式：live.txt 原样，另生成带 #EXTVLCOPT 的 m3u
    返回 (处理后的 lines, m3u 文本或 None)
    """
    if UA_MODE == "off" or not UA_GROUPS:
        return lines, None

    out = []
    m3u = ["#EXTM3U"]
    cur = None
    for line in lines:
        s = line.strip()
        if not s:
            continue
        if s.endswith(",#genre#"):
            cur = s[: -len(",#genre#")]
            out.append(s)          # 分组头在两种模式下都保留
            continue

        has_url = "," in s and s.split(",", 1)[1].strip().lower().startswith("http")
        if cur in UA_GROUPS and has_url:
            name, url = s.split(",", 1)
            ua = UA_GROUPS[cur]
            if UA_MODE == "pipe":
                out.append(f"{name.strip()},{url.rstrip()}|User-Agent={ua}")
            elif UA_MODE == "proxy":
                enc = urllib.parse.quote(url.strip(), safe="")
                out.append(f"{name.strip()},{UA_PROXY_BASE}/p?u={enc}")
            else:
                out.append(s)      # m3u 模式：live.txt 保持原样
                m3u.append(f'#EXTINF:-1 group-title="{cur}",{name.strip()}')
                m3u.append(f"#EXTVLCOPT:http-user-agent={ua}")
                m3u.append(url.rstrip())
            continue

        out.append(s)

    if UA_MODE == "m3u":
        return out, "\n".join(m3u) + "\n" if len(m3u) > 1 else None
    return out, None


def parse_args(argv):
    """解析命令行：--no-speed 跳过测速；--net dx|lt 指定本次运行所在线路"""
    no_speed = "--no-speed" in argv
    net = None
    for i, a in enumerate(argv):
        if a == "--net" and i + 1 < len(argv):
            net = argv[i + 1]
        elif a.startswith("--net="):
            net = a.split("=", 1)[1].strip()
    if net and net not in SPEED_NET_TAGS:
        print(f"⚠️ 未知线路 --net {net}，可选：{'、'.join(SPEED_NET_TAGS)}，已忽略")
        net = None
    return no_speed, net


def main():
    no_speed, net = parse_args(sys.argv[1:])
    if "--check" in sys.argv[1:]:
        check_tvbox_groups(TVBOX_FILE)
        return
    if "--hk-check" in sys.argv[1:]:
        check_hk()
        return
    part1 = filter_all_lines(IPTV_FILE)
    orient_block, other_block = extract_oriental_and_4k(IPASD_FILE)
    part_sh = extract_shanghai(SHIPTV_FILE)
    part_gq = extract_gaoqing_cctv()
    part4 = extract_cctv_migu(TVBOX_FILE)     # ← 原来误写成未定义的 ZHIBO_FILE
    part3 = filter_zb(ZB_FILE)

    # iptv.txt 里由「#类型：…」转换出的「东方有线,#genre#」与 iptasd.txt 的东方有线分组重名，
    # TVBox 会显示成两个同名分组。这里去掉后者多余的分组头，让它并进第一个东方有线分组。
    if orient_block and orient_block[0] == "东方有线,#genre#" and "东方有线,#genre#" in part1:
        orient_block = orient_block[1:]

    # ✅ 顺序：iptv → 东方有线 → 上海频道 → 4K频道+轮播剧场 → 高清央视卫视 → 前三个分组 → ZB.TXT
    final = part1 + orient_block + part_sh + other_block + part_gq + part4 + part3

    # 跨组匹配 + 测速排序（--no-speed 可跳过，快速调试用）
    if no_speed:
        print("⏩ 已跳过跨组匹配与测速（--no-speed）")
    else:
        if net:
            px = SPEED_PROXY.get(net)
            print(f"本次线路：{SPEED_NET_TAGS[net]}（测速结果将存入 "
                  f"{SPEED_REPORT_DIR}/{net}.json，并与另一条线路的结果合并）"
                  + (f"，走代理 {px}" if px else "，直连"))
            globals()["_CURRENT_PROXY"] = px or None
        final = match_and_speed_sort(final, net)

    # 港澳台源并入「新闻频道」（纯归并、不测速，--no-speed 时也执行）
    final = merge_hk_into_news(final, net)

    # 指定分组强制 User-Agent（上海频道的源只认 AppleCoreMedia）
    final, m3u_text = apply_group_ua(final)
    if m3u_text:
        with open(UA_M3U_FILE, "w", encoding="utf-8", newline="\n") as f:
            f.write(m3u_text)
        print(f"已生成带 UA 的播放列表：{UA_M3U_FILE}")
    elif UA_MODE == "proxy" and UA_GROUPS:
        print(f"已把以下分组改写成 UA 中转地址：「{'、'.join(UA_GROUPS)}」 → {UA_PROXY_BASE}")
        print(f"   记得先在这台机器上跑：python3 shanghai_ua_proxy.py，且 UA_PROXY_BASE 要是局域网可访问的 IP")
    elif UA_MODE == "pipe" and UA_GROUPS:
        print(f"⚠️ pipe 模式已启用（多数 TVBox 不认 |User-Agent=，播不了就改 UA_MODE = \"proxy\"）")

    # 输出前把「央视频道 / 卫视频道」改成「备用·央视频道 / 备用·卫视频道」
    final = apply_group_rename(final)

    with open(OUTPUT, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(final) + "\n")

    print(f"\n✅ 合并完成！总条数：{len(final)}")
    print(f"输出文件：{OUTPUT}")


if __name__ == "__main__":
    main()
