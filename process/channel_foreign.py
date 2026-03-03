#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
从 M3U / TXT 格式的 IPTV 订阅文件中提取 CGTN 外语频道，
生成新的 M3U 文件，组名称为"央视外语频道"。
输出到 ./sources/temp 目录
"""

import os
import re
import glob

# ── 目标频道定义（顺序即最终输出顺序）──────────────────────────
# 每个条目：(标准名称, [匹配规则列表])
# 规则按优先级从高到低排列，第一条命中即归入该频道
CHANNEL_DEFS = [
    (
        "CGTN-英语",
        [
            # 明确排除"纪录"的英语
            r"CGTN[-_\s]*(?:英语|English|英文)(?!.*(?:纪录|Doc|Record))",
            r"CGTN(?!.*(?:西|法|阿|俄|纪|Doc|Span|Fran|Arab|Rus|Record))[-_\s]*$",
        ],
    ),
    (
        "CGTN-英语纪录",
        [
            r"CGTN[-_\s]*(?:英语[-_\s]*)?(?:纪录|Documentary|Doc(?:umentary)?|Record)",
            r"CGTN[-_\s]*Doc",
        ],
    ),
    (
        "CGTN-俄语",
        [
            r"CGTN[-_\s]*(?:俄语|俄文|俄|Russian|Rus)",
        ],
    ),
    (
        "CGTN-西班牙语",
        [
            r"CGTN[-_\s]*(?:西班牙语?|西语|西文|Spanish|Span|Español|Espanol)",
        ],
    ),
    (
        "CGTN-法语",
        [
            r"CGTN[-_\s]*(?:法语|法文|French|Fran[cç]ais|Fran)",
        ],
    ),
    (
        "CGTN-阿拉伯语",
        [
            r"CGTN[-_\s]*(?:阿拉伯语?|阿语|阿文|Arabic|Arab)",
        ],
    ),
]

# 预编译所有规则
COMPILED_DEFS = [
    (name, [re.compile(pat, re.IGNORECASE) for pat in pats])
    for name, pats in CHANNEL_DEFS
]


def classify_channel(raw_name: str):
    """返回标准频道名，无法识别则返回 None。"""
    name = raw_name.strip()
    for std_name, patterns in COMPILED_DEFS:
        for pat in patterns:
            if pat.search(name):
                return std_name
    return None


def parse_file_line_by_line(filepath: str):
    """
    逐行读取文件的通用解析器，支持 m3u、m3u8、txt 格式
    """
    results = []  # 列表元素为 (raw_name, url)
    ext = os.path.splitext(filepath)[1].lower()
    
    try:
        with open(filepath, encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
    except Exception as e:
        print(f"❌ 读取文件失败 {filepath}: {e}")
        return []
    
    # 检测是否为 m3u 格式
    is_m3u_format = any(line.startswith("#EXTINF") for line in lines[:10])
    
    if ext in (".m3u", ".m3u8") or is_m3u_format:
        # m3u 格式解析
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            if line.startswith("#EXTINF"):
                # 提取 tvg-name 或逗号后的名称
                m = re.search(r'tvg-name="([^"]*)"', line, re.IGNORECASE)
                if m:
                    raw_name = m.group(1)
                else:
                    # 逗号之后的部分
                    cm = re.search(r",(.+)$", line)
                    raw_name = cm.group(1).strip() if cm else ""
                
                # 查找下一行非空行作为 URL
                j = i + 1
                while j < len(lines):
                    next_line = lines[j].strip()
                    if next_line and not next_line.startswith("#"):
                        url = next_line
                        if url and not url.startswith("#"):
                            results.append((raw_name, url))
                            i = j + 1
                            break
                    j += 1
                else:
                    i += 1
            else:
                i += 1
    else:
        # txt 格式解析（支持多种格式）
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            if not line or line.startswith("#genre#"):
                i += 1
                continue
            
            if line.startswith("#EXTINF"):
                m = re.search(r'tvg-name="([^"]*)"', line, re.IGNORECASE)
                raw_name = m.group(1) if m else ""
                if not raw_name:
                    cm = re.search(r",(.+)$", line)
                    raw_name = cm.group(1).strip() if cm else ""
                
                j = i + 1
                while j < len(lines):
                    next_line = lines[j].strip()
                    if next_line and not next_line.startswith("#"):
                        url = next_line
                        if url and not url.startswith("#"):
                            results.append((raw_name, url))
                            i = j + 1
                            break
                    j += 1
                else:
                    i += 1
            elif "," in line:
                # 格式：频道名,URL  或  分组名,#genre#
                parts = line.split(",", 1)
                raw_name = parts[0].strip()
                url = parts[1].strip()
                if url and url.lower().startswith(("http", "rtsp", "rtp", "udp", "igmp")):
                    results.append((raw_name, url))
                i += 1
            else:
                i += 1
    
    return results


def main():
    # 使用相对于工作目录的路径
    input_dir = "sources"
    output_dir = os.path.join("sources", "temp")
    output_path = os.path.join(output_dir, "央视外语频道.m3u")
    
    # 确保输出目录存在
    os.makedirs(output_dir, exist_ok=True)
    
    print(f"📁 当前工作目录: {os.getcwd()}")
    print(f"📁 源文件目录: {input_dir}")
    print(f"📁 输出目录: {output_dir}")

    # 检查源目录是否存在
    if not os.path.exists(input_dir):
        print(f"❌ 源目录不存在: {input_dir}")
        return

    # 按标准名称收集 URL（去重），保持第一次出现的顺序
    collected: dict[str, list[str]] = {name: [] for name, _ in CHANNEL_DEFS}
    seen_urls: set[str] = set()

    # 遍历 sources 目录下的 .m3u 和 .txt 文件
    files = []
    for pattern in ["src-*.m3u", "src-*.m3u8", "src-*.txt"]:
        files.extend(glob.glob(os.path.join(input_dir, pattern)))
    
    # 排除 temp 目录中的文件
    files = [f for f in files if not f.startswith(os.path.join(input_dir, "temp"))]

    if not files:
        print(f"⚠️  在 {input_dir} 中未找到任何 .m3u/.m3u8/.txt 文件！")
        return

    print(f"\n📂 共找到 {len(files)} 个订阅文件：")
    for f in files:
        print(f"   {os.path.basename(f)}")

    for filepath in files:
        print(f"正在处理: {os.path.basename(filepath)}")
        
        try:
            entries = parse_file_line_by_line(filepath)
        except Exception as e:
            print(f"❌ 解析 {os.path.basename(filepath)} 失败：{e}")
            continue

        for raw_name, url in entries:
            std_name = classify_channel(raw_name)
            if std_name and url not in seen_urls:
                collected[std_name].append(url)
                seen_urls.add(url)

    # 统计
    total = sum(len(v) for v in collected.values())
    print(f"\n📊 提取结果：")
    for name, urls in collected.items():
        if urls:
            print(f"✅ {name}: {len(urls)} 条")
        else:
            print(f"⚠️ {name}: 未找到")

    if total == 0:
        print("\n⚠️ 未提取到任何频道，请检查源文件中的频道命名是否包含 CGTN 相关关键字。")
        return

    # 写出 M3U
    group = "央视外语频道"
    try:
        with open(output_path, "w", encoding="utf-8-sig") as out:
            out.write("#EXTM3U\n")
            for std_name, urls in collected.items():
                for url in urls:
                    out.write(
                        f'#EXTINF:-1 tvg-name="{std_name}" '
                        f'group-title="{group}",{std_name}\n'
                        f"{url}\n"
                    )
        
        print(f"\n🎉 完成！共提取 {total} 条链接")
        print(f"📄 输出文件：{output_path}")
        print(f"📁 文件大小：{os.path.getsize(output_path)} 字节")
    except Exception as e:
        print(f"❌ 写入文件失败: {e}")


if __name__ == "__main__":
    main()
