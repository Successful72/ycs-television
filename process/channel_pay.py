#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import re
import glob

# ─────────────────────────────────────────────
# 1. 目标频道定义（标准名称 + 精确匹配关键词列表）
# ─────────────────────────────────────────────
# 注：关键词为源文件中实际出现的频道名（含错字/异体字变体），精确匹配，忽略大小写。
# 注：关键词"风云剧场"已从 CCTV-第一剧场 中移除，归属 CCTV-风云剧场，以避免冲突。
CHANNEL_DEFINITIONS = [
    {
        "standard_name": "CCTV-电视指南",
        "keywords": ["电视指南", "CCTV电视指南", "CCTV-电视指南", "CCTV电视指南HD"],
    },
    {
        "standard_name": "CCTV-风云足球",
        "keywords": ["风云足球", "CCTV风云足球", "CCTV-风云足球", "CCTV风云足球HD"],
    },
    {
        "standard_name": "CCTV-女性时尚",
        "keywords": [
            "女性时尚", "CCTV女性时尿", "CCTV-女性时尿",
            "CCTV女性时尚", "CCTV-女性时尚", "CCTV女性时尚HD",
        ],
    },
    {
        "standard_name": "CCTV-卫生健康",
        "keywords": ["百姓健康", "CCTV卫生健康", "CCTV-卫生健康", "CCTV卫生与健康"],
    },
    {
        "standard_name": "CCTV-第一剧场",
        "keywords": [
            "第一剧场", "CCTV第一剧场", "CCTV-第一剧场", "CCTV第一剧场HD",
            "中国电影", "CCTV电影轮播",
        ],
    },
    {
        "standard_name": "CCTV-风云剧场",
        "keywords": ["风云剧场", "CCTV风云剧场", "CCTV-风云剧场", "CCTV风云剧场HD"],
    },
    {
        "standard_name": "CCTV-风云音乐",
        "keywords": ["风云音乐", "CCTV风云音乐", "CCTV-风云音乐", "CCTV风云音乐HD"],
    },
    {
        "standard_name": "CCTV-怀旧剧场",
        "keywords": [
            "怀旧剧场", "CCTV怀旧剧场", "CCTV-怀旧剧场", "CCTV怀旧剧场HD",
            "CCTV怀旧剧圿", "CCTV-怀旧剧圿",
        ],
    },
    {
        "standard_name": "CCTV-重温经典",
        "keywords": ["重温经典", "CCTV重温经典", "CCTV-重温经典"],
    },
    {
        "standard_name": "CHC影迷电影",
        "keywords": ["CHC影迷电影", "CHC影迷", "影迷电影", "影迷频道"],
    },
    {
        "standard_name": "CHC动作电影",
        "keywords": ["CHC动作电影", "CHC动作", "动作电影CHC"],
    },
    {
        "standard_name": "CHC家庭影院",
        "keywords": ["CHC家庭影院", "CHC家庭", "家庭影院CHC"],
    },
    {
        "standard_name": "CCTV-高尔夫·网球",
        "keywords": [
            "高尔夫网球", "CCTV高尔夫球", "CCTV高尔夫·网球", "CCTV-高尔夫网琿",
            "CCTV高尔夫网球", "CCTV-高尔夫网球", "CCTV高尔夫网球HD", "CCTV-央视高网",
        ],
    },
    {
        "standard_name": "CCTV-央视文化精品",
        "keywords": [
            "文化精品", "CCTV文化精品", "CCTV-文化精品",
            "CCTV央视文化精品", "CCTV-央视文化精品", "CCTV央视文化精品HD",
        ],
    },
    {
        "standard_name": "CCTV-世界地理",
        "keywords": ["世界地理", "CCTV世界地理", "CCTV-世界地理", "CCTV世界地理HD"],
    },
    {
        "standard_name": "CCTV-台球",
        "keywords": [
            "台球", "央视台球", "CCTV央视台球", "CCTV-央视台球",
            "CCTV央视台球HD", "CCTV-台球",
        ],
    },
    {
        "standard_name": "CCTV-兵器科技",
        "keywords": ["兵器科技", "CCTV兵器", "CCTV兵器科技", "CCTV-兵器科技", "CCTV兵器科技HD"],
    },
    {
        "standard_name": "中央新影-老故事",
        "keywords": [
            "老故事", "CCTV老故事", "CCTV-老故事", "CCTV老故亿",
            "中央新影-老故事", "中央新影-老故亿",
        ],
    },
    {
        "standard_name": "中央新影-发现之旅",
        "keywords": ["发现之旅", "CCTV发现之旅", "CCTV-发现之旅", "中央新影-发现之旅"],
    },
    {
        "standard_name": "中央新影-中学生",
        "keywords": [
            "中学生", "CCTV中学甿", "CCTV中学生", "CCTV-中学生",
            "中央新影-中学甿", "中央新影-中学生",
        ],
    },
]

# 构建关键词快速查找表：关键词（小写）-> 标准频道名，O(1) 精确匹配
KEYWORD_LOOKUP = {}
for _ch in CHANNEL_DEFINITIONS:
    for _kw in _ch["keywords"]:
        _key = _kw.lower()
        if _key in KEYWORD_LOOKUP:
            print(f"⚠️  关键词冲突: '{_kw}' 已映射到 '{KEYWORD_LOOKUP[_key]}'，跳过 '{_ch['standard_name']}'")
        else:
            KEYWORD_LOOKUP[_key] = _ch["standard_name"]

# 标准名 -> 定义 的快速反查
_CH_BY_NAME = {ch["standard_name"]: ch for ch in CHANNEL_DEFINITIONS}


