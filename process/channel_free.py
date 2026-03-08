#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
从 m3u/txt 格式的 IPTV 订阅文件中提取 CCTV 频道，组装成新的 m3u 文件。
"""

import os
import re
import glob
from collections import defaultdict

# ── 频道定义（顺序即输出顺序）──────────────────────────────────────────────
CHANNEL_ORDER = [
    "CCTV-1", "CCTV-2", "CCTV-3",
    "CCTV-4", "CCTV-4 欧洲", "CCTV-4 美洲",
    "CCTV-5", "CCTV-5+",
    "CCTV-6", "CCTV-7", "CCTV-8", "CCTV-9", "CCTV-10",
    "CCTV-11", "CCTV-12", "CCTV-13", "CCTV-14", "CCTV-15",
    "CCTV-16", "CCTV-17", "CCTV-4K", "CCTV-8K",
]

# ── 每个标准频道的匹配规则 ─────────────────────────────────────────────────
# 格式：(标准名, 正则表达式)
# 注意顺序：越特殊的规则放越前面，防止被宽泛规则吞掉
CHANNEL_PATTERNS = [
    # CCTV-4 欧洲 / 美洲 —— 必须在普通 CCTV-4 之前
    ("CCTV-4 欧洲",  r"cctv[-_\s]?0?4[-_\s]*(欧洲|europe|eur)"),
    ("CCTV-4 美洲",  r"cctv[-_\s]?0?4[-_\s]*(美洲|america|ame)"),
    # CCTV-5+ —— 必须在 CCTV-5 之前
    # 覆盖：CCTV5+ / CCTV-5+ / CCTV5plus / CCTV-5体育赛事 等
    ("CCTV-5+",      r"cctv[-_\s]?0?5\s*(\+|plus|体育赛事)"),
    # CCTV-4K —— 必须在普通 CCTV-4 之前
    # 覆盖：CCTV4K / CCTV-4K / CCTV 4K / CCTV04K / CCTV4超高清 / CCTV-4 UHD 等
    ("CCTV-4K",      r"cctv[-_\s]?0?4\s*k|cctv[-_\s]?0?4[-_\s]*(超高清|uhd)"),
    # CCTV-8K —— 必须在普通 CCTV-8 之前
    # 覆盖：CCTV8K / CCTV-8K / CCTV 8K / CCTV08K / CCTV8超高清 / CCTV-8 UHD 等
    ("CCTV-8K",      r"cctv[-_\s]?0?8\s*k|cctv[-_\s]?0?8[-_\s]*(超高清|uhd)"),
    # 普通数字频道 1-17（用循环生成）
]

# 普通数字频道
# 负向前瞻说明：
#   单数字（1-9）：后面不能紧跟 数字/k/K/+/欧/美，防止误匹配 CCTV10~17、CCTV4K、CCTV5+、CCTV4欧洲 等
#   双数字（10-17）：后面不能紧跟数字，防止误匹配三位数
for _n in range(1, 18):
    _std = f"CCTV-{_n}"
    if _n < 10:
        _pat = rf"cctv[-_\s]?0?{_n}(?![\dkK+欧美])"
    else:
        _pat = rf"cctv[-_\s]?{_n}(?!\d)"
    CHANNEL_PATTERNS.append((_std, _pat))

# 编译正则（不区分大小写）
COMPILED = [(std, re.compile(pat, re.IGNORECASE)) for std, pat in CHANNEL_PATTERNS]

# ── 噪声词（匹配前从频道名中剔除）────────────────────────────────────────
# 可随时在此列表中追加新的噪声词，如：|华数|百视通
_NOISE_PATTERN = re.compile(
    r"咪咕|migu|mgtv",
    re.IGNORECASE,
)


def normalize_name(name: str) -> str:
    """剔除频道名中的噪声词，便于后续正则匹配。"""
    return _NOISE_PATTERN.sub("", name).strip()


def identify_channel(name: str):
    """返回标准频道名，无法识别则返回 None。"""
    name_stripped = normalize_name(name.strip())  # 预处理：剔除噪声词
    for std, regex in COMPILED:
        if regex.search(name_stripped):
            return std
    return None


# ── 解析 m3u 格式 ──────────────────────────────────────────────────────────
def parse_m3u(text: str):
    """
    返回 list of (channel_name, url)
    """
    results = []
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if line.startswith("#EXTINF"):
            # 尝试从 tvg-name 或行尾提取频道名
            tvg_name = re.search(r'tvg-name="([^"]*)"', line, re.IGNORECASE)
            if tvg_name:
                ch_name = tvg_name.group(1)
            else:
                # 取最后一个逗号后面的内容
                comma = line.rfind(",")
                ch_name = line[comma + 1:].strip() if comma != -1 else ""
            # 下一行应该是 URL
            if i + 1 < len(lines):
                url = lines[i + 1].strip()
                if url and url.startswith("http"):
                    results.append((ch_name, url))
                    i += 2
                    continue
        i += 1
    return results


# ── 解析 txt 格式（两种常见格式）─────────────────────────────────────────────
# 格式 A：频道名,URL
# 格式 B：分组标题行（如 "央视频道,#genre#"）后跟 "频道名,URL"
def parse_txt(text: str):
    results = []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "#genre#" in line:
            continue
        if "," in line:
            parts = line.split(",", 1)
            ch_name = parts[0].strip()
            url = parts[1].strip()
            if url.startswith("http"):
                results.append((ch_name, url))
    return results


# ── 读取文件（尝试多种编码）────────────────────────────────────────────────
def read_file(path: str) -> str:
    for enc in ("utf-8", "utf-8-sig", "gbk", "gb2312", "latin-1"):
        try:
            with open(path, "r", encoding=enc) as f:
                return f.read()
        except (UnicodeDecodeError, LookupError):
            continue
    return ""


# ── 主逻辑 ────────────────────────────────────────────────────────────────
def main():
    input_dir = "sources"
    output_dir = os.path.join("sources", "temp")
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
        print(f"⚠️  未在 {input_dir} 找到任何 m3u/txt 文件，请检查路径。")
        return

    print(f"找到 {len(files)} 个订阅文件：")
    for f in files:
        print(f"  {f}")

    # channel_map: 标准名 -> set of URLs（去重）
    channel_map: dict[str, set] = defaultdict(set)

    for fpath in files:
        content = read_file(fpath)
        if not content:
            print(f"  ⚠️  无法读取：{fpath}")
            continue

        ext = os.path.splitext(fpath)[1].lower()
        if ext in (".m3u", ".m3u8"):
            entries = parse_m3u(content)
        else:
            # txt 可能是 m3u 内容，也可能是 txt 格式
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

    # ── 构建输出 m3u ───────────────────────────────────────────────────────
    lines = ["#EXTM3U"]
    total = 0

    for std_name in CHANNEL_ORDER:
        urls = sorted(channel_map.get(std_name, set()))  # 排序让输出稳定
        for url in urls:
            lines.append(
                f'#EXTINF:-1 tvg-name="{std_name}" '
                f'group-title="央视公共频道",{std_name}'
            )
            lines.append(url)
            total += 1

    output_content = "\n".join(lines) + "\n"

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(output_content)

    print(f"\n✅ 完成！共写入 {total} 条 CCTV 频道链接 → {output_path}")

    # 打印统计
    print("\n各频道链接数量：")
    for std_name in CHANNEL_ORDER:
        cnt = len(channel_map.get(std_name, set()))
        if cnt:
            print(f"  {std_name:<14} {cnt} 条")


if __name__ == "__main__":
    main()
