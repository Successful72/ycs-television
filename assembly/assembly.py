import os
import glob

# 查找所有 m3u 文件，按创建时间排序
m3u_files = glob.glob("./sources/*.m3u", recursive=True)
m3u_files.sort(key=lambda f: os.path.getctime(f))

output_dir = "./sources/output"
output_path = os.path.join(output_dir, "我的电视节目.m3u")

os.makedirs(output_dir, exist_ok=True)

merged_blocks = []

for filepath in m3u_files:
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read().strip()
    if content:
        merged_blocks.append(content)
        print(f"已读取：{filepath}")

# 用空行分隔各文件内容
merged_content = "\n\n".join(merged_blocks)

with open(output_path, "w", encoding="utf-8") as f:
    f.write(merged_content + "\n")

print(f"合并完成，已保存至：{output_path}")
