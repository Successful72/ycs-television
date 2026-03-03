#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
香港频道 IPTV 提取工具
从 sources 目录中的 m3u/txt 文件提取香港频道，
组装成新的 m3u 文件到 sources/temp 目录。
"""

import os
import re
import glob

# ============================================================
# 香港频道定义（按知名度从大到小排序）
# 每个条目：(标准名称, [匹配关键词列表])
# ============================================================
HK_CHANNELS = [
    # 免费电视 - TVB
    ("翡翠台",          [r"翡翠台", r"tvb\s*jade", r"jade\s*channel", r"tvb翡翠", r"翡翠"]),
    ("TVB明珠台",       [r"明珠台", r"tvb\s*pearl", r"pearl\s*channel", r"tvb明珠", r"明珠"]),
    ("TVB新闻台",       [r"tvb\s*news", r"tvb新闻", r"tvb新聞"]),
    ("无线财经•资讯台", [r"无线财经", r"無線財經", r"tvb\s*finance", r"tvb财经", r"财经资讯台", r"財經資訊台"]),
    # 凤凰卫视
    ("凤凰卫视中文台",  [r"凤凰卫视中文", r"鳳凰衛視中文", r"凤凰中文台", r"鳳凰中文台",
                         r"凤凰中文(?!资讯|資訊|电影|電影)", r"鳳凰中文(?!资讯|資訊|电影|電影)",
                         r"phoenix\s*chinese", r"phoenix\s*ch(?:inese)?tv",
                         r"凤凰卫视$", r"鳳凰衛視$", r"凤凰台$"]),
    ("凤凰卫视资讯台",  [r"凤凰资讯", r"鳳凰資訊", r"phoenix\s*info",
                         r"凤凰卫视资讯", r"鳳凰衛視資訊",
                         r"凤凰中文.{0,4}资讯", r"鳳凰中文.{0,4}資訊"]),
    ("凤凰卫视电影台",  [r"凤凰电影", r"鳳凰電影", r"phoenix\s*movie",
                         r"凤凰卫视电影", r"鳳凰衛視電影"]),
    ("凤凰卫视香港台",  [r"凤凰.{0,4}香港台", r"鳳凰.{0,4}香港台",
                         r"凤凰卫视香港", r"鳳凰衛視香港", r"鳳凰香港"
                         r"phoenix\s*hong\s*kong", r"phoenix\s*hk"]),
    # 香港电台（RTHK）
    ("香港电台31台",    [r"rthk\s*31", r"香港电台31", r"香港電台31", r"港台31"]),
    ("香港电台32台",    [r"rthk\s*32", r"香港电台32", r"香港電台32", r"港台32"]),
    ("香港电台33台",    [r"rthk\s*33", r"香港电台33", r"香港電台33", r"港台33"]),
    ("香港电台",        [r"rthk(?!\s*3[0-9])", r"香港电台(?!3[0-9])", r"香港電台(?!3[0-9])", r"港台(?!3[0-9])"]),
    # ViuTV / 奇妙电视
    ("ViuTV",           [r"viu\s*tv(?!\+)", r"viutv(?!\+)"]),
    ("ViuTV+",          [r"viu\s*tv\+", r"viutv\+"]),
    ("奇妙电视",        [r"奇妙电视", r"奇妙電視", r"free\s*hk\s*tv", r"freehktv"]),
    # 收费频道 / 有线电视
    ("Now新闻台",       [r"now\s*news", r"now新闻", r"now新聞"]),
    ("Now财经台",       [r"now\s*finance", r"now财经", r"now財經"]),
    ("Now劲爆体育",     [r"now\s*sport", r"now劲爆", r"now勁爆"]),
    ("有线新闻台",      [r"有线新闻", r"有線新聞", r"cable\s*news"]),
    ("有线财经资讯台",  [r"有线财经", r"有線財經", r"cable\s*finance"]),
    # 英文/国际频道
    ("亚洲电视经典台",  [r"atv\s*classic", r"亚视经典", r"亞視經典"]),
    ("星空卫视",        [r"星空卫视", r"星空衛視", r"star\s*chinese\s*channel",
                         r"xing\s*kong", r"star\s*chinese(?!\s*movie)"]),
    ("星空音乐",        [r"星空音乐", r"星空音樂",
                         r"channel\s*v(?!\w)", r"channel\[v\]", r"channelv", r"channel v"]),
    ("Star World",      [r"star\s*world"]),
    ("CNN国际",         [r"cnn\s*(international|asia|hk|hong\s*kong)"]),
    ("BBC World",       [r"bbc\s*world"]),
    ("NHK World",       [r"nhk\s*world"]),
    # 其他知名香港频道
    ("TVB星河台",       [r"tvb\s*star", r"星河台", r"tvb星河"]),
    ("TVB J2",          [r"tvb\s*j2", r"j2台", r"j2\s*channel"]),
    ("东方卫视香港台",  [r"东方卫视.{0,4}香港", r"東方衛視.{0,4}香港"]),
    ("本港台",          [r"本港台", r"atv\s*home", r"亚视本港", r"亞視本港"]),
    ("国际台",          [r"国际台(?!.*cctv)", r"國際台(?!.*cctv)", r"atv\s*world"]),
    ("香港卫视",        [r"香港卫视", r"香港衛視", r"hkstv"]),
]

# ============================================================
# 解析函数
# ============================================================

def build_matchers():
    """预编译所有正则"""
    matchers = []
    for ch_name, patterns in HK_CHANNELS:
        compiled = [re.compile(p, re.IGNORECASE) for p in patterns]
        matchers.append((ch_name, compiled))
    return matchers

MATCHERS = build_matchers()

def match_channel(title: str):
    """
    返回匹配到的标准频道名称；若不匹配则返回 None。
    title 为 #EXTINF 行中的频道名。
    """
    for ch_name, compiled_patterns in MATCHERS:
        for pat in compiled_patterns:
            if pat.search(title):
                return ch_name
    return None

def extract_channel_name(extinf: str) -> str:
    """从 #EXTINF 行提取频道名称（逗号后的内容）"""
    if "," in extinf:
        return extinf.split(",", 1)[1].strip()
    return extinf

