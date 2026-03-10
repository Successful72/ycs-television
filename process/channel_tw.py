# -*- coding: utf-8 -*-
"""
台湾频道 IPTV 提取工具
从 sources 目录下的所有 m3u/txt 文件中提取台湾频道，
按知名度排序后输出为新的 m3u 文件到 sources/temp 目录。
"""

import os
import re
import glob
from collections import OrderedDict

# ============================================================
# 台湾频道清单（按知名度从大到小排列）
# 每项格式：
#   ( "输出时使用的简体中文名称", [匹配用的正则关键词列表] )
# ============================================================
TW_CHANNELS = [
    # ── 无线四台（知名度最高）──────────────────────────────
    ("台视",           [r"台視", r"台视", r"TTV", r"臺視"]),
    ("中视",           [
                           r"中視(?!频|頻|频道|頻道)",
                           r"(?<!央)中视(?!频|頻|频道|頻道|央)",
                           r"\bCTV\b",
                           r"中視新聞",
                       ]),
    ("华视",           [r"華視", r"华视", r"CTS"]),
    ("民视",           [r"民視", r"民视", r"FTV"]),
    # ── 新闻台 ──────────────────────────────────────────────
    ("TVBS新闻台",     [r"TVBS[\-\s]*新聞", r"TVBS[\-\s]*新闻", r"TVBS[\-\s]*N"]),
    ("TVBS",           [r"TVBS(?![\-\s]*新)"]),
    ("三立新闻台",     [r"三立新聞", r"三立新闻", r"SET\s*News", r"SETN"]),
    ("中天新闻台",     [r"中天新聞", r"中天新闻", r"CTi\s*News", r"中天新聞台"]),
    ("东森新闻台",     [r"東森新聞", r"东森新闻", r"ETtoday", r"ETNews", r"EBC\s*News"]),
    ("年代新闻台",     [r"年代新聞", r"年代新闻", r"ERA\s*News", r"年代"]),
    # ── 综合/戏剧/娱乐 ──────────────────────────────────────
    ("三立台湾台",     [r"三立台灣台", r"三立台湾台", r"SET\s*Taiwan", r"三立台灣"]),
    ("三立都会台",     [r"三立都會台", r"三立都会台", r"SET\s*Metro"]),
    ("东森综合台",     [r"東森綜合", r"东森综合", r"ETV\s*综合", r"EBC\s*綜合"]),
    ("东森戏剧台",     [r"東森戲劇", r"东森戏剧", r"ETV\s*戏剧", r"EBC\s*戲劇"]),
    ("中天综合台",     [r"中天綜合", r"中天综合", r"CTi\s*综合"]),
    ("中天娱乐台",     [r"中天娛樂", r"中天娱乐", r"CTi\s*Ent"]),
    ("民视综合台",     [r"民視綜合", r"民视综合"]),
    ("台视综合台",     [r"台視綜合", r"台视综合"]),
    ("华视综合台",     [r"華視綜合", r"华视综合"]),
    # ── 电影/洋片 ───────────────────────────────────────────
    ("东森电影台",     [r"東森電影", r"东森电影", r"EBC\s*Movie", r"ETV\s*电影"]),
    ("HBO台湾",        [r"HBO\s*(?:Taiwan|台湾|台灣)", r"HBO\s*TW"]),
    ("MOD电影",        [r"MOD\s*(?:电影|電影|Movie)"]),
    # ── 儿童/教育 ───────────────────────────────────────────
    ("东森幼幼台",     [r"東森幼幼", r"东森幼幼", r"Yoyo\s*TV", r"YOYO"]),
    ("卡通频道台湾",   [r"Cartoon\s*Network.*(?:TW|Taiwan|台灣)", r"卡通(?:頻道|频道).*(?:台灣|台湾)"]),
    # ── 体育 ────────────────────────────────────────────────
    ("纬来体育台",     [r"緯來體育", r"纬来体育", r"緯來", r"Latitude\s*Sport"]),
    ("纬来综合台",     [r"緯來綜合", r"纬来综合"]),
    ("超视",           [r"超視", r"超视", r"CSTV", r"Ch(?:annel)?\s*[Ss]uper"]),
    # ── 生活/旅游/美食 ──────────────────────────────────────
    ("东森房屋台",     [r"東森房屋", r"东森房屋"]),
    ("东森购物台",     [r"東森購物", r"东森购物", r"ETMall"]),
    ("MOMO购物台",     [r"momo\s*购物", r"momo\s*購物", r"momo\s*TV", r"MOMO\s*TV"]),
    # ── 公共/政论 ───────────────────────────────────────────
    ("公视",           [r"公視", r"公视", r"PTS"]),
    ("民视新闻台",     [r"民視新聞", r"民视新闻", r"FTV\s*News"]),
    ("客家电视台",     [r"客家電視", r"客家电视", r"HakkaTV"]),
    ("原住民电视台",   [r"原住民電視", r"原住民电视", r"TITV"]),
    # ── 其他知名频道 ────────────────────────────────────────
    ("大爱电视",       [r"大愛電視", r"大爱电视", r"DaAi\s*TV", r"大愛"]),
    ("寰宇新闻台",     [r"寰宇新聞", r"寰宇新闻", r"Videoland\s*News", r"JET\s*News"]),
    ("八大综合台",     [r"八大綜合", r"八大综合", r"GTV\s*综合", r"GTV"]),
    ("台湾宽频",       [r"台灣寬頻", r"台湾宽频", r"TWC"]),
]

# ============================================================
# 辅助：将繁体关键词列表编译成单条正则
# ============================================================
def build_pattern(keywords: list[str]) -> re.Pattern:
    combined = "|".join(f"(?:{kw})" for kw in keywords)
    return re.compile(combined, re.IGNORECASE)

