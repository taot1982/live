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
GZ_URL = ("https://raw.githubusercontent.com/q1017673817/iptvz/refs/heads/main/"
          "%E7%BB%84%E6%92%AD_%E8%B4%B5%E5%B7%9E%E7%94%B5%E4%BF%A1.txt")
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

# ========== 跨组匹配 + 测速排序 ==========
# 从 live_tvbox.txt 这 4 个地方组播组里取源，匹配进 live.txt 的下面 2 个分组
MATCH_SOURCE_GROUPS = ("山东电信", "河南电信", "重庆联通", "河北联通")
MATCH_TARGET_GROUPS = ("央视频道", "卫视频道")

SPEED_TIMEOUT = 4.0        # 单条源测速超时（秒）
SPEED_WORKERS = 32         # 并发线程数
SPEED_UA = "okhttp/6.0"
SPEED_DROP_DEAD = True     # True=剔除测速无响应的源（全组皆死时保留原源一条，避免频道消失）

# 兼顾电信/联通：两条线路各跑一次，测速结果存成 json，第二次会自动合并
# 用法：python3 merge_sources.py --net dx   （上海电信宽带下跑）
#       python3 merge_sources.py --net lt   （上海联通宽带下跑，会自动读上一步的 dx 结果）
SPEED_REPORT_DIR = "speed_reports"
SPEED_NET_TAGS = {"dx": "电信", "lt": "联通"}

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


def extract_cctv_migu(file_path):
    """
    live_tvbox.txt：只提取 TVBOX_KEEP_GROUPS 白名单里的分组，凑满 3 组为止
    白名单外的分组（咪咕·* / 央卫·* / 国内·* 等）一律跳过，且不占用「3 组」名额
    """
    lines = read_lines(file_path)
    if lines is None:
        print(f"⚠️ 文件 {file_path} 不存在，跳过前三分组")
        return []

    out = []
    in_group = False
    group_count = 0
    skipped = []

    for line in lines:
        line_strip = line.strip()
        if not line_strip:
            continue
        if is_noise(line_strip):
            continue

        if line_strip.endswith(",#genre#"):
            group_name = line_strip.replace(",#genre#", "").strip()

            # 不在白名单：整组跳过（组内频道也不要），不占名额
            if not any(group_name.startswith(k) for k in TVBOX_KEEP_GROUPS):
                in_group = False
                if group_name not in skipped:
                    skipped.append(group_name)
                continue

            if group_count < 3:
                group_count += 1
                in_group = True
                out.append(line_strip)
                continue
            break   # 白名单分组已收满 3 组，后面的不要

        if in_group:
            out.append(line_strip)

    print(f"{file_path} 提取 {group_count} 个分组，行数：{len(out)}"
          + (f"，跳过分组：{'、'.join(skipped)}" if skipped else ""))
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


def probe_speed(url, timeout=SPEED_TIMEOUT):
    """测一条源：返回响应头到达耗时（秒），失败返回 None。直连，不走系统代理"""
    try:
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        req = urllib.request.Request(url, headers={
            "User-Agent": SPEED_UA,
            "Accept": "*/*",
            "Range": "bytes=0-1023",
        })
        t0 = time.time()
        with opener.open(req, timeout=timeout) as r:
            ttfb = time.time() - t0
            try:
                r.read(1024)      # 只取一小口，之后直接断开
            except Exception:
                pass
        return ttfb
    except Exception:
        return None


def probe_all(urls):
    """并发测速，返回 {url: 秒数或 None}"""
    result = {}
    if not urls:
        return result
    with ThreadPoolExecutor(max_workers=SPEED_WORKERS) as ex:
        for url, cost in zip(urls, ex.map(probe_speed, urls)):
            result[url] = cost
    return result


def save_speed_report(tag, speeds):
    """把本次测速结果存成 speed_reports/<tag>.json，供另一条线路合并用"""
    if not tag:
        return
    try:
        os.makedirs(SPEED_REPORT_DIR, exist_ok=True)
        path = os.path.join(SPEED_REPORT_DIR, f"{tag}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"tag": tag, "time": time.strftime("%Y-%m-%d %H:%M:%S"),
                       "urls": speeds}, f, ensure_ascii=False)
        print(f"测速报告已保存：{path}（线路：{SPEED_NET_TAGS.get(tag, tag)}）")
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
            # 全线都不通：保留原标题源一条，否则这个频道会整个从分组里消失
            if SPEED_DROP_DEAD:
                scored = [(cands[0], float("inf"))]
                dropped_dead -= 1
                all_dead_channels.append(name)
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
        print(f"⚠️ 以下 {len(all_dead_channels)} 个频道所有源都无响应，已保留原标题源一条："
              f"{'、'.join(all_dead_channels)}")
    return out


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
            print(f"本次线路：{SPEED_NET_TAGS[net]}（测速结果将存入 "
                  f"{SPEED_REPORT_DIR}/{net}.json，并与另一条线路的结果合并）")
        final = match_and_speed_sort(final, net)

    with open(OUTPUT, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(final) + "\n")

    print(f"\n✅ 合并完成！总条数：{len(final)}")
    print(f"输出文件：{OUTPUT}")


if __name__ == "__main__":
    main()
