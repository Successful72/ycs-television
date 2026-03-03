#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
IPTV 省级卫视频道提取工具
从 sources 目录的 m3u/txt 订阅文件中提取省级卫视频道，
生成新的 m3u 文件到 sources/temp 目录。
"""

import os
import re
import glob

# ─────────────────────────────────────────────
# 1. 省级卫视定义（标准名称 + 匹配关键词）
# ─────────────────────────────────────────────
PROVINCIAL_CHANNELS = [
    {
        "name": "北京卫视",
        "patterns": [r"北京卫视", r"BTV\s*卫视", r"BRTV\s*卫视", r"北京\s*satellite", r"beijingws"],
    },
    {
        "name": "天津卫视",
        "patterns": [r"天津卫视", r"天津\s*卫视", r"tianjinws"],
    },
    {
        "name": "东方卫视",
        "patterns": [r"东方卫视", r"上海\s*东方", r"Dragon\s*TV", r"dongfangws"],
    },
    {
        "name": "重庆卫视",
        "patterns": [r"重庆卫视", r"chongqingws"],
    },
    {
        "name": "河北卫视",
        "patterns": [r"河北卫视", r"hebeiws"],
    },
    {
        "name": "山西卫视",
        "patterns": [r"山西卫视", r"shanxiws"],
    },
    {
        "name": "内蒙古卫视",
        "patterns": [r"内蒙古卫视", r"内蒙\s*卫视", r"neimengguws"],
    },
    {
        "name": "辽宁卫视",
        "patterns": [r"辽宁卫视", r"liaoningws"],
    },
    {
        "name": "吉林卫视",
        "patterns": [r"吉林卫视", r"jilinws"],
    },
    {
        "name": "黑龙江卫视",
        "patterns": [r"黑龙江卫视", r"heilongjiangws"],
    },
    {
        "name": "江苏卫视",
        "patterns": [r"江苏卫视", r"JSTV\s*卫视", r"jiangsuws"],
    },
    {
        "name": "浙江卫视",
        "patterns": [r"浙江卫视", r"zhejiangws"],
    },
    {
        "name": "安徽卫视",
        "patterns": [r"安徽卫视", r"anhuiws"],
    },
    {
        "name": "福建东南卫视",
        "patterns": [r"东南卫视", r"福建\s*东南", r"福建卫视", r"dongnanws"],
    },
    {
        "name": "海峡卫视",
        "patterns": [r"海峡卫视", r"haixiaws", r"福建\s*海峡"],
    },
    {
        "name": "江西卫视",
        "patterns": [r"江西卫视", r"jiangxiws"],
    },
    {
        "name": "山东卫视",
        "patterns": [r"山东卫视", r"shandongws"],
    },
    {
        "name": "河南卫视",
        "patterns": [r"河南卫视", r"henanws"],
    },
    {
        "name": "湖北卫视",
        "patterns": [r"湖北卫视", r"hubeiws"],
    },
    {
        "name": "湖南卫视",
        "patterns": [r"湖南卫视", r"Golden\s*Eagle", r"hunanws"],
    },
    {
        "name": "广东卫视",
        "patterns": [r"广东卫视", r"guangdongws"],
    },
    {
        "name": "深圳卫视",
        "patterns": [r"深圳卫视", r"shenzhenws", r"SZTV\s*卫视"],
    },
    {
        "name": "广西卫视",
        "patterns": [r"广西卫视", r"guangxiws"],
    },
    {
        "name": "海南卫视",
        "patterns": [r"海南卫视", r"hainanws"],
    },
    {
        "name": "四川卫视",
        "patterns": [r"四川卫视", r"sichuanws"],
    },
    {
        "name": "贵州卫视",
        "patterns": [r"贵州卫视", r"guizhouws"],
    },
    {
        "name": "云南卫视",
        "patterns": [r"云南卫视", r"yunnanws"],
    },
    {
        "name": "西藏卫视",
        "patterns": [r"西藏卫视", r"xizangws"],
    },
    {
        "name": "陕西卫视",
        "patterns": [r"陕西卫视", r"shanxi2ws"],      # 与"山西"区分，拼音不同
    },
    {
        "name": "甘肃卫视",
        "patterns": [r"甘肃卫视", r"gansuws"],
    },
    {
        "name": "青海卫视",
        "patterns": [r"青海卫视", r"qinghaiws"],
    },
    {
        "name": "宁夏卫视",
        "patterns": [r"宁夏卫视", r"ningxiaws"],
    },
    {
        "name": "新疆卫视",
        "patterns": [r"新疆卫视", r"xinjiangws"],
    },
    {
        "name": "兵团卫视",
        "patterns": [r"兵团卫视", r"bingtuanws", r"新疆\s*兵团"],
    },
]

# ─────────────────────────────────────────────
# 2. 辅助：将所有 pattern 编译为统一正则
# ─────────────────────────────────────────────
def build_channel_regex(channel_def):
    """为单个频道定义构建大小写/全半角不敏感的正则。"""
    combined = "|".join(channel_def["patterns"])
    return re.compile(combined, re.IGNORECASE)


CHANNEL_REGEXES = [
    (ch, build_channel_regex(ch))
    for ch in PROVINCIAL_CHANNELS
]


# ─────────────────────────────────────────────
# 3. 通用解析函数（逐行读取优化版）
# ─────────────────────────────────────────────
def parse_file_line_by_line(filepath: str):
    """
    逐行读取文件的通用解析器，支持 m3u、m3u8、txt 格式
    返回 list of (channel_name, url)
    """
    entries = []
    ext = os.path.splitext(filepath)[1].lower()
    
    try:
        with open(filepath, encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()
    except Exception as e:
        print(f"❌ 读取文件失败 {filepath}: {e}")
        return []
    
    # 检测是否为 m3u 格式（检查前10行是否有 #EXTINF）
    is_m3u_format = any(line.startswith("#EXTINF") for line in lines[:10])
    
    if ext in (".m3u", ".m3u8") or is_m3u_format:
        # m3u 格式解析
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            if line.startswith("#EXTINF"):
                # 提取频道名：#EXTINF:-1 ... ,频道名
                name_match = re.search(r",(.+)$", line)
                channel_name = name_match.group(1).strip() if name_match else ""
                
                # 向后找第一个非注释、非空行作为 URL
                j = i + 1
                while j < len(lines):
                    candidate = lines[j].strip()
                    if candidate and not candidate.startswith("#"):
                        entries.append((channel_name, candidate))
                        i = j  # 跳过已消费的 URL 行
                        break
                    j += 1
                else:
                    i += 1
            else:
                i += 1
    else:
        # txt 格式解析（支持逗号或竖线分隔）
        for line in lines:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            # 尝试 逗号 或 竖线 分隔
            for sep in (",", "|"):
                parts = line.split(sep, 1)
                if len(parts) == 2:
                    name, url = parts[0].strip(), parts[1].strip()
                    if re.match(r"https?://|rtsp://|rtmp://", url, re.IGNORECASE):
                        entries.append((name, url))
                        break
    
    return entries


# ─────────────────────────────────────────────
# 4. 匹配：判断频道名属于哪个省级卫视
# ─────────────────────────────────────────────
def match_channel(name):
    """
    返回匹配到的省级卫视标准名，未匹配返回 None。
    额外规则：
      - 排除含"高清""HD""4K""超清"之类后缀但频道本体匹配的情况（保留）
      - 严格排除地方台（只包含"新闻""都市""影视"等关键词、不含"卫视"字样）
    """
    # 必须含"卫视"字样 或 已有英文别名，防止误匹配纯地方台
    # 例外：东方卫视在某些源里写"Dragon TV"，已在 patterns 里处理
    for ch_def, regex in CHANNEL_REGEXES:
        if regex.search(name):
            # 二次排除：若名字里含"卫视"但同时含省级卫视范围之外的台标识
            # （保守策略：只要正则命中即认定匹配）
            return ch_def["name"]
    return None


# ─────────────────────────────────────────────
# 5. 主流程
# ─────────────────────────────────────────────
def main():
    # 使用相对于工作目录的路径
    input_dir = "sources"
    output_dir = os.path.join("sources", "temp")
    output_path = os.path.join(output_dir, "省级卫视频道.m3u")
    
    # 确保输出目录存在
    os.makedirs(output_dir, exist_ok=True)
    
    print(f"📁 当前工作目录: {os.getcwd()}")
    print(f"📁 源文件目录: {input_dir}")
    print(f"📁 输出目录: {output_dir}")

    # 检查源目录是否存在
    if not os.path.exists(input_dir):
        print(f"❌ 源目录不存在: {input_dir}")
        return

    # 收集所有 m3u/txt 文件
    files = []
    for pattern in ["src-*.m3u", "src-*.m3u8", "src-*.txt"]:
        files.extend(glob.glob(os.path.join(input_dir, pattern)))
    
    # 排除 temp 目录中的文件
    files = [f for f in files if not f.startswith(os.path.join(input_dir, "temp"))]
    # 排除输出文件本身（如果存在）
    files = [f for f in files if os.path.abspath(f) != os.path.abspath(output_path)]

    if not files:
        print(f"⚠️  在 {input_dir} 中未找到任何 m3u/m3u8/txt 文件。")
        return

    print(f"\n📂 共找到 {len(files)} 个订阅文件：")
    for f in files:
        print(f"   {os.path.basename(f)}")

    # 按标准频道名收集 URL（去重）
    # channel_map: { 标准名: { url: 原始名 } }
    channel_map = {ch["name"]: {} for ch in PROVINCIAL_CHANNELS}
    seen_urls = set()  # 全局去重

    total_raw = 0
    total_matched = 0

    for filepath in files:
        print(f"正在处理: {os.path.basename(filepath)}")
        
        try:
            entries = parse_file_line_by_line(filepath)
        except Exception as e:
            print(f"❌ 解析 {os.path.basename(filepath)} 失败：{e}")
            continue

        total_raw += len(entries)

        for name, url in entries:
            std_name = match_channel(name)
            if std_name is None:
                continue
            # URL 去重
            url_norm = url.strip().rstrip("/")
            if url_norm in seen_urls:
                continue
            seen_urls.add(url_norm)
            channel_map[std_name][url_norm] = name  # 保存原始名备用
            total_matched += 1

    # ── 生成 m3u 文件 ──
    lines_out = ["#EXTM3U"]
    group_name = "省级卫视频道"

    written_channels = 0
    print("\n📊 提取结果：")
    for ch_def in PROVINCIAL_CHANNELS:
        std_name = ch_def["name"]
        url_dict = channel_map[std_name]
        if not url_dict:
            print(f"⚠️  {std_name}: 未找到")
            continue
        
        print(f"✅ {std_name}: {len(url_dict)} 条")
        
        for url, orig_name in url_dict.items():
            lines_out.append(
                f'#EXTINF:-1 group-title="{group_name}" tvg-name="{std_name}"'
                f' tvg-logo="" ,{std_name}'
            )
            lines_out.append(url)
            written_channels += 1

    try:
        with open(output_path, "w", encoding="utf-8-sig") as f:
            f.write("\n".join(lines_out) + "\n")
        
        print(f"\n🎉 完成！")
        print(f"📊 原始条目总数：{total_raw}")
        print(f"📊 匹配省级卫视条目：{total_matched}")
        print(f"📊 写入频道条目数：{written_channels}")
        print(f"📄 输出文件：{output_path}")
        print(f"📁 文件大小：{os.path.getsize(output_path)} 字节")
    except Exception as e:
        print(f"❌ 写入文件失败: {e}")


if __name__ == "__main__":
    main()
