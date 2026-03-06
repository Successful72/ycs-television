import requests
import os
import sys
from pathlib import Path

def download_file(url, output_filename="iptv-8.txt"):
    """从指定 URL 下载文件到 sources 目录"""
    
    sources_dir = Path("sources")
    sources_dir.mkdir(exist_ok=True)
    
    headers = {
        'User-Agent': 'okhttp/3.12.13'
    }
    
    output_path = sources_dir / output_filename
    
    try:
        print(f"开始从 {url} 下载...")
        
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        
        with open(output_path, 'wb') as f:
            f.write(response.content)
        
        print(f"✅ 文件已成功下载到: {output_path}")
        print(f"📊 文件大小: {len(response.content)} 字节")
        
        return True
            
    except requests.exceptions.RequestException as e:
        print(f"❌ 下载失败: {e}")
        return False

if __name__ == "__main__":
    # 检查命令行参数
    if len(sys.argv) < 2:
        print("❌ 错误: 请提供下载 URL")
        print("使用方法: python download_script.py <URL> [输出文件名]")
        print("示例: python download_script.py https://example.com/file.txt myfile.txt")
        sys.exit(1)
    
    # 获取 URL
    url = sys.argv[1]
    
    # 获取输出文件名（如果提供了）
    output_filename = sys.argv[2] if len(sys.argv) > 2 else "iptv-8.txt"
    
    # 执行下载
    success = download_file(url, output_filename)
    
    # 根据结果返回退出码
    sys.exit(0 if success else 1)