# ─────────────────────────────────────────────
# 2. 辅助：判断一行频道名属于哪个目标频道
# ─────────────────────────────────────────────
def match_channel(name: str):
    """精确匹配（忽略大小写），返回匹配的频道定义 dict，或 None。"""
    sname = KEYWORD_LOOKUP.get(name.strip().lower())
    return _CH_BY_NAME[sname] if sname else None


# ─────────────────────────────────────────────
# 3. 解析文件（逐行读取，内存友好）
# ─────────────────────────────────────────────
def parse_file_line_by_line(filepath: str):
    """
    逐行读取文件的通用解析器。
    支持 m3u/m3u8 格式，以及以逗号、制表符或两个以上空格分隔的 txt 格式。
    """
    results = []
    ext = os.path.splitext(filepath)[1].lower()

    try:
        with open(filepath, encoding="utf-8", errors="ignore") as f:
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
            line = lines[i].rstrip()
            if line.startswith("#EXTINF"):
                extinf_line = line
                m = re.search(r",(.+)$", line)
                name = m.group(1).strip() if m else ""
                # 查找下一行非空非注释行作为 URL
                j = i + 1
                while j < len(lines):
                    next_line = lines[j].rstrip()
                    if next_line and not next_line.startswith("#"):
                        results.append({"name": name, "url": next_line, "extinf_line": extinf_line})
                        i = j + 1
                        break
                    j += 1
                else:
                    i += 1
            else:
                i += 1
    else:
        # txt 格式解析：支持逗号、制表符、两个以上空格作为分隔符
        for line in lines:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = re.split(r",|\t|\s{2,}", line, maxsplit=1)
            if len(parts) == 2:
                name, url = parts[0].strip(), parts[1].strip()
                if re.match(r"https?://|rtsp://|rtmp://|rtp://", url, re.IGNORECASE):
                    results.append({"name": name, "url": url, "extinf_line": None})

    return results


# ─────────────────────────────────────────────
# 4. 自然数排序辅助函数
# ─────────────────────────────────────────────
def natural_sort_key(path: str) -> int:
    """从文件名中提取自然数作为排序键，例如 src-10.m3u -> 10。"""
    m = re.search(r"(\d+)", os.path.basename(path))
    return int(m.group(1)) if m else 0


# ─────────────────────────────────────────────
# 5. 主流程
# ─────────────────────────────────────────────
def main():
    input_dir = "sources"
    output_dir = os.path.join("sources", "temp")
    output_path = os.path.join(output_dir, "央视付费频道.m3u")

    os.makedirs(output_dir, exist_ok=True)

    print(f"📁 当前工作目录: {os.getcwd()}")
    print(f"📁 源文件目录: {input_dir}")
    print(f"📁 输出目录: {output_dir}")

    if not os.path.exists(input_dir):
        print(f"❌ 源目录不存在: {input_dir}")
        return

    # 搜集所有 m3u / m3u8 / txt 文件，排除 temp 子目录
    files = []
    for pattern in ["*.m3u", "*.m3u8", "*.txt"]:
        files.extend(glob.glob(os.path.join(input_dir, pattern)))
    files = [f for f in files if not f.startswith(os.path.join(input_dir, "temp"))]

    if not files:
        print(f"⚠️  在 {input_dir} 中未找到任何 .m3u / .m3u8 / .txt 文件")
        return

    # 按文件名中的自然数升序排列（src-1 < src-2 < ... < src-10）
    files.sort(key=natural_sort_key)

    print(f"\n📂 共找到 {len(files)} 个订阅文件（按序号排列）：")
    for f in files:
        print(f"   {os.path.basename(f)}")
    print()

    # 全局 URL 去重集合
    global_urls = set()

    # 按频道汇总：standard_name -> 条目列表
    channel_map = {ch["standard_name"]: [] for ch in CHANNEL_DEFINITIONS}

    for filepath in files:
        print(f"正在处理: {os.path.basename(filepath)}")
        entries = parse_file_line_by_line(filepath)

        for entry in entries:
            ch_def = match_channel(entry["name"])
            if ch_def is None:
                continue

            url = entry["url"]
            if url not in global_urls:
                global_urls.add(url)
                channel_map[ch_def["standard_name"]].append(entry)

    # ── 组装 m3u ──
    output_lines = ["#EXTM3U\n"]
    total = 0

    print("\n📊 提取结果：")
    for ch in CHANNEL_DEFINITIONS:
        sname = ch["standard_name"]
        entries = channel_map[sname]
        if not entries:
            print(f"⚠️  未找到频道：{sname}")
            continue

        for entry in entries:
            original_extinf = entry.get("extinf_line") or ""
            if original_extinf:
                # 移除旧 group-title，插入新 group-title，替换频道名为标准名
                new_extinf = re.sub(r'\s*group-title="[^"]*"', "", original_extinf)
                new_extinf = re.sub(
                    r"(#EXTINF\s*:\s*-?\d+)",
                    r'\1 group-title="央视付费频道"',
                    new_extinf,
                )
                new_extinf = re.sub(r"(,)[^,]*$", r"\1" + sname, new_extinf)
            else:
                new_extinf = f'#EXTINF:-1 group-title="央视付费频道",{sname}'

            output_lines.append(new_extinf + "\n")
            output_lines.append(entry["url"] + "\n")
            total += 1

        print(f"✅  {sname}：找到 {len(entries)} 条链接")

    try:
        with open(output_path, "w", encoding="utf-8-sig") as f:
            f.writelines(output_lines)
        print(f"\n🎉 完成！共提取 {total} 条链接")
        print(f"📄 输出文件：{output_path}")
        print(f"📁 文件大小：{os.path.getsize(output_path)} 字节")
    except Exception as e:
        print(f"❌ 写入文件失败: {e}")


if __name__ == "__main__":
    main()
