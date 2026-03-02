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
- Redirects (301/302/…) are followed automatically.
- Saved as  ./sources/src-N.<ext>  where ext is m3u or txt.
- Responses with no valid feed signature are silently skipped.
"""

import os
import sys

try:
    import requests
except ImportError:
    print("[fatal] 'requests' is not installed. Run: pip install requests")
    sys.exit(1)

# ── Configuration ─────────────────────────────────────────────────────────────

OUTPUT_DIR   = "./sources"
MAX_INDEX    = 50
TIMEOUT      = 30   # seconds

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


def fetch(url: str, ua: str) -> tuple[str | None, str]:
    """
    Download *url* via requests and return (body, reason).
    Body is None on any error; reason is a short diagnostic string.
    Redirects are followed automatically.
    """
    headers = {"User-Agent": ua}
    try:
        resp = requests.get(
            url,
            headers=headers,
            timeout=TIMEOUT,
            allow_redirects=True,   # follow 301/302/… automatically
        )

        # Surface the final URL after redirects for easier debugging
        if resp.history:
            hops = " → ".join(str(r.status_code) for r in resp.history)
            print(f"    [redirect] {hops} → {resp.status_code}  final: {resp.url}")

        if not resp.ok:
            return None, f"HTTP {resp.status_code} {resp.reason}"

        return resp.text, "ok"

    except requests.exceptions.Timeout:
        return None, "timeout"
    except requests.exceptions.TooManyRedirects:
        return None, "too many redirects"
    except requests.exceptions.ConnectionError as e:
        return None, f"connection error: {e}"
    except requests.exceptions.RequestException as e:
        return None, f"request error: {e}"


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
            continue    # gap in numbering — skip, keep scanning

        print(f"[{idx:02d}] {key}")

        content, reason = fetch(url, ua)

        if content is None:
            print(f"    → skip  ({reason})\n")
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
