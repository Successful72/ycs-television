# -*- coding: utf-8 -*-
"""
提取 m3u/txt 文件中的澳门频道，组装成新 m3u 文件到 sources/temp 目录
"""

import os
import re
import glob
from pathlib import Path

# ============================================================
# 澳门频道定义（按名气从大到小排列，每项：(标准名, 匹配关键词列表)）
# ============================================================
MACAU_CHANNELS = [
    ("澳门莲花卫视", [
        r"蓮花衛視", r"莲花卫视", r"蓮花", r"莲花",
        r"lotus\s*tv", r"lotustv", r"LHTV", r"LTV[\-_]?MO"
    ]),
    ("澳门澳视本澳台", [
        r"本澳台", r"本澳頻道", r"澳視本澳",
        r"TDM[\s\-_]?CH[\s\-_]?1", r"TDM[\s\-_]?1",
        r"TDM1", r"澳門電視台[\s\-_]?1", r"澳视本澳"
    ]),
    ("澳门澳视综合台", [
        r"澳視綜合", r"綜合台", r"澳视综合",
        r"TDM[\s\-_]?CH[\s\-_]?2", r"TDM[\s\-_]?2",
        r"TDM2", r"澳門電視台[\s\-_]?2"
    ]),
    ("澳门澳视体育台", [
        r"澳視體育", r"澳视体育", r"體育台",
        r"TDM[\s\-_]?Sport", r"TDM[\s\-_]?體育",
        r"TDM[\s\-_]?体育", r"TDM[\s\-_]?CH[\s\-_]?3", r"TDM3"
    ]),
    ("澳门澳视澳门台", [
        r"澳視澳門", r"澳门台", r"澳視澳門台",
        r"TDM[\s\-_]?Macau", r"TDM[\s\-_]?澳門",
        r"TDM[\s\-_]?CH[\s\-_]?4", r"TDM4"
    ]),
    ("澳门葡语台", [
        r"葡語台", r"葡语台", r"澳視葡語",
        r"TDM[\s\-_]?(Por|PT|葡語|葡语)",
        r"Canal\s*Macau", r"RTP[\s\-_]?Macau"
    ]),
    ("澳门国际台", [
        r"澳門國際", r"澳门国际", r"國際台",
        r"TDM[\s\-_]?Int", r"TDM[\s\-_]?國際",
        r"TDM[\s\-_]?CH[\s\-_]?5", r"TDM5"
    ]),
    ("澳门新闻台", [
        r"澳門新聞", r"澳门新闻", r"澳視新聞",
        r"TDM[\s\-_]?News", r"TDM[\s\-_]?新聞"
    ]),
    ("澳广视资讯台", [
        r"澳廣視", r"澳广视", r"TDM[\s\-_]?資訊",
        r"澳門資訊", r"澳门资讯台", r"TDM[\s\-_]?Info"
    ]),
    ("澳门旅游卫视", [
        r"旅遊衛視", r"旅游卫视",
        r"Macau[\s\-_]?Tourism[\s\-_]?TV",
        r"澳門旅遊台", r"澳门旅游"
    ]),
    ("澳门科教台", [
        r"澳門科教", r"科教台", r"澳门科教",
        r"TDM[\s\-_]?(科教|EDU|Education)"
    ]),
    ("凤凰卫视澳门台", [
        r"鳳凰.*澳門", r"凤凰.*澳门",
        r"Phoenix.*Macau", r"澳門鳳凰",
        r"鳳凰澳門", r"phoenix.*macao"
    ]),
    ("澳门有线新闻台", [
        r"澳門有線", r"澳门有线",
        r"Macau[\s\-_]?Cable", r"有線新聞.*澳門"
    ]),
    ("澳门娱乐台", [
        r"澳門娛樂", r"澳门娱乐",
        r"TDM[\s\-_]?Ent", r"TDM[\s\-_]?娛樂",
        r"Macau[\s\-_]?Ent"
    ]),
    ("澳门文化台", [
        r"澳門文化", r"澳门文化", r"文化台",
        r"TDM[\s\-_]?Culture", r"TDM[\s\-_]?文化",
        r"Macau[\s\-_]?Culture"
    ]),
    ("澳门体育台", [
        r"澳門體育", r"澳门体育",
        r"Macau[\s\-_]?Sport",
        r"体育.*澳門", r"體育.*澳门"
    ]),
    ("澳门卫视", [
        r"澳門衛視(?!.*蓮花)", r"澳门卫视(?!.*莲花)",
        r"Macau[\s\-_]?TV", r"MacauTV",
        r"MCTV", r"MO[\s\-_]?TV"
    ]),
    ("澳门电视台", [
        r"澳門電視台(?!\s*[12345])", r"澳门电视台(?!\s*[12345])",
        r"Macau[\s\-_]?Television",
        r"TDM(?![\s\-_]?[CH12345Sport體育葡語Int News資訊文化娛樂])",
    ]),
    ("澳门综艺台", [
        r"澳門綜藝", r"澳门综艺", r"綜藝台",
        r"Macau[\s\-_]?Variety"
    ]),
    ("澳门电影台", [
        r"澳門電影", r"澳门电影", r"電影台",
        r"Macau[\s\-_]?Movie", r"Macau[\s\-_]?Cinema"
    ]),
    ("澳门儿童台", [
        r"澳門兒童", r"澳门儿童", r"兒童台",
        r"Macau[\s\-_]?Kids", r"TDM[\s\-_]?兒童"
    ]),
    ("澳门财经台", [
        r"澳門財經", r"澳门财经",
        r"Macau[\s\-_]?Finance", r"TDM[\s\-_]?財經"
    ]),
    ("澳门生活台", [
        r"澳門生活", r"澳门生活",
        r"Macau[\s\-_]?Life", r"TDM[\s\-_]?生活"
    ]),
    ("澳门美食台", [
        r"澳門美食", r"澳门美食",
        r"Macau[\s\-_]?Food", r"TDM[\s\-_]?美食"
    ]),
    ("澳门时尚台", [
        r"澳門時尚", r"澳门时尚",
        r"Macau[\s\-_]?Fashion"
    ]),
    ("澳门教育台", [
        r"澳門教育(?!.*科)", r"澳门教育",
        r"Macau[\s\-_]?Education", r"TDM[\s\-_]?教育"
    ]),
    ("澳门健康台", [
        r"澳門健康", r"澳门健康",
        r"Macau[\s\-_]?Health", r"TDM[\s\-_]?健康"
    ]),
    ("澳门音乐台", [
        r"澳門音樂", r"澳门音乐",
        r"Macau[\s\-_]?Music", r"TDM[\s\-_]?音樂"
    ]),
    ("澳门粤语台", [
        r"澳門粵語", r"澳门粤语",
        r"Macau[\s\-_]?Cantonese", r"TDM[\s\-_]?粵語"
    ]),
    ("澳门普通话台", [
        r"澳門普通話", r"澳门普通话",
        r"Macau[\s\-_]?Mandarin", r"TDM[\s\-_]?普通話"
    ]),
    ("濠江卫视", [
        r"濠江衛視", r"濠江卫视", r"濠江",
        r"Haojiang[\s\-_]?TV", r"HJ[\s\-_]?TV"
    ]),
    ("澳门公共频道", [
        r"澳門公共", r"澳门公共",
        r"Macau[\s\-_]?Public", r"公共頻道.*澳"
    ]),
    ("澳门国际中文台", [
        r"澳門國際中文", r"澳门国际中文",
        r"Macau[\s\-_]?Chinese[\s\-_]?Int"
    ]),
    ("大湾区卫视澳门", [
        r"大灣區.*澳", r"大湾区.*澳", r"澳門.*大灣區",
        r"GBA[\s\-_]?TV.*[Mm]acau", r"GBATV"
    ]),
    ("澳门TDM频道", [
        r"TDM[\s\-_]?Macau", r"TDM[\s\-_]?澳門頻道",
        r"澳門TDM"
    ]),
    ("澳亚卫视", [
        r"澳亞衛視", r"澳亚卫视",
        r"Macau[\s\-_]?Asia[\s\-_]?TV",
        r"MATV", r"澳亞"
    ]),
]

