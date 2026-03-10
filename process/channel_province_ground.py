#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
IPTV 省级地方频道提取器
从 sources 目录的 m3u/txt 订阅文件中提取省级地方频道，
按省份由北向南排列，生成新的 m3u 文件到 sources/temp 目录
"""

import os
import re
import glob
from collections import OrderedDict

# ─────────────────────────────────────────────────────────────────────────────
# 各省频道定义（由北向南排列）
# 每个频道条目：(标准显示名称, 正则匹配模式)
# 匹配时忽略大小写，且已处理空格可有可无的情况
# ─────────────────────────────────────────────────────────────────────────────
PROVINCE_CHANNELS = OrderedDict([

    ("北京", [
        ("BRTV 新闻",     r"BRT\s*V\s*新\s*闻|北京\s*新\s*闻"),
        ("BRTV 纪实科教", r"BRT\s*V\s*纪\s*实|北京\s*纪\s*实|BRT\s*V\s*科\s*教"),
        # 新增：卡酷动画、KAKU 等别名（来源数据补充）
        ("BRTV 卡酷少儿", r"BRT\s*V\s*卡\s*酷|北京\s*卡\s*酷|卡\s*酷\s*少\s*儿|卡\s*酷\s*动\s*画|KAKU"),
        ("BRTV 文艺",     r"BRT\s*V\s*文\s*艺|北京\s*文\s*艺"),
        ("BRTV 生活",     r"BRT\s*V\s*生\s*活|北京\s*生\s*活"),
    ]),

    ("天津", [
        ("天津新闻",   r"天\s*津\s*新\s*闻"),
        ("天津文艺",   r"天\s*津\s*文\s*艺"),
        ("天津体育",   r"天\s*津\s*体\s*育"),
        ("天津都市",   r"天\s*津\s*都\s*市"),
    ]),

    ("河北", [
        ("河北经济生活", r"河\s*北\s*经\s*济\s*生\s*活|经\s*济\s*生\s*活"),
        ("河北少儿科教", r"河\s*北\s*少\s*儿\s*科\s*教|少\s*儿\s*科\s*教"),
        ("河北公共",     r"河\s*北\s*公\s*共"),
        ("河北农民",     r"河\s*北\s*农\s*民"),
    ]),

    ("山西", [
        ("山西卫视",   r"山\s*西\s*卫\s*视"),
        ("山西新闻",   r"山\s*西\s*新\s*闻"),
        ("山西经济",   r"山\s*西\s*经\s*济"),
        ("黄河频道",   r"黄\s*河\s*频\s*道|山\s*西\s*黄\s*河"),
    ]),

    ("内蒙古", [
        ("内蒙古卫视",   r"内\s*蒙\s*古\s*卫\s*视"),
        ("内蒙古新闻",   r"内\s*蒙\s*古\s*新\s*闻"),
        ("内蒙古文体",   r"内\s*蒙\s*古\s*文\s*体"),
        ("草原频道",     r"草\s*原\s*频\s*道|内\s*蒙\s*古\s*草\s*原"),
    ]),

    ("辽宁", [
        ("辽宁卫视",   r"辽\s*宁\s*卫\s*视"),
        ("辽宁新闻",   r"辽\s*宁\s*新\s*闻"),
        ("辽宁都市",   r"辽\s*宁\s*都\s*市"),
        ("辽宁北方",   r"辽\s*宁\s*北\s*方"),
    ]),

    ("吉林", [
        ("吉林卫视",   r"吉\s*林\s*卫\s*视"),
        ("吉林新闻",   r"吉\s*林\s*新\s*闻"),
        ("吉林都市",   r"吉\s*林\s*都\s*市"),
        ("吉林乡村",   r"吉\s*林\s*乡\s*村"),
    ]),

    ("黑龙江", [
        ("黑龙江卫视", r"黑\s*龙\s*江\s*卫\s*视"),
        ("黑龙江新闻", r"黑\s*龙\s*江\s*新\s*闻"),
        ("黑龙江都市", r"黑\s*龙\s*江\s*都\s*市"),
        ("黑龙江农业", r"黑\s*龙\s*江\s*农\s*业"),
    ]),

    ("上海", [
        ("上海新闻综合", r"上\s*海\s*新\s*闻\s*综\s*合|东\s*方\s*新\s*闻|STV\s*新\s*闻"),
        ("上海都市",     r"上\s*海\s*都\s*市"),
        ("上海纪实",     r"上\s*海\s*纪\s*实"),
        ("第一财经",     r"第\s*一\s*财\s*经"),
    ]),

    ("江苏", [
        ("江苏城市",   r"江\s*苏\s*城\s*市"),
        ("江苏公共",   r"江\s*苏\s*公\s*共"),
        # 新增：优漫卡通、江苏优漫卡通 等别名（来源数据补充）
        ("江苏优漫",   r"江\s*苏\s*优\s*漫|优\s*漫\s*卡\s*通"),
        ("江苏综艺",   r"江\s*苏\s*综\s*艺"),
    ]),

    ("浙江", [
        ("浙江钱江",   r"浙\s*江\s*钱\s*江|钱\s*江\s*频\s*道"),
        ("浙江教育",   r"浙\s*江\s*教\s*育"),
        ("浙江民生",   r"浙\s*江\s*民\s*生"),
        ("浙江经济生活", r"浙\s*江\s*经\s*济\s*生\s*活"),
    ]),

    ("安徽", [
        ("安徽新闻综合", r"安\s*徽\s*新\s*闻\s*综\s*合|安\s*徽\s*综\s*合"),
        ("安徽公共",     r"安\s*徽\s*公\s*共"),
        ("安徽影视",     r"安\s*徽\s*影\s*视"),
        ("安徽生活",     r"安\s*徽\s*生\s*活"),
    ]),

    ("福建", [
        ("福建新闻综合", r"福\s*建\s*新\s*闻\s*综\s*合|福\s*建\s*综\s*合"),
        ("福建公共",     r"福\s*建\s*公\s*共"),
        ("福建经济生活", r"福\s*建\s*经\s*济\s*生\s*活"),
        ("福建体育",     r"福\s*建\s*体\s*育"),
    ]),

    ("江西", [
        ("江西新闻综合", r"江\s*西\s*新\s*闻\s*综\s*合|江\s*西\s*综\s*合"),
        ("江西都市",     r"江\s*西\s*都\s*市"),
        ("江西公共",     r"江\s*西\s*公\s*共"),
        ("江西经济生活", r"江\s*西\s*经\s*济\s*生\s*活"),
    ]),

    ("山东", [
        ("山东综合",   r"山\s*东\s*综\s*合"),
        ("山东公共",   r"山\s*东\s*公\s*共"),
        ("山东农科",   r"山\s*东\s*农\s*科"),
        ("山东少儿",   r"山\s*东\s*少\s*儿"),
    ]),

    ("河南", [
        ("河南梨园",   r"河\s*南\s*梨\s*园|梨\s*园\s*频\s*道"),
        ("武术世界",   r"武\s*术\s*世\s*界|河\s*南\s*武\s*术"),
        ("河南都市",   r"河\s*南\s*都\s*市"),
        ("河南农村农业", r"河\s*南\s*农\s*村|河\s*南\s*农\s*业"),
    ]),

    ("湖北", [
        ("湖北综合",   r"湖\s*北\s*综\s*合"),
        ("湖北垄上",   r"湖\s*北\s*垄\s*上|垄\s*上\s*频\s*道"),
        ("湖北都市",   r"湖\s*北\s*都\s*市"),
        ("湖北公共",   r"湖\s*北\s*公\s*共"),
    ]),

    ("湖南", [
        ("湖南金鹰纪实", r"湖\s*南\s*金\s*鹰\s*纪\s*实|金\s*鹰\s*纪\s*实"),
        ("湖南公共",     r"湖\s*南\s*公\s*共"),
        ("湖南都市",     r"湖\s*南\s*都\s*市"),
        ("湖南经视",     r"湖\s*南\s*经\s*视|经\s*济\s*电\s*视"),
    ]),

    ("广东", [
        ("广东综合",   r"广\s*东\s*综\s*合"),
        ("广东公共",   r"广\s*东\s*公\s*共"),
        ("广东南方",   r"广\s*东\s*南\s*方|南\s*方\s*卫\s*视"),
        ("广东珠江",   r"广\s*东\s*珠\s*江|珠\s*江\s*频\s*道"),
    ]),

    ("广西", [
        ("广西综合",   r"广\s*西\s*综\s*合"),
        ("广西公共",   r"广\s*西\s*公\s*共"),
        ("广西都市",   r"广\s*西\s*都\s*市"),
        ("广西影视",   r"广\s*西\s*影\s*视"),
    ]),

    ("海南", [
        ("海南综合",   r"海\s*南\s*综\s*合"),
        ("海南公共",   r"海\s*南\s*公\s*共"),
        ("海南旅游",   r"海\s*南\s*旅\s*游"),
        ("海南新闻",   r"海\s*南\s*新\s*闻"),
    ]),

    ("重庆", [
        ("重庆新闻",   r"重\s*庆\s*新\s*闻"),
        ("重庆都市",   r"重\s*庆\s*都\s*市"),
        ("重庆公共",   r"重\s*庆\s*公\s*共"),
        ("重庆影视",   r"重\s*庆\s*影\s*视"),
    ]),

    ("四川", [
        ("四川新闻",   r"四\s*川\s*新\s*闻"),
        ("四川文化旅游", r"四\s*川\s*文\s*化\s*旅\s*游|四\s*川\s*文\s*旅"),
        ("四川公共",   r"四\s*川\s*公\s*共"),
        ("四川经济",   r"四\s*川\s*经\s*济"),
    ]),

    ("贵州", [
        ("贵州综合",   r"贵\s*州\s*综\s*合"),
        ("贵州公共",   r"贵\s*州\s*公\s*共"),
        ("贵州都市",   r"贵\s*州\s*都\s*市"),
        ("贵州影视",   r"贵\s*州\s*影\s*视"),
    ]),

    ("云南", [
        ("云南综合",   r"云\s*南\s*综\s*合"),
        ("云南都市",   r"云\s*南\s*都\s*市"),
        ("云南公共",   r"云\s*南\s*公\s*共"),
        ("云南影视",   r"云\s*南\s*影\s*视"),
    ]),

    ("西藏", [
        ("西藏综合",   r"西\s*藏\s*综\s*合"),
        ("西藏卫视",   r"西\s*藏\s*卫\s*视"),
        ("藏语卫视",   r"藏\s*语\s*卫\s*视"),
        ("西藏文艺",   r"西\s*藏\s*文\s*艺"),
    ]),

    ("陕西", [
        ("陕西综合",   r"陕\s*西\s*综\s*合"),
        ("陕西都市",   r"陕\s*西\s*都\s*市"),
        ("陕西公共",   r"陕\s*西\s*公\s*共"),
        ("陕西农林",   r"陕\s*西\s*农\s*林|陕\s*西\s*农\s*业"),
    ]),

    ("甘肃", [
        ("甘肃综合",   r"甘\s*肃\s*综\s*合"),
        ("甘肃都市",   r"甘\s*肃\s*都\s*市"),
        ("甘肃公共",   r"甘\s*肃\s*公\s*共"),
        ("甘肃经济",   r"甘\s*肃\s*经\s*济"),
    ]),

    ("青海", [
        ("青海综合",   r"青\s*海\s*综\s*合"),
        ("青海公共",   r"青\s*海\s*公\s*共"),
        ("青海影视",   r"青\s*海\s*影\s*视"),
        ("青海新闻",   r"青\s*海\s*新\s*闻"),
    ]),

    ("宁夏", [
        ("宁夏综合",   r"宁\s*夏\s*综\s*合"),
        ("宁夏公共",   r"宁\s*夏\s*公\s*共"),
        ("宁夏都市",   r"宁\s*夏\s*都\s*市"),
        ("宁夏影视",   r"宁\s*夏\s*影\s*视"),
    ]),

    ("新疆", [
        ("新疆综合",   r"新\s*疆\s*综\s*合"),
        ("新疆都市",   r"新\s*疆\s*都\s*市"),
        ("新疆公共",   r"新\s*疆\s*公\s*共"),
        ("新疆汉语",   r"新\s*疆\s*汉\s*语"),
    ]),
])


# ─────────────────────────────────────────────────────────────────────────────
# 预编译所有正则，提高性能
# ─────────────────────────────────────────────────────────────────────────────
COMPILED_PATTERNS = OrderedDict()
for province, channels in PROVINCE_CHANNELS.items():
    COMPILED_PATTERNS[province] = [
        (name, re.compile(pattern, re.IGNORECASE))
        for name, pattern in channels
    ]


# ─────────────────────────────────────────────────────────────────────────────
# 自然数排序：按 src-<N> 中的数字排序
# ─────────────────────────────────────────────────────────────────────────────
def natural_sort_key(filepath):
    """提取文件名中 src-<N> 的数字，用于自然数排序。"""
    basename = os.path.basename(filepath)
    match = re.search(r"src-(\d+)", basename, re.IGNORECASE)
    return int(match.group(1)) if match else float("inf")


def parse_file_line_by_line(filepath: str):
    """
    逐行读取文件的通用解析器，支持 m3u、m3u8、txt 格式。
    txt 格式支持逗号或竖线分隔。
    返回 list of dict: {'name': str, 'url': str, 'extinf_line': str}
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
    is_m3u_format = any(line.startswith("#EXTINF") for line in lines[:10])

    if ext in (".m3u", ".m3u8") or is_m3u_format:
        # m3u 格式解析
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            if line.startswith('#EXTINF'):
                extinf_line = line
                # 提取频道名（最后一个逗号之后）
                name_match = re.search(r',(.+)$', line)
                name = name_match.group(1).strip() if name_match else ''
                # 查找下一行非空行作为 URL
                j = i + 1
                while j < len(lines):
                    next_line = lines[j].strip()
                    if next_line and not next_line.startswith('#'):
                        url = next_line
                        entries.append({'name': name, 'url': url, 'extinf_line': extinf_line})
                        i = j + 1
                        break
                    j += 1
                else:
                    i += 1
            else:
                i += 1
    else:
        # txt 格式解析，支持逗号或竖线分隔
        for line in lines:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            for sep in (',', '|'):
                parts = line.split(sep, 1)
                if len(parts) == 2:
                    name = parts[0].strip()
                    url = parts[1].strip()
                    if re.match(r"https?://|rtmp://|rtsp://|rtp://", url, re.IGNORECASE):
                        entries.append({
                            'name': name,
                            'url': url,
                            'extinf_line': f'#EXTINF:-1,{name}'
                        })
                        break
    return entries


