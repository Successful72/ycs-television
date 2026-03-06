#!/usr/bin/env python3
"""
Source Sync  —  fetch remote subscription feeds and save locally.

Environment variables (GitHub Secrets/Variables)
-------------------------------------------------
SRC_UA          : User-Agent string (required)
AUX_ENDPOINT    : Cloudflare Pages domain, e.g. 123456.xyz (required)
AUX_KEY         : Access key appended directly to endpoint URL (required)
SRC_LOC         : Two lines:
                    Line 1 — path for normal URLs,  e.g. /src_urls/normal
                    Line 2 — path for special URLs, e.g. /src_urls/special
"""

import os
import subprocess
import sys
import tempfile
from datetime import datetime, timezone

# ── Configuration ─────────────────────────────────────────────────────────────

OUTPUT_DIR = "./sources"
LOG_PATH   = "./logs/logs.txt"
TIMEOUT    = 60   # seconds per request

M3U_MARKERS = ["#EXTM3U"]
TXT_MARKERS = ["#EXTINF", ",http://", ",https://", ",rtmp://", ",rtsp://"]


# ── Helpers ───────────────────────────────────────────────────────────────────

def detect_format(content: str) -> str | None:
    if any(m in content for m in M3U_MARKERS):
        return "m3u"
    if any(m in content for m in TXT_MARKERS):
        return "txt"
    return None


def direct_fetch(url: str, ua: str) -> tuple[str | None, int, str]:
    """Direct curl download. Returns (body, http_code, reason)."""
    tmp_fd, tmp_path = tempfile.mkstemp(suffix=".tmp")
    os.close(tmp_fd)

    cmd = [
        "curl",
        "--silent",
        "--location",
        "--max-time", str(TIMEOUT),
        "--user-agent", ua,
        "--output", tmp_path,
        "--write-out", "%{http_code}\t%{url_effective}\t%{num_redirects}",
        url,
    ]
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=TIMEOUT + 5
        )

        wout      = result.stdout.strip().split("\t")
        http_code = int(wout[0]) if wout and wout[0].isdigit() else 0
        final_url = wout[1] if len(wout) > 1 else url
        n_redir   = wout[2] if len(wout) > 2 else "0"

        if n_redir not in ("0", ""):
            print(f"    [redirect] x{n_redir} -> HTTP {http_code}  {final_url}")

        if result.returncode != 0:
            err = result.stderr.strip()[:120]
            return None, http_code, f"curl exit={result.returncode}  {err}"
        if http_code == 0:
            return None, 0, "no response"
        if not (200 <= http_code < 300):
            return None, http_code, f"HTTP {http_code}"

        with open(tmp_path, "r", encoding="utf-8", errors="replace") as f:
            body = f.read()
        return body, http_code, "ok"

    except subprocess.TimeoutExpired:
        return None, 0, "timeout"
    except FileNotFoundError:
        print("[fatal] curl is not installed or not in PATH")
        sys.exit(1)
    finally:
        try:
            os.remove(tmp_path)
        except OSError:
            pass


def fetch_url_list(endpoint: str, loc: str, key: str, ua: str) -> str | None:
    """
    Fetch URL list from Cloudflare Pages via POST request.
    Final URL: https://<endpoint><loc><key>
    Returns raw response text, or None on failure.
    """
    url = f"https://{endpoint}{loc}{key}"
    print(f"  Fetching URL list: {url}")
    body, _, reason = direct_fetch(url, ua)
    
    # 👇 就加这一行
    print(f"  [DEBUG] Response content:\n{body}\n")
    
    if body is None:
        print(f"  [error] {reason}")
    return body

    tmp_fd, tmp_path = tempfile.mkstemp(suffix=".tmp")
    os.close(tmp_fd)

    cmd = [
        "curl",
        "--silent",
        "--location",
        "--max-time", str(TIMEOUT),
        "--request", "POST",
        "--user-agent", ua,
        "--output", tmp_path,
        "--write-out", "%{http_code}",
        url,
    ]
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=TIMEOUT + 5
        )
        http_code = int(result.stdout.strip()) if result.stdout.strip().isdigit() else 0

        if result.returncode != 0 or not (200 <= http_code < 300):
            print(f"  [error] HTTP {http_code}")
            return None

        with open(tmp_path, "r", encoding="utf-8", errors="replace") as f:
            return f.read()

    except subprocess.TimeoutExpired:
        print("  [error] timeout")
        return None
    except FileNotFoundError:
        print("[fatal] curl is not installed or not in PATH")
        sys.exit(1)
    finally:
        try:
            os.remove(tmp_path)
        except OSError:
            pass


