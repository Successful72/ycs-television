#!/usr/bin/env python3
"""
Source Sync  —  fetch remote subscription feeds and save locally.

Environment variables (GitHub Secrets)
---------------------------------------
SRC_UA            : User-Agent string (required)
SRC_LINK_1 … 50  : Source URLs (gaps allowed)
CF_WORKER_URL     : Cloudflare Worker URL, e.g. https://xxxx.workers.dev/fetch
CF_WORKER_TOKEN   : Bearer token set in the Worker's environment variables

Fetch strategy
--------------
1. Try direct curl (fast, works for most URLs)
2. If HTTP 403 → retry via Cloudflare Worker (bypasses CF IP blocks)
3. If Worker also fails → skip
"""

import json
import os
import subprocess
import sys
import tempfile

# ── Configuration ─────────────────────────────────────────────────────────────

OUTPUT_DIR = "./sources"
MAX_INDEX  = 50
TIMEOUT    = 30   # seconds per request

M3U_MARKERS = ["#EXTM3U"]
TXT_MARKERS = ["#EXTINF", ",http://", ",https://", ",rtmp://", ",rtsp://"]


# ── Helpers ───────────────────────────────────────────────────────────────────

def detect_format(content: str) -> str | None:
    if any(m in content for m in M3U_MARKERS):
        return "m3u"
    if any(m in content for m in TXT_MARKERS):
        return "txt"
    return None


def curl_fetch(url: str, ua: str) -> tuple[str | None, int, str]:
    """
    Direct curl download.
    Returns (body, http_code, reason).
    body is None on failure.
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
            cmd, capture_output=True, text=True, timeout=TIMEOUT + 5
        )

        wout = result.stdout.strip().split("\t")
        http_code    = int(wout[0]) if wout and wout[0].isdigit() else 0
        final_url    = wout[1] if len(wout) > 1 else url
        num_redirect = wout[2] if len(wout) > 2 else "0"

        if num_redirect not in ("0", ""):
            print(f"    [redirect] x{num_redirect} -> HTTP {http_code}  {final_url}")

        if result.returncode != 0:
            err = result.stderr.strip()[:120]
            return None, 0, f"curl exit={result.returncode}  {err}"

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


def worker_fetch(url: str, ua: str, worker_url: str, token: str) -> tuple[str | None, str]:
    """
    Fetch via Cloudflare Worker proxy.
    Returns (body, reason).
    """
    payload = json.dumps({"url": url, "ua": ua})

    tmp_fd, tmp_path = tempfile.mkstemp(suffix=".tmp")
    os.close(tmp_fd)

    cmd = [
        "curl",
        "--silent",
        "--location",
        "--max-time", str(TIMEOUT),
        "--request", "POST",
        "--header", "Content-Type: application/json",
        "--header", f"Authorization: Bearer {token}",
        "--data", payload,
        "--output", tmp_path,
        "--write-out", "%{http_code}",
        worker_url,
    ]
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=TIMEOUT + 5
        )

        http_code = int(result.stdout.strip()) if result.stdout.strip().isdigit() else 0

        if result.returncode != 0 or http_code != 200:
            err = result.stderr.strip()[:80]
            return None, f"worker HTTP {http_code}  {err}"

        with open(tmp_path, "r", encoding="utf-8", errors="replace") as f:
            raw = f.read()

        data = json.loads(raw)
        target_status = data.get("status", 0)
        body          = data.get("body", "")

        if not (200 <= target_status < 300):
            return None, f"worker relayed HTTP {target_status}"

        return body, "ok"

    except (subprocess.TimeoutExpired, json.JSONDecodeError, KeyError) as e:
        return None, f"worker error: {e}"
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
    ua          = os.environ.get("SRC_UA", "").strip()
    worker_url  = os.environ.get("CF_WORKER_URL", "").strip()
    worker_token= os.environ.get("CF_WORKER_TOKEN", "").strip()

    if not ua:
        print("[fatal] SRC_UA is not set.")
        sys.exit(1)

    use_worker = bool(worker_url and worker_token)

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    print(f"Output : {os.path.abspath(OUTPUT_DIR)}")
    print(f"UA     : {ua[:72]}{'...' if len(ua) > 72 else ''}")
    print(f"Worker : {'enabled' if use_worker else 'disabled (CF_WORKER_URL or CF_WORKER_TOKEN not set)'}")
    print()

    saved   = 0
    skipped = 0

    for idx in range(1, MAX_INDEX + 1):
        key = f"SRC_LINK_{idx}"
        url = os.environ.get(key, "").strip()

        if not url:
            continue

        print(f"[{idx:02d}] {key}")

        # ── Step 1: direct request ────────────────────────────────────────
        content, http_code, reason = curl_fetch(url, ua)

        # ── Step 2: 403 → retry via Worker ───────────────────────────────
        if content is None and http_code == 403 and use_worker:
            print(f"    [direct] HTTP 403 — retrying via Worker...")
            content, reason = worker_fetch(url, ua, worker_url, worker_token)
            if content is not None:
                print(f"    [worker] ok")
            else:
                print(f"    [worker] {reason}")

        # ── Step 3: evaluate result ───────────────────────────────────────
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
