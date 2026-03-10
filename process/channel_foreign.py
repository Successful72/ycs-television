#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
从 M3U / TXT 格式的 IPTV 订阅文件中提取 CGTN 外语频道及 CETV 教育频道，
生成新的 M3U 文件，组名称为"央视其他频道"。
输出到 ./sources/temp 目录
"""

import os
import re
import glob
from typing import Dict, List, Optional, Tuple

# ── 目标频道定义（顺序即最终输出顺序）──────────────────────────
# 每个条目：(标准名称, {"aliases": [...], "patterns": [...]})
# aliases : 精确匹配列表（大小写不敏感），优先级高于正则
# patterns: 正则匹配列表，作为 aliases 未命中时的后备
CHANNEL_DEFS: List[Tuple[str, Dict]] = [
    (
        "CGTN-英语",
        {
            "aliases": ["CGTN英语", "CGTN英语新闻"],
            "patterns": [
                r"CGTN[-_\s]*(?:英语|English|英文)(?!.*(?:纪录|Doc|Record))",
                r"CGTN(?!.*(?:西|法|阿|俄|纪|Doc|Span|Fran|Arab|Rus|Record))[-_\s]*$",
            ],
        },
    ),
    (
        "CGTN-英语纪录",
        {
            "aliases": [],
            "patterns": [
                r"CGTN[-_\s]*(?:英语[-_\s]*)?(?:纪录|Documentary|Doc(?:umentary)?|Record)",
                r"CGTN[-_\s]*Doc",
            ],
        },
    ),
    (
        "CGTN-俄语",
        {
            "aliases": ["CGTN俄语", "CGTN俄罗斯语"],
            "patterns": [
                r"CGTN[-_\s]*(?:俄语|俄文|俄|Russian|Rus)",
            ],
        },
    ),
    (
        "CGTN-西班牙语",
        {
            "aliases": [],
            "patterns": [
                r"CGTN[-_\s]*(?:西班牙语?|西语|西文|Spanish|Span|Español|Espanol)",
            ],
        },
    ),
    (
        "CGTN-法语",
        {
            "aliases": [],
            "patterns": [
                r"CGTN[-_\s]*(?:法语|法文|French|Fran[cç]ais|Fran)",
            ],
        },
    ),
    (
        "CGTN-阿拉伯语",
        {
            "aliases": [],
            "patterns": [
                r"CGTN[-_\s]*(?:阿拉伯语?|阿语|阿文|Arabic|Arab)",
            ],
        },
    ),
    (
        "CETV-1",
        {
            "aliases": ["CETV-1", "CETV1", "CETV1中国教育", "CETV1 中国教育", "中国教育1", "中国教育1HD"],
            "patterns": [],
        },
    ),
    (
        "CETV-2",
        {
            "aliases": ["CETV-2", "CETV2", "CETV2中国教育", "CETV2 中国教育", "中国教育2", "中国教育2HD"],
            "patterns": [],
        },
    ),
    (
        "CETV-3",
        {
            "aliases": ["CETV-3", "CETV3", "CETV3中国教育", "CETV3 中国教育", "中国教育3", "中国教育3HD"],
            "patterns": [],
        },
    ),
    (
        "CETV-4",
        {
            "aliases": ["CETV-4", "CETV4", "CETV4中国教育", "CETV4 中国教育", "中国教育4", "中国教育4HD"],
            "patterns": [],
        },
    ),
    (
        "CETV早教",
        {
            "aliases": ["CETV早教", "CETV早期教育", "早期教育"],
            "patterns": [],
        },
    ),
]

# 预编译：aliases 统一转小写，patterns 编译为正则对象
COMPILED_DEFS: List[Tuple[str, Dict]] = [
    (
        name,
        {
            "aliases": [a.lower() for a in matchers["aliases"]],
            "patterns": [re.compile(pat, re.IGNORECASE) for pat in matchers["patterns"]],
        },
    )
    for name, matchers in CHANNEL_DEFS
]


def classify_channel(raw_name: str) -> Optional[str]:
    """
    返回标准频道名，无法识别则返回 None。
    优先精确匹配 aliases（大小写不敏感），再尝试正则 patterns。
    """
    name = raw_name.strip()
    name_lower = name.lower()
    for std_name, matchers in COMPILED_DEFS:
        if name_lower in matchers["aliases"]:
            return std_name
        for pat in matchers["patterns"]:
            if pat.search(name):
                return std_name
    return None


# ── 解析辅助函数 ─────────────────────────────────────────────────

def _extract_extinf_name(line: str) -> str:
    """从 #EXTINF 行中提取频道名称（tvg-name 优先，否则取逗号后内容）。"""
    m = re.search(r'tvg-name="([^"]*)"', line, re.IGNORECASE)
    if m:
        return m.group(1)
    cm = re.search(r",(.+)$", line)
    return cm.group(1).strip() if cm else ""