def parse_normal_urls(text: str) -> list[tuple[int, str]]:
    """
    Parse normal URL list text.
    Expected format (one per line):
        URL-1: https://example.com/feed.m3u
        URL-2: https://example.com/feed2.m3u
    Returns list of (number, url), sorted by number.
    """
    results = []
    for line in text.splitlines():
        line = line.strip()
        if not line or ":" not in line:
            continue
        key_part, _, val = line.partition(":")
        key_part = key_part.strip().lower()
        val = val.strip()
        if key_part.startswith("url-"):
            try:
                num = int(key_part[4:])   # "url-" is 4 chars
                if val:
                    results.append((num, val))
            except ValueError:
                pass
    return sorted(results, key=lambda x: x[0])


def parse_special_urls(text: str) -> list[tuple[int, str, str | None]]:
    """
    Parse special URL list text.
    Expected format (pairs of lines per entry):
        URL-1: https://example.com/feed.m3u
        scripts_path_1: ./scripts/fetch1.py
        URL-2: https://example.com/feed2.m3u
        scripts_path_2: ./scripts/fetch2.py
    Returns list of (number, url, script_path_or_None), sorted by number.
    Entries with no URL are dropped entirely.
    """
    data: dict[int, dict] = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or ":" not in line:
            continue
        key_part, _, val = line.partition(":")
        key_part = key_part.strip().lower()
        val = val.strip()

        if key_part.startswith("url-"):
            try:
                num = int(key_part[4:])
                data.setdefault(num, {})["url"] = val
            except ValueError:
                pass
        elif key_part.startswith("scripts_path_"):
            try:
                num = int(key_part[len("scripts_path_"):])
                data.setdefault(num, {})["script"] = val
            except ValueError:
                pass

    results = []
    for num in sorted(data.keys()):
        entry = data[num]
        url   = entry.get("url", "")
        if not url:
            continue
        results.append((num, url, entry.get("script") or None))
    return results


def run_special_script(script_path: str, url: str) -> bool:
    """
    Execute a special py script, passing the URL as a command-line argument.
    The script is responsible for saving the output file under OUTPUT_DIR.
    Returns True if the script exited successfully.
    """
    if not os.path.isfile(script_path):
        print(f"    -> skip  (script not found: {script_path})")
        return False

    try:
        result = subprocess.run(
            [sys.executable, script_path, url],
            timeout=TIMEOUT + 30,
            text=True,
        )
        if result.returncode == 0:
            print(f"    -> script executed successfully")
            return True
        else:
            print(f"    -> skip  (script exited with code {result.returncode})")
            return False
    except subprocess.TimeoutExpired:
        print(f"    -> skip  (script timeout)")
        return False