def parse_file_line_by_line(filepath: str):
    """
    逐行读取文件的通用解析器，支持 m3u、m3u8、txt 格式
    返回 list of (extinf_line, url)
    """
    entries = []
    ext = os.path.splitext(filepath)[1].lower()
    
    try:
        with open(filepath, encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()
    except Exception as e:
        print(f"❌ 读取文件失败 {filepath}: {e}")
        return []
    
    # 检测是否为 m3u 格式
    is_m3u_format = any(line.upper().startswith("#EXTINF") for line in lines[:10])
    
    if ext in (".m3u", ".m3u8") or is_m3u_format:
        # m3u 格式解析
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            if line.upper().startswith("#EXTINF"):
                extinf = line
                # 查找下一行非空行作为 URL
                j = i + 1
                while j < len(lines):
                    next_line = lines[j].strip()
                    if next_line and not next_line.startswith("#"):
                        url = next_line
                        entries.append((extinf, url))
                        i = j + 1
                        break
                    j += 1
                else:
                    i += 1
            else:
                i += 1
    else:
        # txt 格式解析
        for line in lines:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            # 支持 "频道名,URL" 或 "频道名|URL" 格式
            for sep in [",", "|", "\t"]:
                if sep in line:
                    parts = line.split(sep, 1)
                    if len(parts) == 2:
                        name, url = parts[0].strip(), parts[1].strip()
                        if url.startswith(("http", "rtmp", "rtp")):
                            extinf = f'#EXTINF:-1,{name}'
                            entries.append((extinf, url))
                            break
    
    return entries

def read_file_with_encoding(filepath: str) -> str:
    """尝试多种编码读取文件"""
    for enc in ["utf-8", "utf-8-sig", "gbk", "gb18030", "big5"]:
        try:
            with open(filepath, "r", encoding=enc, errors="strict") as f:
                return f.read()
        except (UnicodeDecodeError, LookupError):
            continue
    # 最后用 ignore 模式
    with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
        return f.read()

# ============================================================
# 主流程
# ============================================================

def main():
    # 使用相对于工作目录的路径
    input_dir = "sources"
    output_dir = os.path.join("sources", "temp")
    output_path = os.path.join(output_dir, "香港频道.m3u")
    
    # 确保输出目录存在
    os.makedirs(output_dir, exist_ok=True)
    
    print(f"📁 当前工作目录: {os.getcwd()}")
    print(f"📁 源文件目录: {input_dir}")
    print(f"📁 输出目录: {output_dir}")

    # 检查源目录是否存在
    if not os.path.exists(input_dir):
        print(f"❌ 源目录不存在: {input_dir}")
        return

    # 搜集所有 m3u / txt 文件
    files = []
    for pattern in ["src-*.m3u", "src-*.m3u8", "src-*.txt"]:
        files.extend(glob.glob(os.path.join(input_dir, pattern)))
    
    # 排除 temp 目录中的文件
    files = [f for f in files if not f.startswith(os.path.join(input_dir, "temp"))]
    # 排除输出文件本身（如果存在）
    files = [f for f in files if os.path.abspath(f) != os.path.abspath(output_path)]

    if not files:
        print(f"⚠️  在 {input_dir} 中未找到任何 m3u/txt 文件！")
        return

    print(f"\n📂 共找到 {len(files)} 个源文件：")
    for f in files:
        print(f"   {os.path.basename(f)}")

    # 按标准名称分组存储：{ch_name: [(extinf, url), ...]}
    channel_order = [ch[0] for ch in HK_CHANNELS]  # 保持排序
    channel_data: dict[str, list] = {name: [] for name in channel_order}
    seen_urls: set[str] = set()

    for filepath in files:
        try:
            entries = parse_file_line_by_line(filepath)
        except Exception as e:
            print(f"❌ 解析 {filepath} 失败：{e}")
            continue

        for extinf, url in entries:
            ch_title = extract_channel_name(extinf)
            std_name = match_channel(ch_title)
            if std_name is None:
                continue
            # URL 去重
            if url in seen_urls:
                continue
            seen_urls.add(url)
            # 重写 extinf，统一格式，加 group-title
            attrs = re.findall(r'(\w[\w-]*)="([^"]*)"', extinf)
            attr_str = ""
            for k, v in attrs:
                if k.lower() not in ("group-title",):
                    attr_str += f' {k}="{v}"'
            new_extinf = f'#EXTINF:-1{attr_str} group-title="香港频道" tvg-name="{std_name}",{std_name}'
            channel_data[std_name].append((new_extinf, url))

    # 统计结果
    total_links = sum(len(v) for v in channel_data.values())
    found_channels = [(name, links) for name, links in channel_data.items() if links]

    print(f"\n📊 提取结果：")
    for name, links in found_channels:
        print(f"   ✅ {name}：{len(links)} 条链接")
    for name, links in channel_data.items():
        if not links:
            print(f"   ⚠️ {name}：未找到")

    if total_links == 0:
        print("❌ 未提取到任何频道，请检查源文件内容与频道名称是否匹配。")
        return

    # 组装 m3u 文件
    lines = ["#EXTM3U"]
    for ch_name in channel_order:
        for extinf, url in channel_data[ch_name]:
            lines.append(extinf)
            lines.append(url)

    output_content = "\n".join(lines) + "\n"

    try:
        with open(output_path, "w", encoding="utf-8-sig") as f:
            f.write(output_content)
        print(f"\n🎉 完成！共匹配到 {len(found_channels)} 个香港频道，{total_links} 条有效链接")
        print(f"📄 输出文件：{output_path}")
        print(f"📁 文件大小：{os.path.getsize(output_path)} 字节")
    except Exception as e:
        print(f"❌ 写入输出文件失败：{e}")

if __name__ == "__main__":
    main()
