#!/usr/bin/env python3
"""
Source Sync  —  fetch remote subscription feeds and save locally.

Environment variables
---------------------
SRC_UA        : User-Agent string (required)
SRC_LINK_1    : First source URL
SRC_LINK_2    : Second source URL
…
SRC_LINK_50   : Up to 50 source URLs

Rules
-----
- Numbering gaps are allowed; all 50 slots are scanned independently.
- Saved as  ./sources/src-N.<ext>  where ext is m3u or txt.
- Responses with no valid feed signature are silently skipped.
"""

import os
import subprocess
import sys

# ── Configuration ─────────────────────────────────────────────────────────────

OUTPUT_DIR   = "./sources"
MAX_INDEX    = 50
CURL_TIMEOUT = 30   # seconds per request

# Signatures that confirm the response is a valid feed
M3U_MARKERS = ["#EXTM3U"]
TXT_MARKERS = ["#EXTINF", ",http://", ",https://", ",rtmp://", ",rtsp://"]


# ── Helpers ───────────────────────────────────────────────────────────────────

def detect_format(content: str) -> str | None:
    """Return 'm3u', 'txt', or None if the content is not a valid feed."""
    if any(m in content for m in M3U_MARKERS):
        return "m3u"
    if any(m in content for m in TXT_MARKERS):
        return "txt"
    return None


def fetch(url: str, ua: str) -> str | None:
    """
    Download *url* via curl and return the response body.
    Returns None on any error (network, timeout, non-2xx, etc.).
    """
    cmd = [
        "curl",
        "--silent",
        "--fail",          # treat HTTP 4xx/5xx as errors
        "--max-time", str(CURL_TIMEOUT),
        "--user-agent", ua,
        url,
    ]
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=CURL_TIMEOUT + 5,
        )
        if result.returncode != 0:
            err = result.stderr.strip()[:120]
            print(f"    [curl] exit={result.returncode}  {err}")
            return None
        return result.stdout

    except subprocess.TimeoutExpired:
        print("    [timeout] request exceeded time limit")
        return None
    except FileNotFoundError:
        print("[fatal] curl is not installed or not in PATH")
        sys.exit(1)


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    ua = os.environ.get("SRC_UA", "").strip()
    if not ua:
        print("[fatal] SRC_UA is not set.")
        sys.exit(1)

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    print(f"Output : {os.path.abspath(OUTPUT_DIR)}")
    print(f"UA     : {ua[:72]}{'…' if len(ua) > 72 else ''}")
    print()

    saved   = 0
    skipped = 0

    for idx in range(1, MAX_INDEX + 1):
        key = f"SRC_LINK_{idx}"
        url = os.environ.get(key, "").strip()

        if not url:
            # Gap in numbering — skip this slot, keep scanning
            continue

        print(f"[{idx:02d}] {key}")

        content = fetch(url, ua)

        if content is None:
            print("    → skip  (fetch failed)\n")
            skipped += 1
            continue

        if not content.strip():
            print("    → skip  (empty response)\n")
            skipped += 1
            continue

        fmt = detect_format(content)
        if fmt is None:
            preview = content.strip()[:100].replace("\n", " ")
            print(f"    → skip  (no feed signature)")
            print(f"       preview: {preview}\n")
            skipped += 1
            continue

        out_path = os.path.join(OUTPUT_DIR, f"src-{idx}.{fmt}")
        with open(out_path, "w", encoding="utf-8") as fh:
            fh.write(content)

        lines = content.count("\n")
        print(f"    → saved  src-{idx}.{fmt}  ({lines} lines)\n")
        saved += 1

    print("─" * 48)
    print(f"Saved: {saved}   Skipped: {skipped}")


if __name__ == "__main__":
    main()
