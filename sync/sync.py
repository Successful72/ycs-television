#!/usr/bin/env python3
"""
Source Sync  —  fetch remote subscription feeds and save locally.

Environment variables (GitHub Secrets)
---------------------------------------
SRC_UA             : User-Agent string (required)
SRC_LINK_1 … 50   : Source URLs (gaps allowed)
AUX_ENDPOINT       : Alternate endpoint URL (optional)
AUX_KEY            : Access key for alternate endpoint (optional)
"""

import json
import os
import subprocess
import sys
import tempfile

# ── Configuration ─────────────────────────────────────────────────────────────

OUTPUT_DIR = "./sources"
MAX_INDEX  = 50
TIMEOUT    = 30

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


def aux_fetch(url: str, ua: str, endpoint: str, key: str) -> tuple[str | None, str]:
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


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    ua       = os.environ.get("SRC_UA", "").strip()
    aux_url  = os.environ.get("AUX_ENDPOINT", "").strip()
    aux_key  = os.environ.get("AUX_KEY", "").strip()

    if not ua:
        print("[fatal] SRC_UA is not set.")
        sys.exit(1)

    use_aux = bool(aux_url and aux_key)

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    print(f"Output : {os.path.abspath(OUTPUT_DIR)}")
    print(f"UA     : {ua[:72]}{'...' if len(ua) > 72 else ''}")
    print(f"Aux    : {'enabled' if use_aux else 'disabled'}")
    print()

    saved   = 0
    skipped = 0

    for idx in range(1, MAX_INDEX + 1):
        key = f"SRC_LINK_{idx}"
        url = os.environ.get(key, "").strip()

        if not url:
            continue

        print(f"[{idx:02d}] {key}")

        content, http_code, reason = direct_fetch(url, ua)

        if content is None and http_code == 403 and use_aux:
            print(f"    [direct] {reason} — trying alternate route...")
            content, reason = aux_fetch(url, ua, aux_url, aux_key)
            if content is not None:
                print(f"    [alt] ok")
            else:
                print(f"    [alt] {reason}")

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
