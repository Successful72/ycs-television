"""
Upload processed M3U playlist to Cloudflare KV storage.

This script handles the first type of playlist file (complete_playlist_iptv).
The KV key is fixed as "complete_playlist_iptv" and requires no external configuration.

Required environment variables (configured in repository secrets):
  REMOTE_HOST         - Remote service host
  STORAGE_ACCOUNT_ID  - Account identifier
  STORAGE_NS_ID       - Storage namespace identifier
  STORAGE_API_TOKEN   - API access token (write permission)
"""

import os
import sys
import glob
import requests

_STORAGE_ENDPOINT = (
    "https://api.{host}/client/v4/accounts/{account_id}"
    "/storage/kv/namespaces/{namespace_id}/values/{key}"
)

# Fixed KV key for the processed/complete playlist
_KV_KEY = "complete_playlist_iptv"


def get_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        print(f"[ERROR] Environment variable '{name}' is not set or empty.")
        sys.exit(1)
    return value


def find_m3u_file(directory: str) -> str:
    for ext in ("*.m3u", "*.m3u8"):
        files = glob.glob(os.path.join(directory, ext))
        if files:
            if len(files) > 1:
                print(f"[WARNING] Multiple files found, using: {files[0]}")
            return files[0]
    print(f"[ERROR] No playlist file found in '{directory}'")
    sys.exit(1)


def push_content(host: str, account_id: str, namespace_id: str,
                 api_token: str, key: str, content: str) -> None:
    url = _STORAGE_ENDPOINT.format(
        host=host,
        account_id=account_id,
        namespace_id=namespace_id,
        key=key,
    )
    headers = {
        "Authorization": f"Bearer {api_token}",
        "Content-Type": "text/plain; charset=utf-8",
    }

    print(f"[INFO] Pushing playlist to remote storage, key='{key}' ...")
    resp = requests.put(url, headers=headers, data=content.encode("utf-8"))

    if resp.status_code == 200:
        print("[SUCCESS] Playlist pushed to remote storage successfully.")
    else:
        print(f"[ERROR] Push failed. HTTP {resp.status_code}: {resp.text}")
        sys.exit(1)


def main():
    source_dir = "./sources/output"

    remote_host  = get_env("REMOTE_HOST")
    account_id   = get_env("STORAGE_ACCOUNT_ID")
    namespace_id = get_env("STORAGE_NS_ID")
    api_token    = get_env("STORAGE_API_TOKEN")

    m3u_path = find_m3u_file(source_dir)
    print(f"[INFO] Found playlist file: {m3u_path}")

    with open(m3u_path, "r", encoding="utf-8") as f:
        content = f.read()

    print(f"[INFO] File size: {len(content.encode('utf-8'))} bytes")
    push_content(remote_host, account_id, namespace_id, api_token, _KV_KEY, content)


if __name__ == "__main__":
    main()