# ============================================================
# 通用澳门相关兜底正则（命中后用原始频道名，排在已命名的后面）
# ============================================================
MACAU_FALLBACK_PATTERNS = [
    re.compile(r'澳門|澳门|Macau|Macao|MACAO|MACAU|TDM[\s\-_]', re.IGNORECASE),
]

# 繁体 → 简体 对照表
_T2S = str.maketrans(
    "門蓮視衛頻體娛樂綜藝兒財經時尚語臺灣區亞鳳凰濠華際聞",
    "门莲视卫频体娱乐综艺儿财经时尚语台湾区亚凤凰濠华际闻"
)

def to_simplified(text: str) -> str:
    """将常见繁体字转换为简体"""
    return text.translate(_T2S)

# 预编译各频道正则
COMPILED_CHANNELS = []
for ch_name, patterns in MACAU_CHANNELS:
    compiled = [re.compile(p, re.IGNORECASE) for p in patterns]
    COMPILED_CHANNELS.append((ch_name, compiled))

def match_channel(extinf_line: str) -> str | None:
    """
    返回匹配到的标准频道名，或 None（不是澳门频道）。
    """
    # 提取 tvg-name 和顯示名（逗號後）
    name_match = re.search(r'tvg-name="([^"]*)"', extinf_line, re.IGNORECASE)
    tvg_name = name_match.group(1) if name_match else ""
    display_name = extinf_line.rsplit(",", 1)[-1].strip() if "," in extinf_line else ""
    search_text = f"{tvg_name} {display_name}"

    # 先逐频道精确匹配
    for ch_name, patterns in COMPILED_CHANNELS:
        for pat in patterns:
            if pat.search(search_text):
                return ch_name

    # 兜底：只要包含澳門/Macau 等关键词，原始名转简体后返回
    for pat in MACAU_FALLBACK_PATTERNS:
        if pat.search(search_text):
            raw = display_name.strip() or tvg_name.strip() or "澳门频道"
            return to_simplified(raw)

    return None