# ─────────────────────────────────────────────────────────────────────────────
# URL 规范化
# ─────────────────────────────────────────────────────────────────────────────
def normalize_url(url: str) -> str:
    """统一去除首尾空白和末尾斜杠，用于去重比较。"""
    return url.strip().rstrip("/")


# ─────────────────────────────────────────────────────────────────────────────
# 卫视排除规则：省份名（全称/简称）+ 卫视 → 属于卫视频道，不纳入地方频道
# ─────────────────────────────────────────────────────────────────────────────
_WEISHI_KEYWORDS = [
    "北京卫视", "天津卫视", "河北卫视", "山西卫视", "内蒙古卫视",
    "辽宁卫视", "吉林卫视", "黑龙江卫视", "黑龙卫视",
    "东方卫视", "上海卫视",
    "江苏卫视", "浙江卫视", "安徽卫视", "福建卫视", "江西卫视",
    "山东卫视", "河南卫视", "湖北卫视", "湖南卫视",
    "广东卫视", "南方卫视", "广西卫视", "海南卫视",
    "重庆卫视", "四川卫视", "贵州卫视", "云南卫视", "西藏卫视",
    "藏语卫视", "陕西卫视", "甘肃卫视", "青海卫视", "宁夏卫视", "新疆卫视",
]
# 每个关键词的汉字之间允许有任意空格，整体忽略大小写
_WEISHI_PATTERN = re.compile(
    '|'.join(r'\s*'.join(list(kw)) for kw in _WEISHI_KEYWORDS),
    re.IGNORECASE
)


