
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
IPTV 央视付费频道提取工具
从 ./sources 目录下的 m3u 和 txt 格式 IPTV 订阅文件中，
提取所有 CCTV 付费频道的播放链接，组装成新的 m3u 文件。
输出到 ./sources/temp 目录
"""

import os
import re
import glob
from pathlib import Path

# ─────────────────────────────────────────────
# 1. 目标频道定义（标准名称 + 匹配关键词列表）
# ─────────────────────────────────────────────
CHANNEL_DEFINITIONS = [
    {
        "standard_name": "CCTV-电视指南",
        "keywords": ["电视指南", "cctv.*指南", "指南频道"],
    },
    {
        "standard_name": "CCTV-风云足球",
        "keywords": ["风云足球", "cctv.*足球", "央视.*足球", "足球.*频道"],
    },
    {
        "standard_name": "CCTV-女性时尚",
        "keywords": ["女性时尚", "cctv.*女性", "央视.*女性", "时尚.*频道"],
    },
    {
        "standard_name": "CCTV-卫生健康",
        "keywords": ["卫生健康", "cctv.*卫生", "cctv.*健康", "央视.*健康"],
    },
    {
        "standard_name": "CCTV-第一剧场",
        "keywords": ["第一剧场", "cctv.*第一剧", "央视.*第一剧"],
    },
    {
        "standard_name": "CCTV-风云剧场",
        "keywords": ["风云剧场", "cctv.*风云剧", "央视.*风云剧"],
    },
    {
        "standard_name": "CCTV-风云音乐",
        "keywords": ["风云音乐", "cctv.*风云音乐", "央视.*风云音乐"],
    },
    {
        "standard_name": "CCTV-怀旧剧场",
        "keywords": ["怀旧剧场", "cctv.*怀旧", "央视.*怀旧"],
    },
    {
        "standard_name": "CCTV-重温经典",
        "keywords": ["重温经典", "cctv.*重温", "央视.*重温"],
    },
    {
        "standard_name": "CHC影迷电影",
        "keywords": ["chc.*影迷", "影迷.*电影", "影迷频道"],
    },
    {
        "standard_name": "CHC动作电影",
        "keywords": ["chc.*动作", "动作.*电影.*chc", "chc.*action"],
    },
    {
        "standard_name": "CHC家庭影院",
        "keywords": ["chc.*家庭", "家庭.*影院.*chc", "chc.*home"],
    },
    {
        "standard_name": "CCTV-高尔夫·网球",
        "keywords": ["高尔夫.*网球", "网球.*高尔夫", "cctv.*高尔夫", "央视.*高尔夫", "cctv.*网球"],
    },
    {
        "standard_name": "CCTV-央视文化精品",
        "keywords": ["文化精品", "cctv.*文化精品", "央视文化精品", "央视.*文化精品"],
    },
    {
        "standard_name": "CCTV-世界地理",
        "keywords": ["世界地理", "cctv.*世界地理", "央视.*世界地理"],
    },
    {
        "standard_name": "CCTV-台球",
        "keywords": ["台球", "cctv.*台球", "央视.*台球"],
    },
    {
        "standard_name": "CCTV-兵器科技",
        "keywords": ["兵器科技", "cctv.*兵器", "央视.*兵器", "兵器.*频道"],
    },
    {
        "standard_name": "中央新影-老故事",
        "keywords": ["老故事", "新影.*老故事", "中央新影.*老故事", "央视.*老故事"],
    },
    {
        "standard_name": "中央新影-发现之旅",
        "keywords": ["发现之旅", "新影.*发现", "中央新影.*发现", "央视.*发现之旅"],
    },
    {
        "standard_name": "中央新影-中学生",
        "keywords": ["中学生", "新影.*中学生", "中央新影.*中学生", "央视.*中学生"],
    },
]

# 预编译每个频道的正则（忽略大小写）
for ch in CHANNEL_DEFINITIONS:
    ch["pattern"] = re.compile("|".join(ch["keywords"]), re.IGNORECASE)


# ─────────────────────────────────────────────
# 2. 辅助：判断一行频道名属于哪个目标频道
# ─────────────────────────────────────────────
def match_channel(name: str):
    """返回匹配的频道定义 dict，或 None。"""
    name_stripped = name.strip()
    for ch in CHANNEL_DEFINITIONS:
        if ch["pattern"].search(name_stripped):
            return ch
    return None


# ─────────────────────────────────────────────
# 3. 解析 m3u 格式文件（逐行读取优化版）
# ─────────────────────────────────────────────
def parse_m3u(filepath: str):
    """
    返回列表：[{"name": ..., "url": ..., "extinf_line": ...}, ...]
    """
    results = []
    try:
        with open(filepath, encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()
    except Exception as e:
        print(f"❌ 读取文件失败 {filepath}: {e}")
        return []

    i = 0
    while i < len(lines):
        line = lines[i].rstrip()
        if line.startswith("#EXTINF"):
            extinf_line = line
            # 提取频道名（#EXTINF 最后一个逗号后面的内容）
            m = re.search(r",(.+)$", line)
            name = m.group(1).strip() if m else ""
            # 下一行应为 URL
            j = i + 1
            while j < len(lines) and lines[j].strip() == "":
                j += 1
            if j < len(lines):
                url = lines[j].strip()
                if url and not url.startswith("#"):
                    results.append({"name": name, "url": url, "extinf_line": extinf_line})
                    i = j + 1
                    continue
        i += 1
    return results


# ─────────────────────────────────────────────
# 4. 解析 txt 格式文件（两种常见格式）
#    格式A：频道名,URL
#    格式B：#EXTINF ... （同 m3u，但扩展名是 txt）
# ─────────────────────────────────────────────
def parse_txt(filepath: str):
    results = []
    try:
        with open(filepath, encoding="utf-8", errors="ignore") as f:
            content = f.read()
    except Exception as e:
        print(f"❌ 读取文件失败 {filepath}: {e}")
        return []

    # 如果文件内含 #EXTINF，按 m3u 方式处理
    if "#EXTINF" in content:
        lines = content.splitlines()
        i = 0
        while i < len(lines):
            line = lines[i].rstrip()
            if line.startswith("#EXTINF"):
                m = re.search(r",(.+)$", line)
                name = m.group(1).strip() if m else ""
                j = i + 1
                while j < len(lines) and lines[j].strip() == "":
                    j += 1
                if j < len(lines):
                    url = lines[j].strip()
                    if url and not url.startswith("#"):
                        results.append({"name": name, "url": url, "extinf_line": line})
                        i = j + 1
                        continue
            i += 1
        return results

    # 否则按 "频道名,URL" 格式逐行处理
    for line in content.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        # 支持逗号或空格分隔
        parts = re.split(r",\s*|\s{2,}", line, maxsplit=1)
        if len(parts) == 2:
            name, url = parts[0].strip(), parts[1].strip()
            if re.match(r"https?://|rtsp://|rtmp://|rtp://", url, re.IGNORECASE):
                results.append({"name": name, "url": url, "extinf_line": None})
    return results


# ─────────────────────────────────────────────
# 5. 逐行读取优化版解析器
# ─────────────────────────────────────────────
def parse_file_line_by_line(filepath: str):
    """
    逐行读取文件的通用解析器，内存友好型
    支持 m3u、m3u8、txt 格式
    """
    results = []
    ext = os.path.splitext(filepath)[1].lower()
    
    try:
        with open(filepath, encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()  # 对于 GitHub Actions 的小文件，一次读取也没问题
            # 但如果文件真的很大，可以使用迭代器方式：
            # lines = f  # 这样 lines 就是迭代器
    except Exception as e:
        print(f"❌ 读取文件失败 {filepath}: {e}")
        return []
    
    # 检测是否为 m3u 格式
    is_m3u_format = any(line.startswith("#EXTINF") for line in lines[:10])
    
    if ext in (".m3u", ".m3u8") or is_m3u_format:
        # m3u 格式解析
        i = 0
        while i < len(lines):
            line = lines[i].rstrip() if hasattr(lines[i], 'rstrip') else lines[i].strip()
            if line.startswith("#EXTINF"):
                extinf_line = line
                m = re.search(r",(.+)$", line)
                name = m.group(1).strip() if m else ""
                # 查找下一行非空行作为 URL
                j = i + 1
                while j < len(lines):
                    next_line = lines[j].rstrip() if hasattr(lines[j], 'rstrip') else lines[j].strip()
                    if next_line and not next_line.startswith("#"):
                        url = next_line
                        results.append({"name": name, "url": url, "extinf_line": extinf_line})
                        i = j + 1
                        break
                    j += 1
                else:
                    i += 1
            else:
                i += 1
    else:
        # txt 格式解析（频道名,URL）
        for line in lines:
            line = line.strip() if hasattr(line, 'strip') else line
            if not line or line.startswith("#"):
                continue
            parts = re.split(r",\s*|\s{2,}", line, maxsplit=1)
            if len(parts) == 2:
                name, url = parts[0].strip(), parts[1].strip()
                if re.match(r"https?://|rtsp://|rtmp://|rtp://", url, re.IGNORECASE):
                    results.append({"name": name, "url": url, "extinf_line": None})
    
    return results


# ─────────────────────────────────────────────
# 6. 主流程
# ─────────────────────────────────────────────
def main():
    # GitHub Actions 环境下的路径
    base_dir = Path(__file__).parent  # 获取脚本所在目录
    source_dir = base_dir / "sources"  # 源文件目录
    temp_dir = source_dir / "temp"     # 输出目录
    
    # 确保 temp 目录存在
    temp_dir.mkdir(parents=True, exist_ok=True)
    
    output_file = temp_dir / "央视付费频道.m3u"
    
    print(f"📁 当前工作目录: {os.getcwd()}")
    print(f"📁 脚本所在目录: {base_dir}")
    print(f"📁 源文件目录: {source_dir}")
    print(f"📁 输出目录: {temp_dir}")

    # 检查源目录是否存在
    if not source_dir.exists():
        print(f"❌ 源目录不存在: {source_dir}")
        print("请在GitHub Actions的workflow中确保已创建sources目录并放入文件")
        return

    # 搜集所有 m3u / m3u8 / txt 文件
    files = []
    for pattern in ["src-*.m3u", "src-*.m3u8", "src-*.txt"]:
        files.extend(glob.glob(str(source_dir / pattern)))
    
    # 排除 temp 目录中的文件
    files = [f for f in files if not f.startswith(str(temp_dir))]

    if not files:
        print(f"⚠️  在 {source_dir} 中未找到任何 .m3u / .m3u8 / .txt 文件")
        print("请检查文件是否已放入sources目录")
        return

    print(f"\n📂 共找到 {len(files)} 个订阅文件：")
    for f in files:
        print(f"   {os.path.basename(f)}")
    print()

    # 全局URL去重
    global_urls = set()
    
    # 按频道汇总：standard_name -> {urls: set, entries: list}
    channel_map = {ch["standard_name"]: {"urls": set(), "entries": []} for ch in CHANNEL_DEFINITIONS}

    for filepath in files:
        print(f"正在处理: {os.path.basename(filepath)}")
        
        # 使用逐行读取优化版解析器
        entries = parse_file_line_by_line(filepath)

        for entry in entries:
            ch_def = match_channel(entry["name"])
            if ch_def is None:
                continue
            
            sname = ch_def["standard_name"]
            url = entry["url"]
            
            # 全局去重
            if url not in global_urls:
                global_urls.add(url)
                if url not in channel_map[sname]["urls"]:
                    channel_map[sname]["urls"].add(url)
                    channel_map[sname]["entries"].append(entry)

    # ── 组装 m3u ──
    output_lines = ["#EXTM3U\n"]
    total = 0

    print("\n📊 提取结果：")
    for ch in CHANNEL_DEFINITIONS:
        sname = ch["standard_name"]
        data = channel_map[sname]
        if not data["entries"]:
            print(f"⚠️  未找到频道：{sname}")
            continue

        for entry in data["entries"]:
            # 重新构造 EXTINF 行
            original_extinf = entry.get("extinf_line") or ""
            if original_extinf:
                # 移除旧的 group-title 属性
                new_extinf = re.sub(r'\s*group-title="[^"]*"', "", original_extinf)
                # 在 #EXTINF:-1 之后插入 group-title
                new_extinf = re.sub(
                    r"(#EXTINF\s*:\s*-?\d+)",
                    r'\1 group-title="央视付费频道"',
                    new_extinf,
                )
                # 替换最后一个逗号后的频道名为标准名
                new_extinf = re.sub(r"(,)[^,]*$", r"\1" + sname, new_extinf)
            else:
                new_extinf = f'#EXTINF:-1 group-title="央视付费频道",{sname}'

            output_lines.append(new_extinf + "\n")
            output_lines.append(entry["url"] + "\n")
            total += 1

        print(f"✅  {sname}：找到 {len(data['entries'])} 条链接")

    # 写入文件
    try:
        with open(output_file, "w", encoding="utf-8-sig") as f:
            f.writelines(output_lines)
        print(f"\n🎉 完成！共提取 {total} 条链接")
        print(f"📄 输出文件：{output_file}")
        print(f"📁 文件大小：{os.path.getsize(output_file)} 字节")
    except Exception as e:
        print(f"❌ 写入文件失败: {e}")


if __name__ == "__main__":
    main()