def parse_file_line_by_line(filepath: str):
    """
    逐行读取文件的通用解析器，支持 m3u、m3u8、txt 格式
    返回 list of (extinf_line, url)
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
        # m3u 格式解析
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            if line.upper().startswith("#EXTINF"):
                extinf = line
                # 找到下一個非空行
                j = i + 1
                while j < len(lines) and not lines[j].strip():
                    j += 1
                if j < len(lines):
                    url = lines[j].strip()
                    if url and not url.startswith("#"):
                        entries.append((extinf, url))
                        i = j + 1
                        continue
            i += 1
    else:
        # txt 格式解析
        for line in lines:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            # 格式 1：频道名,url
            if "," in line:
                parts = line.split(",", 1)
                ch_name = parts[0].strip()
                url = parts[1].strip()
                if url.startswith(("http", "rtmp", "rtp")):
                    extinf = f'#EXTINF:-1 tvg-name="{ch_name}",{ch_name}'
                    entries.append((extinf, url))
    return entries

def main():
    # 使用相对于工作目录的路径
    input_dir = "sources"
    output_dir = os.path.join("sources", "temp")
    output_path = os.path.join(output_dir, "澳门频道.m3u")
    
    # 确保输出目录存在
    os.makedirs(output_dir, exist_ok=True)
    
    print(f"📁 当前工作目录: {os.getcwd()}")
    print(f"📁 源文件目录: {input_dir}")
    print(f"📁 输出目录: {output_dir}")

    # 检查源目录是否存在
    if not os.path.exists(input_dir):
        print(f"❌ 源目录不存在: {input_dir}")
        return

    # 蒐集所有 m3u 和 txt 文件
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

    print(f"\n📂 共找到 {len(files)} 個文件：")
    for f in files:
        print(f"   {os.path.basename(f)}")

    # 逐文件解析 → 按标准频道名分类
    channel_data: dict[str, dict[str, str]] = {}

    for filepath in files:
        try:
            entries = parse_file_line_by_line(filepath)
        except Exception as e:
            print(f"❌ 解析 {filepath} 失败：{e}")
            continue

        for extinf, url in entries:
            ch_name = match_channel(extinf)
            if ch_name is None:
                continue
            if ch_name not in channel_data:
                channel_data[ch_name] = {}
            if url not in channel_data[ch_name]:
                channel_data[ch_name][url] = extinf

    if not channel_data:
        print("❌ 未找到任何澳门频道！")
        return

    # ============================================================
    # 按名气排序输出（MACAU_CHANNELS 顺序优先，兜底频道放末尾）
    # ============================================================
    ordered_names = [ch[0] for ch in MACAU_CHANNELS]

    def sort_key(name):
        try:
            return ordered_names.index(name)
        except ValueError:
            return len(ordered_names)  # 兜底频道排最后

    sorted_channels = sorted(channel_data.keys(), key=sort_key)

    # ============================================================
    # 組裝 m3u
    # ============================================================
    lines_out = ["#EXTM3U"]
    total_links = 0

    print("\n📋 提取结果：")
    for ch_name in sorted_channels:
        url_dict = channel_data[ch_name]
        print(f"   ✅ {ch_name}  ({len(url_dict)} 个链接)")
        for url, extinf in url_dict.items():
            # 統一修改 group-title 和 tvg-name
            new_extinf = re.sub(r'group-title="[^"]*"', '', extinf)
            new_extinf = re.sub(r'tvg-name="[^"]*"', '', new_extinf)
            new_extinf = re.sub(r'\s{2,}', ' ', new_extinf).strip()
            insert = f'tvg-name="{ch_name}" group-title="澳门频道"'
            new_extinf = new_extinf.replace("#EXTINF:-1", f"#EXTINF:-1 {insert}", 1)
            if f"#EXTINF:-1 {insert}" not in new_extinf:
                new_extinf = re.sub(
                    r'(#EXTINF:\s*-?\d+)',
                    rf'\1 {insert}',
                    new_extinf, count=1
                )
            # 修正逗號後的顯示名
            if "," in new_extinf:
                new_extinf = re.sub(r',.*$', f',{ch_name}', new_extinf)
            else:
                new_extinf += f",{ch_name}"

            lines_out.append(new_extinf)
            lines_out.append(url)
            total_links += 1

    m3u_content = "\n".join(lines_out) + "\n"

    try:
        with open(output_path, "w", encoding="utf-8-sig") as f:
            f.write(m3u_content)
        print(f"\n🎉 完成！共找到 {len(sorted_channels)} 个澳门频道，{total_links} 条播放链接")
        print(f"📄 输出文件：{output_path}")
        print(f"📁 文件大小：{os.path.getsize(output_path)} 字节")
    except Exception as e:
        print(f"❌ 写入文件失败: {e}")

if __name__ == "__main__":
    main()
