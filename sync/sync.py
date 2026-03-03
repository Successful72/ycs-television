#!/usr/bin/env python3
"""
Source Sync  —  fetch remote subscription feeds and save locally.

Environment variables (GitHub Secrets)
---------------------------------------
SRC_UA          : User-Agent string (required)
SRC_LINKS       : All source URLs, one per line (blank lines ignored)
AUX_ENDPOINT    : Alternate endpoint URL (optional)
AUX_KEY         : Access key for alternate endpoint (optional)
"""

import json
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


def aux_fetch(url: str, ua: str, endpoint: str, key: str) -> tuple[str | None, str]:
    """Fetch via alternate endpoint. Returns (body, reason)."""
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
        "--header", f"Authorization: Bearer {key}",
        "--data", payload,
        "--output", tmp_path,
        "--write-out", "%{http_code}",
        endpoint,
    ]
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=TIMEOUT + 5
        )

        http_code = int(result.stdout.strip()) if result.stdout.strip().isdigit() else 0

        if result.returncode != 0 or http_code != 200:
            return None, f"endpoint HTTP {http_code}"

        with open(tmp_path, "r", encoding="utf-8", errors="replace") as f:
            raw = f.read()

        data   = json.loads(raw)
        status = data.get("status", 0)
        body   = data.get("body", "")

        if not (200 <= status < 300):
            return None, f"upstream HTTP {status}"

        return body, "ok"

    except (subprocess.TimeoutExpired, json.JSONDecodeError, KeyError) as e:
        return None, f"error: {e}"
    except FileNotFoundError:
        print("[fatal] curl is not installed or not in PATH")
        sys.exit(1)
    finally:
        try:
            os.remove(tmp_path)
        except OSError:
            pass


def write_log(failed: list[int]) -> None:
    """Write failed link numbers to log file, overwriting any previous log."""
    if not failed:
        # No failures — remove stale log if it exists
        try:
            os.remove(LOG_PATH)
        except OSError:
            pass
        return

    os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    with open(LOG_PATH, "w", encoding="utf-8") as f:
        f.write(f"# {ts}\n")
        for idx in failed:
            f.write(f"{idx}号链接获取不到有效文件，可能已失效。\n")
    print(f"\nLog written -> {LOG_PATH}  ({len(failed)} item(s))")


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    ua       = os.environ.get("SRC_UA", "").strip()
    aux_url  = os.environ.get("AUX_ENDPOINT", "").strip()
    aux_key  = os.environ.get("AUX_KEY", "").strip()
    src_raw  = os.environ.get("SRC_LINKS", "")

    if not ua:
        print("[fatal] SRC_UA is not set.")
        sys.exit(1)

    # Parse URLs: one per line, skip blanks
    urls = [line.strip() for line in src_raw.splitlines() if line.strip()]
    if not urls:
        print("[fatal] SRC_LINKS is empty or not set.")
        sys.exit(1)

    use_aux = bool(aux_url and aux_key)

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    print(f"Output : {os.path.abspath(OUTPUT_DIR)}")
    print(f"UA     : {ua[:72]}{'...' if len(ua) > 72 else ''}")
    print(f"Aux    : {'enabled' if use_aux else 'disabled'}")
    print(f"Total  : {len(urls)} link(s)")
    print()

    saved   = 0
    skipped = 0
    failed  = []   # indices of links that could not be saved

    for idx, url in enumerate(urls, start=1):
        print(f"[{idx:02d}] link {idx}")

        # ── Step 1: direct ────────────────────────────────────────────────
        content, http_code, reason = direct_fetch(url, ua)

        # ── Step 2: any failure → try alternate route ─────────────────────
        if content is None and use_aux:
            print(f"    [direct] {reason} — trying alternate route...")
            content, reason = aux_fetch(url, ua, aux_url, aux_key)
            if content is not None:
                print(f"    [alt] ok")
            else:
                print(f"    [alt] {reason}")

        # ── Step 3: evaluate ──────────────────────────────────────────────
        if content is None:
            print(f"    -> skip  ({reason})\n")
            skipped += 1
            failed.append(idx)
            continue

        if not content.strip():
            print("    -> skip  (empty response)\n")
            skipped += 1
            failed.append(idx)
            continue

        fmt = detect_format(content)
        if fmt is None:
            preview = content.strip()[:100].replace("\n", " ")
            print(f"    -> skip  (no feed signature)")
            print(f"       preview: {preview}\n")
            skipped += 1
            failed.append(idx)
            continue

        out_path = os.path.join(OUTPUT_DIR, f"src-{idx}.{fmt}")
        with open(out_path, "w", encoding="utf-8") as fh:
            fh.write(content)

        lines = content.count("\n")
        print(f"    -> saved  src-{idx}.{fmt}  ({lines} lines)\n")
        saved += 1

    print("-" * 48)
    print(f"Saved: {saved}   Skipped: {skipped}")

    write_log(failed)


if __name__ == "__main__":
    main()
