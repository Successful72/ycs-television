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
- Redirects (301/302/…) are followed automatically via curl -L.
- curl sends ONLY the User-Agent header; no extra headers are injected,
  so servers that fingerprint okhttp/etc. will not reject the request.
- Saved as  ./sources/src-N.<ext>  where ext is m3u or txt.
- Responses with no valid feed signature are silently skipped.
"""

import os
import subprocess
import sys
import tempfile

# ── Configuration ─────────────────────────────────────────────────────────────

OUTPUT_DIR = "./sources"
MAX_INDEX  = 50
TIMEOUT    = 30   # seconds per request

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
    Download *url* via curl and return (body, reason).

    Key flags
    ---------
    --location   : follow 301/302/… redirects
    --user-agent : set UA; curl adds NO other fingerprint headers
    --output     : write body to a temp file (keeps stdout clean for --write-out)
    --write-out  : capture status code, final URL, redirect count
    """
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
            cmd,
            capture_output=True,
            text=True,
            timeout=TIMEOUT + 5,
        )

        wout = result.stdout.strip().split("\t")
        http_code    = int(wout[0]) if wout and wout[0].isdigit() else 0
        final_url    = wout[1] if len(wout) > 1 else url
        num_redirect = wout[2] if len(wout) > 2 else "0"

        if num_redirect not in ("0", ""):
            print(f"    [redirect] x{num_redirect} -> HTTP {http_code}  {final_url}")

        if result.returncode != 0:
            err = result.stderr.strip()[:120]
            return None, f"curl exit={result.returncode}  {err}"

        if http_code == 0:
            return None, "no response"
        if not (200 <= http_code < 300):
            return None, f"HTTP {http_code}"

        with open(tmp_path, "r", encoding="utf-8", errors="replace") as f:
            body = f.read()
        return body, "ok"

    except subprocess.TimeoutExpired:
        return None, "timeout"
    except FileNotFoundError:
        print("[fatal] curl is not installed or not in PATH")
        sys.exit(1)
    finally:
        try:
            os.remove(tmp_path)
        except OSError:
            pass


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    ua = os.environ.get("SRC_UA", "").strip()
    if not ua:
        print("[fatal] SRC_UA is not set.")
        sys.exit(1)

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    print(f"Output : {os.path.abspath(OUTPUT_DIR)}")
    print(f"UA     : {ua[:72]}{'...' if len(ua) > 72 else ''}")
    print()

    saved   = 0
    skipped = 0

    for idx in range(1, MAX_INDEX + 1):
        key = f"SRC_LINK_{idx}"
        url = os.environ.get(key, "").strip()

        if not url:
            continue

        print(f"[{idx:02d}] {key}")

        content, reason = fetch(url, ua)

        if content is None:
            print(f"    -> skip  ({reason})\n")
            skipped += 1
            continue

        if not content.strip():
            print("    -> skip  (empty response)\n")
            skipped += 1
            continue

        fmt = detect_format(content)
        if fmt is None:
            preview = content.strip()[:100].replace("\n", " ")
            print(f"    -> skip  (no feed signature)")
            print(f"       preview: {preview}\n")
            skipped += 1
            continue

        out_path = os.path.join(OUTPUT_DIR, f"src-{idx}.{fmt}")
        with open(out_path, "w", encoding="utf-8") as fh:
            fh.write(content)

        lines = content.count("\n")
        print(f"    -> saved  src-{idx}.{fmt}  ({lines} lines)\n")
        saved += 1

    print("-" * 48)
    print(f"Saved: {saved}   Skipped: {skipped}")


if __name__ == "__main__":
    main()
