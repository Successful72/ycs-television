#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
从 m3u/txt 格式的 IPTV 订阅文件中提取 CCTV 频道，组装成新的 m3u 文件。
"""

import os
import re
import glob
from collections import defaultdict

# ── 输出频道顺序 ──────────────────────────────────────────────────────────────
CHANNEL_ORDER = [
    "CCTV-1", "CCTV-2", "CCTV-3",
    "CCTV-4", "CCTV-4欧洲", "CCTV-4美洲",
    "CCTV-5", "CCTV-5+",
    "CCTV-6", "CCTV-7", "CCTV-8", "CCTV-9", "CCTV-10",
    "CCTV-11", "CCTV-12", "CCTV-13", "CCTV-14", "CCTV-15",
    "CCTV-16", "CCTV-17", "CCTV-4K", "CCTV-8K",
]

# ── 频道定义 ──────────────────────────────────────────────────────────────────
# 格式：(标准名, 正则表达式字符串, {别名集合})
# 正则与别名均来源于 abc.txt
# 注意：特殊频道（4K/8K/5+/4欧洲/4美洲）须放在对应普通频道之前，防止宽泛正则误吞
_CHANNEL_DEFS_RAW = [
    ("CCTV-1",  r"(?i)^\s*CCTV[-\s_]*0?1(?![0-9Kk+])[\s\S]*$", {
        "CCTV1","CCTV-01","CCTV-01_ITV","CCTV-01北联","CCTV-01电信","CCTV-01东联",
        "CCTV-01高码","CCTV-01高清","CCTV-01广西","CCTV-01梅州","CCTV-01咪咕",
        "CCTV-01汝阳","CCTV-01山东","CCTV-01上海","CCTV-01斯特","CCTV-01四川",
        "CCTV-01太原","CCTV-01天津","CCTV-01影视","CCTV-01浙江","CCTV-01重庆",
        "CCTV1综合","CCTV-1综合","CCTV1(B)","CCTV1[1920*1080]","CCTV1「IPV6」",
        "CCTV1HD","CCTV-1HD","CCTV1-标清","CCTV-1高清","CCTV1-综合",
    }),
    ("CCTV-2",  r"(?i)^\s*CCTV[-\s_]*0?2(?![0-9Kk+])[\s\S]*$", {
        "CCTV2","CCTV-02北联","CCTV-02电信","CCTV-02东联","CCTV-02高码","CCTV-02高清",
        "CCTV-02广西","CCTV-02梅州","CCTV-02咪咕","CCTV-02汝阳","CCTV-02山东",
        "CCTV-02上海","CCTV-02斯特","CCTV-02四川","CCTV-02太原","CCTV-02天津",
        "CCTV-02影视","CCTV-02浙江","CCTV-02重庆","CCTV2财经","CCTV-2财经",
        "CCTV2[1280*720]","CCTV2「IPV6」","CCTV2HD","CCTV-2HD","CCTV2-标清",
        "CCTV2-财经","CCTV-2高清",
    }),
    ("CCTV-3",  r"(?i)^\s*CCTV[-\s_]*0?3(?![0-9Kk+])[\s\S]*$", {
        "CCTV3","CCTV-03","CCTV-03_ITV","CCTV-03北联","CCTV-03电信","CCTV-03东联",
        "CCTV-03高码","CCTV-03高清","CCTV-03广西","CCTV-03梅州","CCTV-03咪咕",
        "CCTV-03汝阳","CCTV-03山东","CCTV-03上海","CCTV-03斯特","CCTV-03四川",
        "CCTV-03太原","CCTV-03天津","CCTV-03影视","CCTV-03浙江","CCTV-03重庆",
        "CCTV3综艺","CCTV-3综艺","CCTV3[1920*1080]","CCTV3「IPV6」","CCTV3HD",
        "CCTV-3HD","CCTV3-标清","CCTV-3高清","CCTV-3-高清","CCTV3-综艺",
    }),
    # CCTV-4K 须在 CCTV-4 之前
    ("CCTV-4K", r"(?i)^\s*CCTV[-\s_]*0?4(?![0-9])\s*(?:[Kk]|Ｋ)\b[\s\S]*$", {
        "CCTV4K","cctv4k_10m","CCTV4K超高清","CCTV-4K超高清","CCTV-4k高码",
        "CCTV-4K广西","CCTV-4k浙江",
    }),
    # CCTV-4欧洲 / 4美洲 须在 CCTV-4 之前
    ("CCTV-4欧洲", r"(?i)^\s*CCTV[-\s_]*0?4(?![0-9Kk+])[\s\S]*\b(?:欧洲|Europe)\b[\s\S]*$", {
        "CCTV4欧洲","CCTV4欧洲咪咕",
    }),
    ("CCTV-4美洲", r"(?i)^\s*CCTV[-\s_]*0?4(?![0-9Kk+])[\s\S]*\b(?:美洲|America|Americas)\b[\s\S]*$", {
        "CCTV4美洲","CCTV4美洲咪咕",
    }),
    ("CCTV-4",  r"(?i)^\s*CCTV[-\s_]*0?4(?![0-9Kk+])(?!.*(?:欧洲|美洲|Europe|America|Americas))[\s\S]*$", {
        "CCTV4","CCTV-04","CCTV-04_ITV","CCTV-04北联","CCTV-04电信","CCTV-04东联",
        "CCTV-04高码","CCTV-04高清","CCTV-04广西","CCTV-04梅州","CCTV-04咪咕",
        "CCTV-04汝阳","CCTV-04山东","CCTV-04上海","CCTV-04斯特","CCTV-04四川",
        "CCTV-04太原","CCTV-04天津","CCTV-04影视","CCTV-04浙江","CCTV-04重庆",
        "CCTV4[1280*720]","CCTV4[1920*1080]","CCTV4「IPV6」","CCTV4HD","CCTV-4HD",
        "CCTV-4标清","CCTV-4高清",
    }),
    # CCTV-5+ 须在 CCTV-5 之前
    ("CCTV-5+", r"(?i)^\s*CCTV[-\s_]*0?5\s*(?:\+|＋)[\s\S]*$", {
        "CCTV5+","CCTV5＋","CCTV5+ 体育赛事","CCTV-5+体育赛事","CCTV5+[1920*1080]",
        "CCTV-5+_ITV","CCTV5+「IPV6」","CCTV5+HD","CCTV-5+HD","CCTV-5+北联",
        "CCTV-5+电信","CCTV-5+高码","CCTV-5+高清","CCTV-5+广西","CCTV-5+梅州",
        "CCTV-5+咪咕","CCTV-5+汝阳","CCTV-5+四川","CCTV-5+太原","CCTV5+体育赛事",
        "CCTV5+-体育赛事","CCTV-5+天津","CCTV-5+影视","CCTV-5+浙江","CCTV-5+重庆",
        "CCTV5+斯特","CCTV5+体育",
    }),
    ("CCTV-5",  r"(?i)^\s*CCTV[-\s_]*0?5(?![0-9Kk+])[\s\S]*$", {
        "CCTV5","CCTV-05","CCTV-05_ITV","CCTV-05北联","CCTV-05电信","CCTV-05东联",
        "CCTV-05高码","CCTV-05高清","CCTV-05广西","CCTV-05梅州","CCTV-05咪咕",
        "CCTV-05汝阳","CCTV-05山东","CCTV-05上海","CCTV-05斯特","CCTV-05四川",
        "CCTV-05太原","CCTV-05天津","CCTV-05影视","CCTV-05浙江","CCTV-05重庆",
        "CCTV5体育","CCTV-5 体育","CCTV-5体育（高码率）","CCTV5[1920*1080]",
        "CCTV5「IPV6」","CCTV5HD","CCTV-5HD","CCTV5-标清","CCTV-5高清","CCTV-5-高清",
        "CCTV-5高清测试","CCTV5-体育","CCTV-5体育",
    }),
    ("CCTV-6",  r"(?i)^\s*CCTV[-\s_]*0?6(?![0-9Kk+])[\s\S]*$", {
        "CCTV6","CCTV-06","CCTV-06_ITV","CCTV-06北联","CCTV-06电信","CCTV-06东联",
        "CCTV-06高码","CCTV-06高清","CCTV-06广西","CCTV-06梅州","CCTV-06咪咕",
        "CCTV-06汝阳","CCTV-06山东","CCTV-06上海","CCTV-06斯特","CCTV-06四川",
        "CCTV-06太原","CCTV-06天津","CCTV-06影视","CCTV-06浙江","CCTV-06重庆",
        "CCTV6电影","CCTV-6电影","CCTV6[1920*1080]","CCTV6「IPV6」","CCTV6HD",
        "CCTV-6HD","CCTV6-标清","CCTV6-电影","CCTV-6高清","CCTV-6-高清","CCTV-6高清测试",
    }),
    ("CCTV-7",  r"(?i)^\s*CCTV[-\s_]*0?7(?![0-9Kk+])[\s\S]*$", {
        "CCTV7","CCTV7 国防军事","CCTV-7国防军事","CCTV7[1920*1080]","CCTV7「IPV6」",
        "CCTV7HD","CCTV-7HD","CCTV7-标清","CCTV-7高清","CCTV7-国防军事","CCTV7-军农",
        "CCTV-07","CCTV-07_ITV","CCTV-07北联","CCTV-07电信","CCTV-07东联","CCTV-07高码",
        "CCTV-07高清","CCTV-07广西","CCTV-07梅州","CCTV-07咪咕","CCTV-07汝阳",
        "CCTV-07山东","CCTV-07上海","CCTV-07斯特","CCTV-07四川","CCTV-07太原",
        "CCTV-07天津","CCTV-07影视","CCTV-07浙江","CCTV-07重庆","CCTV7军事","CCTV国防军事",
    }),
    # CCTV-8K 须在 CCTV-8 之前
    ("CCTV-8K", r"(?i)^\s*CCTV[-\s_]*0?8(?![0-9])\s*(?:[Kk]|Ｋ)\b[\s\S]*$", {
        "CCTV8K","CCTV8K 超高清","CCTV-8K超高清[3840*2160]","cctv8k_120m","cctv8k_36m",
        "CCTV8K超高清","CCTV-8k高码",
    }),
    ("CCTV-8",  r"(?i)^\s*CCTV[-\s_]*0?8(?![0-9Kk+])[\s\S]*$", {
        "CCTV8","CCTV8 电视剧","CCTV-8电视剧","CCTV8[1920*1080]","CCTV8「IPV6」",
        "CCTV8HD","CCTV-8HD","CCTV8-标清","CCTV8-电视剿","CCTV-8电视剿","CCTV8-电视剧",
        "CCTV-8电视剧","CCTV-8高清","CCTV-8-高清","CCTV-08","CCTV-08_ITV","CCTV-08北联",
        "CCTV-08电信","CCTV-08东联","CCTV-08高码","CCTV-08高清","CCTV-08广西","CCTV-08梅州",
        "CCTV-08咪咕","CCTV-08汝阳","CCTV-08山东","CCTV-08上海","CCTV-08斯特","CCTV-08四川",
        "CCTV-08太原","CCTV-08天津","CCTV-08影视","CCTV-08浙江","CCTV-08重庆","CCTV8电视剧",
    }),
    ("CCTV-9",  r"(?i)^\s*CCTV[-\s_]*0?9(?![0-9Kk+])[\s\S]*$", {
        "CCTV9","CCTV9 纪录","CCTV-9纪录","CCTV9[1920*1080]","CCTV9「IPV6」",
        "CCTV9HD","CCTV-9HD","CCTV9-标清","CCTV-9高清","CCTV9-纪录",
        "CCTV-09","CCTV-09_ITV","CCTV-09北联","CCTV-09电信","CCTV-09东联","CCTV-09高码",
        "CCTV-09高清","CCTV-09广西","CCTV-09梅州","CCTV-09咪咕","CCTV-09汝阳",
        "CCTV-09山东","CCTV-09上海","CCTV-09斯特","CCTV-09四川","CCTV-09太原",
        "CCTV-09天津","CCTV-09影视","CCTV-09浙江","CCTV-09重庆","CCTV9纪录",
    }),
    ("CCTV-10", r"(?i)^\s*CCTV[-\s_]*0?10(?![0-9Kk+])[\s\S]*$", {
        "CCTV10","CCTV10 科教","CCTV-10科教","CCTV10[1920*1080]","CCTV-10_ITV",
        "CCTV10「IPV6」","CCTV10HD","CCTV-10HD","CCTV-10北联","CCTV10-标清","CCTV-10电信",
        "CCTV-10东联","CCTV-10高码","CCTV-10高清","CCTV-10广西","CCTV10-科教","CCTV-10梅州",
        "CCTV-10咪咕","CCTV-10汝阳","CCTV-10山东","CCTV-10上海","CCTV-10斯特","CCTV-10四川",
        "CCTV-10太原","CCTV-10天津","CCTV-10影视","CCTV-10浙江","CCTV-10重庆","CCTV10科教",
    }),
    ("CCTV-11", r"(?i)^\s*CCTV[-\s_]*0?11(?![0-9Kk+])[\s\S]*$", {
        "CCTV11","CCTV11 戏曲","CCTV-11戏曲","CCTV11[1280*720]","CCTV-11_ITV",
        "CCTV11「IPV6」","CCTV11HD","CCTV-11HD","CCTV-11北联","CCTV11-标清","CCTV-11电信",
        "CCTV-11东联","CCTV-11高码","CCTV-11高清","CCTV-11广西","CCTV-11梅州","CCTV-11咪咕",
        "CCTV-11汝阳","CCTV-11山东","CCTV-11上海","CCTV-11斯特","CCTV-11四川","CCTV-11太原",
        "CCTV-11天津","CCTV11-戏曲","CCTV-11影视","CCTV-11浙江","CCTV-11重庆",
        "CCTV11戏曲","CCTV戏曲","CCTV-戏曲",
    }),
    ("CCTV-12", r"(?i)^\s*CCTV[-\s_]*0?12(?![0-9Kk+])[\s\S]*$", {
        "CCTV12","CCTV12 社会与法","CCTV-12 社会与法","CCTV-12社会与法（5.1环绕声）",
        "CCTV12[1920*1080]","CCTV-12_ITV","CCTV12「IPV6」","CCTV12HD","CCTV-12HD",
        "CCTV-12北联","CCTV12-标清","CCTV-12电信","CCTV-12东联","CCTV-12高码","CCTV-12高清",
        "CCTV-12广西","CCTV-12梅州","CCTV-12咪咕","CCTV-12汝阳","CCTV-12山东","CCTV-12上海",
        "CCTV12-社会与法","CCTV-12社会与法","CCTV-12斯特","CCTV-12四川","CCTV-12太原",
        "CCTV-12天津","CCTV-12影视","CCTV-12浙江","CCTV-12重庆","CCTV12社会与法",
    }),
    ("CCTV-13", r"(?i)^\s*CCTV[-\s_]*0?13(?![0-9Kk+])[\s\S]*$", {
        "CCTV13","CCTV13 新闻","CCTV-13新闻","CCTV13[1920*1080]","CCTV13「IPV6」",
        "CCTV13HD","CCTV-13HD","CCTV-13北联","CCTV13-标清","CCTV-13电信","CCTV-13东联",
        "CCTV-13高码","CCTV-13高清","CCTV-13广西","CCTV-13梅州","CCTV-13咪咕","CCTV-13汝阳",
        "CCTV-13山东","CCTV-13上海","CCTV-13斯特","CCTV-13四川","CCTV-13太原","CCTV-13天津",
        "CCTV13听电视","CCTV13-新闻","CCTV-13影视","CCTV-13浙江","CCTV-13重庆","CCTV13新闻",
    }),
    ("CCTV-14", r"(?i)^\s*CCTV[-\s_]*0?14(?![0-9Kk+])[\s\S]*$", {
        "CCTV14","CCTV14 少儿","CCTV-14少儿","CCTV14[1920*1080]","CCTV-14_ITV",
        "CCTV14「IPV6」","CCTV14HD","CCTV-14HD","CCTV-14北联","CCTV14-标清","CCTV-14电信",
        "CCTV-14东联","CCTV-14高码","CCTV-14高清","CCTV-14广西","CCTV-14梅州","CCTV-14咪咕",
        "CCTV-14汝阳","CCTV-14山东","CCTV-14上海","CCTV14-少儿","CCTV-14斯特","CCTV-14四川",
        "CCTV-14太原","CCTV-14天津","CCTV-14影视","CCTV-14浙江","CCTV-14重庆",
        "CCTV14少儿","CCTV少儿","CCTV-少儿",
    }),
    ("CCTV-15", r"(?i)^\s*CCTV[-\s_]*0?15(?![0-9Kk+])[\s\S]*$", {
        "CCTV15","CCTV15 音乐","CCTV-15音乐","CCTV-15(音乐)","CCTV15[1280*720]",
        "CCTV-15_ITV","CCTV15「IPV6」","CCTV15HD","CCTV-15HD","CCTV-15北联","CCTV15-标清",
        "CCTV-15电信","CCTV-15东联","CCTV-15高码","CCTV-15高清","CCTV-15广西","CCTV-15梅州",
        "CCTV-15咪咕","CCTV-15汝阳","CCTV-15山东","CCTV-15上海","CCTV-15斯特","CCTV-15四川",
        "CCTV-15太原","CCTV-15天津","CCTV15-音乐","CCTV-15影视","CCTV-15浙江","CCTV-15重庆",
        "CCTV15音乐","CCTV音乐","CCTV娱乐","CCTV-娱乐",
    }),
    ("CCTV-16", r"(?i)^\s*CCTV[-\s_]*0?16(?![0-9Kk+])[\s\S]*$", {
        "CCTV16","CCTV16 4K","CCTV-16 4K","CCTV16 奥林匹克","CCTV-16 奥林匹克",
        "CCTV-16奥林匹克（5.1环绕声）","CCTV-16奥林匹克4K（5.1环绕声）","CCTV16(4K)",
        "CCTV16[1920*1080]","CCTV-16_ITV","CCTV16「IPV6」","CCTV16-4K","CCTV-16-4K",
        "CCTV16-4K-25PHLG源","CCTV16HD","CCTV-16HD","CCTV16-奥林匹克","CCTV-16奥林匹克",
        "CCTV16奥林匹克4K","CCTV-16北联","CCTV-16电信","CCTV-16高码","CCTV-16高清",
        "CCTV-16梅州","CCTV-16咪咕","CCTV-16汝阳","CCTV-16太原","CCTV-16天津",
        "CCTV-16影视","CCTV-16浙江","CCTV16体育赛事",
    }),
    ("CCTV-17", r"(?i)^\s*CCTV[-\s_]*0?17(?![0-9Kk+])[\s\S]*$", {
        "CCTV17","CCTV17 农业农村","CCTV-17 农业农村","CCTV-17农业农村（5.1环绕声）",
        "CCTV17[1920*1080]","CCTV-17_ITV","CCTV17「IPV6」","CCTV17HD","CCTV-17HD",
        "CCTV-17北联","CCTV17-标清","CCTV-17电信","CCTV-17高码","CCTV-17高清","CCTV-17广西",
        "CCTV-17梅州","CCTV-17咪咕","CCTV17-农业农村","CCTV-17农业农村","CCTV-17汝阳",
        "CCTV-17上海","CCTV-17四川","CCTV-17太原","CCTV-17天津","CCTV-17影视",
        "CCTV-17浙江","CCTV-17重庆","CCTV17农业农村",
    }),
]

# ── 噪声词（匹配前从频道名中剔除）────────────────────────────────────────────
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


# ── 解析 m3u 格式 ──────────────────────────────────────────────────────────────
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


# ── 解析 txt 格式 ──────────────────────────────────────────────────────────────
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
        # 支持 | 分隔的多路 URL
        for url in url_field.split("|"):
            url = url.strip()
            if url and url.lower().startswith(_STREAM_PROTOCOLS):
                results.append((ch_name, url))
    return results


# ── 读取文件（尝试多种编码）────────────────────────────────────────────────────
def read_file(path: str) -> str:
    for enc in ("utf-8", "utf-8-sig", "gbk", "gb2312", "latin-1"):
        try:
            with open(path, "r", encoding=enc) as f:
                return f.read()
        except (UnicodeDecodeError, LookupError):
            continue
    return ""


# ── 自然数排序（src-1, src-2 ... src-10, 而非 src-1, src-10, src-2）──────────
def _natural_sort_key(path: str):
    """将文件名中连续数字段转为整数参与排序，实现自然数顺序。"""
    name = os.path.basename(path)
    return [int(c) if c.isdigit() else c.lower() for c in re.split(r"(\d+)", name)]


# ── 主逻辑 ────────────────────────────────────────────────────────────────────
def main():
    input_dir = "sources"
    output_dir = os.path.join(input_dir, "temp")
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, "央视公共频道.m3u")

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

    # 按自然数顺序排序：src-1, src-2, ... src-10, src-11 ...
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

        print(f"  ✔ {os.path.basename(fpath)}：共 {len(entries)} 条，匹配 CCTV {matched} 条")

    # ── 构建输出 m3u ──────────────────────────────────────────────────────────
    lines_out = ["#EXTM3U"]
    total = 0
    for std_name in CHANNEL_ORDER:
        for url in sorted(channel_map.get(std_name, set())):
            lines_out.append(
                f'#EXTINF:-1 tvg-name="{std_name}" '
                f'group-title="央视公共频道",{std_name}'
            )
            lines_out.append(url)
            total += 1

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines_out) + "\n")

    print(f"\n✅ 完成！共写入 {total} 条 CCTV 频道链接 → {output_path}")
    print("\n各频道链接数量：")
    for std_name in CHANNEL_ORDER:
        cnt = len(channel_map.get(std_name, set()))
        if cnt:
            print(f"  {std_name:<14} {cnt} 条")


if __name__ == "__main__":
    main()