def write_log(failed_normal: list[int], failed_special: list[int]) -> None:
    """Write failed link numbers to log file, overwriting any previous log."""
    if not failed_normal and not failed_special:
        try:
            os.remove(LOG_PATH)
        except OSError:
            pass
        return

    os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    with open(LOG_PATH, "w", encoding="utf-8") as f:
        f.write(f"# {ts}\n")
        for idx in failed_normal:
            f.write(f"普通链接 {idx} 号获取不到有效文件，可能已失效。\n")
        for idx in failed_special:
            f.write(f"特殊链接 {idx} 号获取不到有效文件，可能已失效。\n")
    total = len(failed_normal) + len(failed_special)
    print(f"\nLog written -> {LOG_PATH}  ({total} item(s))")


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    ua          = os.environ.get("SRC_UA", "").strip()
    endpoint    = os.environ.get("AUX_ENDPOINT", "").strip()
    key         = os.environ.get("AUX_KEY", "").strip()
    src_loc_raw = os.environ.get("SRC_LOC", "")

    if not ua:
        print("[fatal] SRC_UA is not set.")
        sys.exit(1)
    if not endpoint:
        print("[fatal] AUX_ENDPOINT is not set.")
        sys.exit(1)
    if not key:
        print("[fatal] AUX_KEY is not set.")
        sys.exit(1)

    # SRC_LOC: line 1 = normal path, line 2 = special path
    loc_lines = [l.strip() for l in src_loc_raw.splitlines() if l.strip()]
    if len(loc_lines) < 2:
        print("[fatal] SRC_LOC must contain two lines: normal path and special path.")
        sys.exit(1)
    loc_normal  = loc_lines[0]
    loc_special = loc_lines[1]

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    print(f"Output   : {os.path.abspath(OUTPUT_DIR)}")
    print(f"UA       : {ua[:72]}{'...' if len(ua) > 72 else ''}")
    print(f"Endpoint : {endpoint}")
    print()

    saved_normal    = 0
    skipped_normal  = 0
    failed_normal: list[int] = []

    saved_special   = 0
    skipped_special = 0
    failed_special: list[int] = []

    # ── Normal URLs ───────────────────────────────────────────────────────────
    print("=== Normal URLs ===")
    normal_text = fetch_url_list(endpoint, loc_normal, key, ua)
    if not normal_text:
        print("[warning] Could not fetch normal URL list — skipping.\n")
    else:
        normal_urls = parse_normal_urls(normal_text)
        print(f"Found {len(normal_urls)} normal URL(s)\n")

        for idx, url in normal_urls:
            print(f"[N-{idx:02d}] link {idx}")

            content, _, reason = direct_fetch(url, ua)

            if content is None:
                print(f"    -> skip  ({reason})\n")
                skipped_normal += 1
                failed_normal.append(idx)
                continue

            if not content.strip():
                print("    -> skip  (empty response)\n")
                skipped_normal += 1
                failed_normal.append(idx)
                continue

            fmt = detect_format(content)
            if fmt is None:
                preview = content.strip()[:100].replace("\n", " ")
                print(f"    -> skip  (no feed signature)")
                print(f"       preview: {preview}\n")
                skipped_normal += 1
                failed_normal.append(idx)
                continue

            out_path = os.path.join(OUTPUT_DIR, f"src-{idx}.{fmt}")
            with open(out_path, "w", encoding="utf-8") as fh:
                fh.write(content)

            lines = content.count("\n")
            print(f"    -> saved  src-{idx}.{fmt}  ({lines} lines)\n")
            saved_normal += 1

    # ── Special URLs ──────────────────────────────────────────────────────────
    print("=== Special URLs ===")
    special_text = fetch_url_list(endpoint, loc_special, key, ua)
    if not special_text:
        print("[warning] Could not fetch special URL list — skipping.\n")
    else:
        special_urls = parse_special_urls(special_text)
        print(f"Found {len(special_urls)} special URL(s)\n")

        for idx, url, script_path in special_urls:
            print(f"[S-{idx:02d}] link {idx}  url={url[:72]}{'...' if len(url) > 72 else ''}")

            if script_path is None:
                print(f"    -> skip  (no script path defined)\n")
                skipped_special += 1
                failed_special.append(idx)
                continue

            success = run_special_script(script_path, url)
            if success:
                saved_special += 1
            else:
                skipped_special += 1
                failed_special.append(idx)
            print()

    # ── Summary ───────────────────────────────────────────────────────────────
    print("-" * 48)
    print(f"Normal  — Saved: {saved_normal}   Skipped: {skipped_normal}")
    print(f"Special — Saved: {saved_special}   Skipped: {skipped_special}")

    write_log(failed_normal, failed_special)


if __name__ == "__main__":
    main()
