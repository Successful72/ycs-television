import requests
import sys
import os
from pathlib import Path

def download_file():
    # 创建 sources 目录（如果不存在）
    sources_dir = Path("sources")
    sources_dir.mkdir(exist_ok=True)
    
    # 设置请求头，模拟 okhttp/3.12.13
    headers = {
        'User-Agent': 'okhttp/3.12.13'
    }
    
    # 下载 URL
    url = "sys.argv[1]"
    
    # 保存路径
    output_path = sources_dir / "src-13.txt"
    
    try:
        # 发送 GET 请求（自动处理重定向，相当于 curl -L）
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()  # 检查是否下载成功
        
        # 保存文件
        with open(output_path, 'wb') as f:
            f.write(response.content)
        
        print(f"文件已成功下载到: {output_path}")
        print(f"文件大小: {len(response.content)} 字节")
        
        # 列出 sources 目录的内容（用于验证）
        print("\nsources 目录内容:")
        for file in sources_dir.iterdir():
            print(f"  - {file.name}")
            
    except requests.exceptions.RequestException as e:
        print(f"下载失败: {e}")
        raise  # 在 GitHub Actions 中抛出异常以便工作流失败

if __name__ == "__main__":
    download_file()
