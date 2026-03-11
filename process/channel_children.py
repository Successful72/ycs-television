#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
从 m3u/txt 格式的 IPTV 订阅文件中提取少儿动漫频道，组装成新的 m3u 文件。
"""

import os
import re
import glob
from collections import defaultdict

# ── 输出频道顺序 ──────────────────────────────────────────────────────────────
CHANNEL_ORDER = [
    "CCTV-14",       # 中央少儿（全国覆盖，置顶）
    "金鹰卡通",       # 湖南卫星
    "嘉佳卡通",       # 广东卫星
    "哈哈炫动",       # 上海（含炫动卡通）
    "优漫卡通",       # 江苏
    "卡酷少儿",       # 北京
    "七彩少儿",       # 有线/IPTV
    "黑莓动画",       # NewTV
    "动漫秀场",       # SiTV·上海
    "爱动漫",         # iHOT
    "南方少儿",       # 广东有线
    "星空卫视",       # Star Chinese（含少儿节目）
]

GROUP_TITLE = "少儿动漫频道"

# ── 频道定义 ──────────────────────────────────────────────────────────────────
# 格式：(标准名, 正则表达式字符串, {别名集合})
# 说明：
#   - 别名集合用于 O(1) 精确匹配（优先）
#   - 正则用于模糊兜底（后备）
#   - 正则中不加 ^ 锚点，允许名称携带前缀/后缀（如 HD、高清、省份等）
_CHANNEL_DEFS_RAW = [

    # ── CCTV-14 少儿 ────────────────────────────────────────────────────────
    ("CCTV-14", r"(?i)CCTV[-\s_]*0?14(?![0-9Kk+])", {
        "CCTV14", "CCTV14 少儿", "CCTV-14少儿", "CCTV14[1920*1080]",
        "CCTV-14_ITV", "CCTV14「IPV6」", "CCTV14HD", "CCTV-14HD",
        "CCTV-14北联", "CCTV14-标清", "CCTV-14电信", "CCTV-14东联",
        "CCTV-14高码", "CCTV-14高清", "CCTV-14广西", "CCTV-14梅州",
        "CCTV-14咪咕", "CCTV-14汝阳", "CCTV-14山东", "CCTV-14上海",
        "CCTV14-少儿", "CCTV-14斯特", "CCTV-14四川", "CCTV-14太原",
        "CCTV-14天津", "CCTV-14影视", "CCTV-14浙江", "CCTV-14重庆",
        "CCTV14少儿", "CCTV少儿", "CCTV-少儿",
    }),

    # ── 金鹰卡通（湖南广播电视台卫星频道） ──────────────────────────────────
    ("金鹰卡通", r"(?i)金鹰[\s_-]*卡通|金鹰[\s_-]*少儿", {
        "金鹰卡通", "湖南金鹰卡通", "金鹰卡通卫视", "湖南金鹰卡通卫视",
        "金鹰卡通HD", "金鹰卡通高清", "金鹰卡通-HD", "金鹰卡通频道",
        "金鹰卡通[1920*1080]", "金鹰卡通（高清）", "金鹰少儿",
        "金鹰卡通咪咕", "金鹰卡通标清",
    }),

    # ── 嘉佳卡通（广东广播电视台卫星频道） ──────────────────────────────────
    ("嘉佳卡通", r"(?i)嘉佳[\s_-]*卡通|广东[\s_-]*嘉佳", {
        "嘉佳卡通", "广东嘉佳卡通", "嘉佳卡通卫视", "广东嘉佳卡通卫视",
        "嘉佳卡通HD", "嘉佳卡通高清", "嘉佳卡通频道", "嘉佳卡通[1920*1080]",
        "嘉佳卡通（高清）", "嘉佳卡通-HD", "嘉佳卡通咪咕", "嘉佳卡通标清",
    }),

    # ── 哈哈炫动（上海文广，含"炫动卡通"旧称） ──────────────────────────────
    ("哈哈炫动", r"(?i)哈哈[\s_-]*炫动|炫动[\s_-]*(?:卡通|卫视|少儿)|上海[\s_-]*(?:哈哈|炫动)", {
        "哈哈炫动", "炫动卡通", "上海哈哈炫动", "哈哈炫动卫星频道",
        "炫动卡通频道", "哈哈炫动HD", "炫动卡通HD", "哈哈炫动高清",
        "炫动卡通高清", "哈哈炫动[1920*1080]", "哈哈炫动卫视",
        "炫动卡通-HD", "炫动卫视", "哈哈炫动-HD", "炫动少儿",
        "哈哈炫动咪咕", "炫动卡通咪咕", "炫动卡通标清",
    }),

    # ── 优漫卡通（江苏广电卫星频道） ─────────────────────────────────────────
    ("优漫卡通", r"(?i)优漫[\s_-]*(?:卡通|卫视)|江苏[\s_-]*优漫", {
        "优漫卡通", "江苏优漫卡通", "优漫卡通频道", "优漫卡通HD",
        "优漫卡通高清", "优漫卡通[1920*1080]", "优漫卡通-HD",
        "优漫卡通（高清）", "优漫卡通卫视", "优漫卡通咪咕", "优漫卡通标清",
    }),

    # ── 卡酷少儿（北京广播电视台） ──────────────────────────────────────────
    # kaku / KAKU 是其官方英文名，须用词边界防止误匹配
    ("卡酷少儿", r"(?i)卡酷|(?<![a-zA-Z])kaku(?![a-zA-Z])", {
        "北京卡酷少儿", "卡酷少儿", "卡酷少儿高清", "卡酷少儿HD",
        "北京卡酷少儿HD", "卡酷少儿高码", "北京卡酷少儿高码",
        "KAKU", "kaku", "KaKu", "卡酷动画", "卡酷动画HD",
        "卡酷少儿频道", "卡酷少儿[1920*1080]", "卡酷少儿-HD",
        "卡酷少儿（高清）", "北京卡酷", "卡酷卫视", "卡酷",
        "卡酷少儿咪咕", "卡酷少儿标清",
    }),

    # ── 七彩少儿（有线/IPTV 专属频道） ──────────────────────────────────────
    ("七彩少儿", r"(?i)七彩[\s_-]*(?:少儿|儿童)", {
        "七彩少儿", "七彩少儿频道", "七彩少儿HD", "七彩少儿高清",
        "七彩少儿[1920*1080]", "七彩少儿-HD", "七彩儿童", "七彩少儿卫视",
        "七彩少儿咪咕", "七彩少儿标清",
    }),

    # ── 黑莓动画（NewTV·华数传媒） ──────────────────────────────────────────
    ("黑莓动画", r"(?i)黑莓[\s_-]*动[画漫]|NewTV[\s_-]*黑莓", {
        "黑莓动画", "NewTV黑莓动画", "NewTV黑莓", "黑莓动漫",
        "NewTV黑莓动漫", "黑莓动画HD", "黑莓动画高清", "黑莓动画频道",
        "黑莓动漫HD", "黑莓动画标清",
    }),

    # ── 动漫秀场（SiTV·上海广播电视台） ─────────────────────────────────────
    ("动漫秀场", r"(?i)动漫[\s_-]*秀场|SiTV[\s_-]*动漫|sitv动漫", {
        "动漫秀场", "SiTV动漫秀场", "上海动漫秀场", "动漫秀场HD",
        "动漫秀场高清", "SiTV动漫", "动漫秀场频道", "动漫秀场[1920*1080]",
        "SiTV动漫秀场HD", "动漫秀场标清",
    }),

    # ── 爱动漫（iHOT·上海百视通） ───────────────────────────────────────────
    ("爱动漫", r"(?i)(?:iHOT[\s_-]*)?爱[\s_-]*动漫|iHOT[\s_-]*动漫", {
        "爱动漫", "iHOT爱动漫", "iHOT爱动漫频道", "iHOT动漫",
        "爱动漫HD", "爱动漫高清", "iHOT爱动漫HD", "iHOT爱动漫高清",
        "iHOT爱动漫频道HD", "爱动漫标清",
    }),

    # ── 南方少儿（广东有线） ─────────────────────────────────────────────────
    ("南方少儿", r"(?i)南方[\s_-]*少儿", {
        "南方少儿", "南方少儿频道", "南方少儿HD", "南方少儿高清",
        "广东南方少儿", "南方少儿-HD", "南方少儿标清",
    }),

    # ── 星空卫视（Star Chinese Channel） ─────────────────────────────────────
    ("星空卫视", r"(?i)星空[\s_-]*(?:卫视|国际|中文)|star[\s_-]*(?:chinese|中文)|(?<![a-zA-Z])startv(?![a-zA-Z])|(?<![a-zA-Z])starv(?![a-zA-Z])", {
        "星空卫视", "StarTV", "Star卫视", "星空国际", "星空中文台",
        "Star TV", "星空卫视HD", "星空中文频道", "星空卫视高清",
        "星空中文台HD", "STARTV", "STARV", "星空卫视标清",
        "Star Chinese Channel",
    }),
]

# ── 噪声词（匹配前从频道名中剔除，防止平台/ISP 标识干扰识别） ────────────────
_NOISE_PATTERN = re.compile(r"migu|mgtv", re.IGNORECASE)

# ── 支持的直播流协议 ──────────────────────────────────────────────────────────
_STREAM_PROTOCOLS = ("http://", "https://", "rtmp://", "rtsp://", "rtp://", "udp://")


def normalize_name(name: str) -> str:
    """剔除频道名中的噪声词。"""
    return _NOISE_PATTERN.sub("", name).strip()


def _build_matcher():
    """
    构建两个查找结构：
      alias_map  : normalize(别名) -> 标准名   （O(1) 精确匹配）
      regex_list : [(标准名, 编译正则), ...]   （顺序正则兜底）
    """
    alias_map: dict[str, str] = {}
    regex_list = []
    for std_name, pat, aliases in _CHANNEL_DEFS_RAW:
        for alias in aliases:
            alias_map[normalize_name(alias)] = std_name
        regex_list.append((std_name, re.compile(pat)))
    return alias_map, regex_list


_ALIAS_MAP, _REGEX_LIST = _build_matcher()


def identify_channel(name: str) -> str | None:
    """
    识别频道名，返回标准名；无法识别则返回 None。
    优先精确别名匹配，再用正则兜底。
    """
    normalized = normalize_name(name.strip())
    if normalized in _ALIAS_MAP:
        return _ALIAS_MAP[normalized]
    for std_name, regex in _REGEX_LIST:
        if regex.search(normalized):
            return std_name
    return None


# ── 解析 m3u 格式 ─────────────────────────────────────────────────────────────
def parse_m3u(text: str) -> list[tuple[str, str]]:
    results = []
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if line.startswith("#EXTINF"):
            tvg = re.search(r'tvg-name="([^"]*)"', line, re.IGNORECASE)
            ch_name = tvg.group(1) if tvg else ""
            if not ch_name:
                comma = line.rfind(",")
                ch_name = line[comma + 1:].strip() if comma != -1 else ""
            if i + 1 < len(lines):
                url = lines[i + 1].strip()
                if url and url.lower().startswith(_STREAM_PROTOCOLS):
                    results.append((ch_name, url))
                    i += 2
                    continue
        i += 1
    return results


# ── 解析 txt 格式 ─────────────────────────────────────────────────────────────
def parse_txt(text: str) -> list[tuple[str, str]]:
    results = []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "#genre#" in line:
            continue
        if "," not in line:
            continue
        ch_name, _, url_field = line.partition(",")
        ch_name = ch_name.strip()
        if not url_field.strip():
            continue
        # 支持 | 分隔的多路 URL
        for url in url_field.split("|"):
            url = url.strip()
            if url and url.lower().startswith(_STREAM_PROTOCOLS):
                results.append((ch_name, url))
    return results


# ── 读取文件（尝试多种编码） ──────────────────────────────────────────────────
def read_file(path: str) -> str:
    for enc in ("utf-8", "utf-8-sig", "gbk", "gb2312", "latin-1"):
        try:
            with open(path, "r", encoding=enc) as f:
                return f.read()
        except (UnicodeDecodeError, LookupError):
            continue
    return ""


# ── 自然数排序（src-1, src-2 ... src-10，而非字典序） ────────────────────────
def _natural_sort_key(path: str):
    name = os.path.basename(path)
    return [int(c) if c.isdigit() else c.lower() for c in re.split(r"(\d+)", name)]


# ── 主逻辑 ────────────────────────────────────────────────────────────────────
def main():
    input_dir = "sources"
    output_dir = os.path.join(input_dir, "temp")
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, "少儿动漫频道.m3u")

    patterns = [
        os.path.join(input_dir, "src-*.m3u"),
        os.path.join(input_dir, "src-*.m3u8"),
        os.path.join(input_dir, "src-*.txt"),
    ]
    files = []
    for p in patterns:
        files.extend(glob.glob(p))

    if not files:
        print(f"⚠️  未在 {input_dir} 找到任何 src-* 文件，请检查路径。")
        return

    # 按自然数顺序排序：src-1, src-2 ... src-10, src-11 ...
    files.sort(key=_natural_sort_key)

    print(f"找到 {len(files)} 个订阅文件（自然数顺序）：")
    for f in files:
        print(f"  {f}")

    channel_map: dict[str, set] = defaultdict(set)

    for fpath in files:
        content = read_file(fpath)
        if not content:
            print(f"  ⚠️  无法读取：{fpath}")
            continue

        if "#EXTM3U" in content or "#EXTINF" in content:
            entries = parse_m3u(content)
        else:
            entries = parse_txt(content)

        matched = 0
        for ch_name, url in entries:
            std = identify_channel(ch_name)
            if std:
                channel_map[std].add(url)
                matched += 1

        print(f"  ✔ {os.path.basename(fpath)}：共 {len(entries)} 条，匹配少儿动漫 {matched} 条")

    # ── 构建输出 m3u ──────────────────────────────────────────────────────────
    lines_out = ["#EXTM3U"]
    total = 0
    for std_name in CHANNEL_ORDER:
        for url in sorted(channel_map.get(std_name, set())):
            lines_out.append(
                f'#EXTINF:-1 tvg-name="{std_name}" '
                f'group-title="{GROUP_TITLE}",{std_name}'
            )
            lines_out.append(url)
            total += 1

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines_out) + "\n")

    print(f"\n✅ 完成！共写入 {total} 条少儿动漫频道链接 → {output_path}")
    print("\n各频道链接数量：")
    for std_name in CHANNEL_ORDER:
        cnt = len(channel_map.get(std_name, set()))
        if cnt:
            print(f"  {std_name:<14} {cnt} 条")


if __name__ == "__main__":
    main()
