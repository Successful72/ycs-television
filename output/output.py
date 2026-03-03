import os
import requests

# 从环境变量读取（GitHub Actions 自动提供）
GITHUB_TOKEN = os.environ["GITHUB_TOKEN"]
REPO = os.environ["GITHUB_REPOSITORY"]  # 格式：owner/repo
TAG = os.environ.get("RELEASE_TAG", "latest")  # 可在 workflow 中自定义

FILE_PATH = "./sources/output/我的电视节目.m3u"
FILE_NAME = "我的电视节目.m3u"

headers = {
    "Authorization": f"token {GITHUB_TOKEN}",
    "Accept": "application/vnd.github+json",
}
api_base = f"https://api.github.com/repos/{REPO}"

# 查找或创建 Release
res = requests.get(f"{api_base}/releases/tags/{TAG}", headers=headers)

if res.status_code == 200:
    release = res.json()
    print(f"找到已有 Release：{TAG}")
else:
    # 创建新 Release
    payload = {"tag_name": TAG, "name": TAG, "draft": False, "prerelease": False}
    res = requests.post(f"{api_base}/releases", json=payload, headers=headers)
    res.raise_for_status()
    release = res.json()
    print(f"已创建新 Release：{TAG}")

release_id = release["id"]

# 删除同名旧文件（避免重复）
for asset in release.get("assets", []):
    if asset["name"] == FILE_NAME:
        requests.delete(f"{api_base}/releases/assets/{asset['id']}", headers=headers)
        print(f"已删除旧文件：{FILE_NAME}")

# 上传新文件
upload_url = f"https://uploads.github.com/repos/{REPO}/releases/{release_id}/assets?name={FILE_NAME}"
with open(FILE_PATH, "rb") as f:
    upload_res = requests.post(
        upload_url,
        headers={**headers, "Content-Type": "application/octet-stream"},
        data=f,
    )
upload_res.raise_for_status()
print(f"上传成功：{upload_res.json()['browser_download_url']}")