def match_channel(name):
    """
    尝试匹配频道名到省份+标准名，返回 (province, standard_name) 或 None。
    若频道名命中"省份名+卫视"则直接排除，避免与已有卫视列表重复。
    """
    if _WEISHI_PATTERN.search(name):
        return None  # 卫视频道，跳过

    for province, patterns in COMPILED_PATTERNS.items():
        for std_name, pattern in patterns:
            if pattern.search(name):
                return province, std_name
    return None


def build_extinf(province, std_name):
    """构建新的 #EXTINF 行"""
    return f'#EXTINF:-1 group-title="省级地方频道",【{province}】{std_name}'


def main():
    input_dir = "sources"
    output_dir = os.path.join("sources", "temp")
    output_path = os.path.join(output_dir, "省级地方频道.m3u")

    os.makedirs(output_dir, exist_ok=True)

    print(f"📁 当前工作目录: {os.getcwd()}")
    print(f"📁 源文件目录: {input_dir}")
    print(f"📁 输出目录: {output_dir}")

    if not os.path.exists(input_dir):
        print(f"❌ 源目录不存在: {input_dir}")
        return

    # 支持的文件类型
    files = []
    for pattern in ["src-*.m3u", "src-*.m3u8", "src-*.txt"]:
        files.extend(glob.glob(os.path.join(input_dir, pattern)))

    # 排除 temp 目录及输出文件自身
    files = [f for f in files if not f.startswith(os.path.join(input_dir, "temp"))]
    files = [f for f in files if os.path.abspath(f) != os.path.abspath(output_path)]

    if not files:
        print(f"⚠️  在 {input_dir} 中未找到任何 m3u/txt 文件！")
        return

    # ── 按 src-<N> 自然数排序 ──
    files.sort(key=natural_sort_key)

    print(f"\n📂 共找到 {len(files)} 个文件（按自然数顺序）：")
    for f in files:
        print(f"   {os.path.basename(f)}")

    # 读取并解析所有文件
    all_entries = []
    for filepath in files:
        try:
            entries = parse_file_line_by_line(filepath)
            print(f"   {os.path.basename(filepath)}: 解析到 {len(entries)} 条记录")
            all_entries.extend(entries)
        except Exception as e:
            print(f"❌ 解析 {os.path.basename(filepath)} 失败：{e}")

    print(f"\n📊 共解析 {len(all_entries)} 条记录，开始匹配省级频道...")

    # 匹配 + 去重（按 URL 去重）
    seen_urls = set()
    province_results = OrderedDict((p, OrderedDict()) for p in PROVINCE_CHANNELS.keys())

    matched_count = 0
    dup_count = 0

    for entry in all_entries:
        result = match_channel(entry['name'])
        if result is None:
            continue
        province, std_name = result
        url = normalize_url(entry['url'])

        if url in seen_urls:
            dup_count += 1
            continue

        seen_urls.add(url)
        if std_name not in province_results[province]:
            province_results[province][std_name] = []
        province_results[province][std_name].append(url)
        matched_count += 1

    print(f"✅ 匹配成功 {matched_count} 条，过滤重复 URL {dup_count} 条\n")

    # 生成 m3u 文件
    lines = ['#EXTM3U']

    total_written = 0
    not_found = []

    print("📋 提取结果：")
    for province, name_url_map in province_results.items():
        if not name_url_map:
            not_found.append(province)
            continue
        lines.append(f'\n# ── {province} ──────────────────────')
        for std_name, urls in name_url_map.items():
            extinf = build_extinf(province, std_name)
            for url in urls:
                lines.append(extinf)
                lines.append(url)
            total_written += len(urls)
            print(f"  ✅ 【{province}】{std_name}（{len(urls)} 个源）")

    if not_found:
        print(f"\n⚠️  以下 {len(not_found)} 个省份未找到任何频道：")
        for p in not_found:
            print(f"   ✗ {p}")

    # 写入文件
    try:
        with open(output_path, 'w', encoding='utf-8-sig') as f:
            f.write('\n'.join(lines) + '\n')
        print(f"\n🎉 完成！共写入 {total_written} 条播放记录")
        print(f"📄 输出文件：{output_path}")
        print(f"📁 文件大小：{os.path.getsize(output_path)} 字节")
    except Exception as e:
        print(f"❌ 写入文件失败：{e}")


if __name__ == '__main__':
    main()