CHANNEL_PATTERNS = [
    (name, build_pattern(kws))
    for name, kws in TW_CHANNELS
]

def parse_file_line_by_line(filepath: str):
    """
    逐行读取文件的通用解析器，支持 m3u、m3u8、txt 格式
    返回 list of (channel_name_raw, url)
    """
    entries = []
    ext = os.path.splitext(filepath)[1].lower()
    
    try:
        with open(filepath, encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
    except Exception as e:
        print(f"❌ 读取文件失败 {filepath}: {e}")
        return []
    
    # 检测是否为 m3u 格式
    is_m3u_format = any(line.upper().startswith("#EXTINF") for line in lines[:10])
    
    if ext in (".m3u", ".m3u8") or is_m3u_format:
        # M3U 格式解析
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            if line.startswith("#EXTINF"):
                # 取 tvg-name 属性（可能为空）
                tvg_match = re.search(r'tvg-name="([^"]*)"', line, re.IGNORECASE)
                tvg_name = tvg_match.group(1).strip() if tvg_match else ""
                # 取显示名：逗号之后的部分
                disp_match = re.search(r",(.+)$", line)
                display_name = disp_match.group(1).strip() if disp_match else ""
                # 两者拼合作为匹配文本，优先用非空的那个作为代表名
                ch_name = display_name or tvg_name
                search_name = f"{tvg_name} {display_name}".strip()
                # 查找下一行非空行作为 URL
                j = i + 1
                while j < len(lines):
                    next_line = lines[j].strip()
                    if next_line and not next_line.startswith("#"):
                        url = next_line
                        entries.append((search_name, url))
                        i = j + 1
                        break
                    j += 1
                else:
                    i += 1
            else:
                i += 1
    else:
        # TXT 格式解析（"名称,URL"）
        for line in lines:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split(",", 1)
            if len(parts) == 2:
                name_part, url_part = parts[0].strip(), parts[1].strip()
                if re.match(r"https?://|rtmp://|rtsp://", url_part, re.I):
                    entries.append((name_part, url_part))

    return entries

# ============================================================
# 主逻辑
# ============================================================
def natural_sort_key(filepath: str):
    """
    自然数排序键：将文件名中的数字部分按数值大小排序，
    避免字典序导致 src-2 排在 src-10 之后的问题。
    """
    basename = os.path.basename(filepath)
    parts = re.split(r'(\d+)', basename)
    return [int(p) if p.isdigit() else p.lower() for p in parts]


def main():
    # 使用相对于工作目录的路径
    input_dir = "sources"
    output_dir = os.path.join("sources", "temp")
    output_path = os.path.join(output_dir, "台湾频道.m3u")
    
    # 确保输出目录存在
    os.makedirs(output_dir, exist_ok=True)
    
    print("=" * 60)
    print("台湾频道 IPTV 提取工具")
    print("=" * 60)
    print(f"📁 当前工作目录: {os.getcwd()}")
    print(f"📁 源文件目录: {input_dir}")
    print(f"📁 输出目录: {output_dir}")

    # 检查源目录是否存在
    if not os.path.exists(input_dir):
        print(f"❌ 源目录不存在: {input_dir}")
        return

    # 收集源文件
    files = []
    for pattern in ["src-*.m3u", "src-*.m3u8", "src-*.txt"]:
        files.extend(glob.glob(os.path.join(input_dir, pattern)))
    
    # 排除 temp 目录中的文件
    files = [f for f in files if not f.startswith(os.path.join(input_dir, "temp"))]
    # 排除输出文件本身（如果存在）
    files = [f for f in files if os.path.abspath(f) != os.path.abspath(output_path)]
    files = sorted(set(files), key=natural_sort_key)

    if not files:
        print(f"❌ 在 {input_dir} 下未找到任何 m3u/m3u8/txt 文件！")
        return

    print(f"\n📂 共找到 {len(files)} 个文件：")
    for f in files:
        print(f"   {os.path.basename(f)}")
    print()

    # 解析所有文件，按台湾频道分桶
    buckets: dict[int, "OrderedDict[str, bool]"] = {i: OrderedDict() for i in range(len(CHANNEL_PATTERNS))}
    total_raw = 0

    for filepath in files:
        entries = parse_file_line_by_line(filepath)
        total_raw += len(entries)
        for raw_name, url in entries:
            for idx, (ch_name, pattern) in enumerate(CHANNEL_PATTERNS):
                if pattern.search(raw_name):
                    if url not in buckets[idx]:
                        buckets[idx][url] = True
                    break

    # 统计
    matched_channels = sum(1 for v in buckets.values() if v)
    matched_urls     = sum(len(v) for v in buckets.values())
    
    print(f"📊 共解析条目：{total_raw}")
    print(f"📊 匹配台湾频道数：{matched_channels}")
    print(f"📊 匹配 URL 总数（已去重）：{matched_urls}")
    print()

    # 写出 m3u 文件
    with open(output_path, "w", encoding="utf-8-sig") as out:
        out.write("#EXTM3U\n\n")
        print("📋 提取结果：")
        for idx, (ch_name, _pattern) in enumerate(CHANNEL_PATTERNS):
            urls = list(buckets[idx].keys())
            if not urls:
                continue
            print(f"   ✅ {ch_name}：{len(urls)} 个链接")
            for url in urls:
                out.write(
                    f'#EXTINF:-1 group-title="台湾频道",{ch_name}\n'
                    f'{url}\n'
                )

    print()
    print(f"🎉 输出完成！")
    print(f"📄 输出文件：{output_path}")
    print(f"📁 文件大小：{os.path.getsize(output_path)} 字节")
    print("=" * 60)

if __name__ == "__main__":
    main()