def _find_next_url(lines: List[str], start: int) -> Tuple[Optional[str], int]:
    """
    从 start 行开始向后找到第一条非注释、非空的 URL。
    返回 (url, next_index)；未找到则返回 (None, start + 1)。
    """
    j = start
    while j < len(lines):
        candidate = lines[j].strip()
        if candidate and not candidate.startswith("#"):
            return candidate, j + 1
        j += 1
    return None, start + 1


def parse_file_line_by_line(filepath: str) -> List[Tuple[str, str]]:
    """
    逐行读取文件的通用解析器，支持 m3u、m3u8、txt 格式。
    返回 [(raw_name, url), ...] 列表。
    """
    results: List[Tuple[str, str]] = []
    ext = os.path.splitext(filepath)[1].lower()

    try:
        with open(filepath, encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
    except Exception as e:
        print(f"❌ 读取文件失败 {filepath}: {e}")
        return []

    # 检测是否为 M3U 格式：
    # 1. 扩展名为 .m3u/.m3u8，或
    # 2. 文件头以 #EXTM3U 开头，或
    # 3. 前 20 行中出现 #EXTINF
    is_m3u_format = (
        ext in (".m3u", ".m3u8")
        or (bool(lines) and lines[0].strip().upper().startswith("#EXTM3U"))
        or any(line.startswith("#EXTINF") for line in lines[:20])
    )

    if is_m3u_format:
        # ── M3U 格式解析 ─────────────────────────────────────────
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            if line.startswith("#EXTINF"):
                raw_name = _extract_extinf_name(line)
                url, i = _find_next_url(lines, i + 1)
                if url:
                    results.append((raw_name, url))
            else:
                i += 1
    else:
        # ── TXT 格式解析 ─────────────────────────────────────────
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            if not line or line.startswith("#genre#"):
                i += 1
                continue

            if line.startswith("#EXTINF"):
                # TXT 文件中偶尔也会混入 M3U 格式行，统一处理
                raw_name = _extract_extinf_name(line)
                url, i = _find_next_url(lines, i + 1)
                if url:
                    results.append((raw_name, url))
            elif "," in line:
                # 格式：频道名,URL  或  分组名,#genre#
                parts = line.split(",", 1)
                raw_name = parts[0].strip()
                url = parts[1].strip()
                if url.lower().startswith(("http", "rtsp", "rtp", "udp", "igmp")):
                    results.append((raw_name, url))
                i += 1
            else:
                i += 1

    return results


def main() -> None:
    input_dir = "sources"
    output_dir = os.path.join("sources", "temp")
    output_path = os.path.join(output_dir, "央视其他频道.m3u")

    os.makedirs(output_dir, exist_ok=True)

    print(f"📁 当前工作目录: {os.getcwd()}")
    print(f"📁 源文件目录: {input_dir}")
    print(f"📁 输出目录: {output_dir}")

    if not os.path.exists(input_dir):
        print(f"❌ 源目录不存在: {input_dir}")
        return

    # 按标准名称收集 URL（去重），保持第一次出现的顺序
    collected: Dict[str, List[str]] = {name: [] for name, _ in CHANNEL_DEFS}
    seen_urls: set = set()

    files: List[str] = []
    for pattern in ["src-*.m3u", "src-*.m3u8", "src-*.txt"]:
        files.extend(glob.glob(os.path.join(input_dir, pattern)))
    # 排除 temp 子目录中的文件
    files = [f for f in files if not f.startswith(os.path.join(input_dir, "temp"))]

    # 按文件名中的自然数排序（src-1, src-2, ..., src-10 而非字典序）
    def _natural_key(path: str) -> List[int]:
        return [int(n) for n in re.findall(r"\d+", os.path.basename(path))]

    files.sort(key=_natural_key)

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

    # 统计结果
    total = sum(len(v) for v in collected.values())
    print("\n📊 提取结果：")
    for name, urls in collected.items():
        status = f"✅ {len(urls)} 条" if urls else "⚠️  未找到"
        print(f"   {name}: {status}")

    if total == 0:
        print("\n⚠️ 未提取到任何频道，请检查源文件中的频道命名是否包含相关关键字。")
        return

    # 写出 M3U
    group = "央视其他频道"
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
