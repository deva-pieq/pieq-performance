#!/usr/bin/env python3
"""Run the full ICM performance test pipeline.

1. Runs the all-roles sitespeed tests (Ops Manager, Agency Owner, Agent)
2. Asks the opencode CLI to read the latest results and explain performance in plain business language
3. Injects the explanation into the custom dashboard (custom-dashboard/index.html) as a new card
   rendered at the end of the page

Usage:
    python3 tools/run-performance.py                 # preprod (matches run-all-roles default)
    python3 tools/run-performance.py --prod          # production environment
    python3 tools/run-performance.py -n 3            # 3 sitespeed iterations per page
    python3 tools/run-performance.py --skip-command  # use existing results, no new test run
"""

from __future__ import annotations

import argparse
import html
import json
import os
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DASHBOARD_FILE = ROOT / "custom-dashboard" / "index.html"
DATA_FILE = ROOT / "custom-dashboard" / "perf-data.json"
SUMMARY_FILE = ROOT / "custom-dashboard" / "performance-summary.md"
RUN_LOG = ROOT / "run-performance.log"

OPENCODE_TIMEOUT_S = 900

ANALYST_PROMPT = """\
You are a performance analyst at an insurance company, writing for a NON-TECHNICAL \
business audience (managers, product owners, executives).

Read the attached JSON file perf-data.json. It is the latest performance measurement \
of the ICM platform, taken by sitespeed.io, for three roles: Ops Manager, Agency Owner, \
and Agent. Each role has a list of measured pages. For every page you are given: \
loadMs (time until the page is fully loaded), onLoadMs, lcpMs, requests (number of \
network calls), reqSize and resSize (data sent and received), and the top 5 slowest \
requests.

Produce ONE well-structured, human-friendly markdown document with these sections:

1. "Executive summary" - 3 to 5 bullets a manager can read in 30 seconds, calling out \
the overall health of the platform and the biggest issues.
2. "Role by role" - for each role, a few sentences in plain language: how fast the \
platform feels overall for that user, the fastest pages and the slowest pages (give the \
approximate seconds each takes to fully load and how many data requests it makes), and \
what that means for the people using it.
3. "Pages that need attention" - a short list of the worst offenders with a plain-why \
(long load, many requests, heavy data) and one practical business-level suggestion for \
each (e.g. reduce data, fewer requests, caching, defer non-critical content).
4. "Recommended next steps" - at most 5 prioritized, actionable items, each phrased as \
a business outcome (not technical jargon).

Guidelines:
- Write ONLY readable markdown: ## headings, **bold**, - bullets, numbered steps, short \
paragraphs. No tables, no code fences, no JSON.
- Translate numbers into human meaning. Instead of "loadMs is 4123" say "The Dashboard \
takes just over 4 seconds to fully load, which makes the page feel sluggish and can lose \
user attention."
- Use these plain categories based on time until fully loaded: under ~2.5s = fast, \
2.5-4s = acceptable, over 4s = slow and needs attention. State the category next to the \
numbers.
- Do NOT modify any files and do NOT run any commands. Only analyze the attached data.
- Your entire final message must be the finished markdown document and nothing else."""


def log(msg: str) -> None:
    print(f"[run-performance] {msg}", flush=True)


def write_stdout(text: str) -> None:
    buffer = getattr(sys.stdout, "buffer", None)
    if buffer is not None:
        try:
            buffer.write(text.encode("utf-8", "replace"))
            buffer.flush()
        except Exception:
            sys.stdout.write(text)
            sys.stdout.flush()
    else:
        sys.stdout.write(text)
        sys.stdout.flush()


def run_command_logged(cmd: list[str], log_path: Path, env: dict | None = None) -> int:
    proc = subprocess.Popen(
        cmd,
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
        env=env,
    )
    with log_path.open("a", encoding="utf-8") as fh:
        for line in proc.stdout:
            write_stdout(line)
            fh.write(line)
    proc.wait()
    return proc.returncode


def _is_windows() -> bool:
    return sys.platform == "win32"


def run_all_roles(extra_args: list[str], log_path: Path) -> int:
    if _is_windows():
        label = "run-all-roles.cmd"
        cmd = ["cmd.exe", "/c", "run-all-roles.cmd", *extra_args]
    else:
        label = "run-all-roles.sh"
        cmd = ["bash", str(ROOT / "run-all-roles.sh"), *extra_args]
    log(f"Starting {label}" + (f" with args: {' '.join(extra_args)}" if extra_args else ""))
    log(f"Output being streamed to {RUN_LOG.name}")
    header = f"\n===== {label} started {datetime.now():%Y-%m-%d %H:%M:%S} =====\n"
    with log_path.open("a", encoding="utf-8") as fh:
        fh.write(header)
    env = os.environ.copy()
    env["SKIP_AI_SUMMARY"] = "1"
    code = run_command_logged(cmd, log_path, env=env)
    with log_path.open("a", encoding="utf-8") as fh:
        fh.write(f"===== {label} finished (code {code}) {datetime.now():%Y-%m-%d %H:%M:%S} =====\n")
    if code != 0:
        log(f"WARNING: {label} exited with code {code}. Continuing anyway.")
    return code


def find_opencode() -> list[str]:
    home = Path.home()
    if _is_windows():
        direct = home / "AppData" / "Roaming" / "npm" / "node_modules" / "opencode-ai" / "bin" / "opencode.exe"
        if direct.exists():
            return [str(direct)]
        exe = shutil.which("opencode.exe")
        if exe:
            return [exe]
        shim = shutil.which("opencode.cmd") or shutil.which("opencode")
        if shim:
            return ["cmd.exe", "/c", shim]
    else:
        user_bin = home / ".npm-global" / "bin" / "opencode"
        if user_bin.exists():
            return [str(user_bin)]
        exe = shutil.which("opencode")
        if exe:
            return [exe]
    raise SystemExit(
        "Could not locate the opencode CLI. Install it with:  npm install -g opencode-ai --prefix \"$HOME/.npm-global\""
    )


def summarize_with_opencode(data_file: Path, summary_file: Path, timeout_s: int) -> str:
    prefix = find_opencode()
    cmd = [*prefix, "run", "--format", "default", ANALYST_PROMPT, "-f", str(data_file)]
    log(f"Running opencode to explain results: {' '.join(cmd[:5])} ...")
    log("This can take a few minutes (model analysis) - please wait.")
    t0 = time.time()
    env = os.environ.copy()
    npm_bin = str(Path.home() / ".npm-global" / "bin")
    env["PATH"] = npm_bin + os.pathsep + env.get("PATH", "")
    proc = subprocess.Popen(
        cmd,
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
        env=env,
    )
    try:
        out, err = proc.communicate(timeout=timeout_s)
    except subprocess.TimeoutExpired:
        proc.kill()
        out, err = proc.communicate()
        seconds = int(time.time() - t0)
        raise TimeoutError(f"opencode took more than {seconds}s and was stopped.")
    if proc.returncode != 0:
        tail = " | ".join(err.strip().splitlines()[-5:])
        raise RuntimeError(f"opencode exited with code {proc.returncode}: {tail}")
    summary = (out or "").strip()
    if not summary:
        raise RuntimeError(f"opencode returned an empty summary. stderr tail: {' | '.join((err or '').strip().splitlines()[-3:])}")
    summary_file.write_text(summary + "\n", encoding="utf-8")
    log(f"Summary written to {summary_file.name} ({len(summary)} chars in "
        f"{int(time.time() - t0)}s).")
    return summary


def extract_dashboard_data(dashboard_file: Path) -> str:
    text = dashboard_file.read_text(encoding="utf-8", errors="replace")
    m = re.search(r'<script\s+id="data"\s+type="application/json">(.*?)</script>', text, re.S)
    if not m:
        raise RuntimeError(f"No embedded data block found in {dashboard_file}")
    payload = m.group(1).strip()
    json.loads(payload)
    return payload


BOLD_RE = re.compile(r"\*\*(.+?)\*\*")
ITALIC_RE = re.compile(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)")
CODE_RE = re.compile(r"`([^`]+)`")


def md_inline(text: str) -> str:
    text = html.escape(text)
    text = CODE_RE.sub(r"<code>\1</code>", text)
    text = BOLD_RE.sub(r"<strong>\1</strong>", text)
    text = ITALIC_RE.sub(r"<em>\1</em>", text)
    return text


def md_to_html(md_text: str) -> str:
    lines = md_text.splitlines()
    blocks: list[str] = []
    para: list[str] = []
    list_buf: list[tuple[str, str]] = []

    def flush_para() -> None:
        if para:
            blocks.append(f"<p>{md_inline(' '.join(para))}</p>")
            para.clear()

    def flush_list() -> None:
        if list_buf:
            tag = "ol" if list_buf[0][0] == "ol" else "ul"
            items = "".join(
                f"<li>{item}</li>" for _, item in list_buf
            )
            blocks.append(f"<{tag}>{items}</{tag}>")
            list_buf.clear()

    def flush_all() -> None:
        flush_para()
        flush_list()

    for raw in lines:
        line = raw.rstrip()
        if not line.strip():
            flush_all()
            continue
        if re.match(r"^#{1,6}\s+", line):
            flush_all()
            match = re.match(r"^(#{1,6})\s+(.*)$", line)
            level = len(match.group(1)) + 2
            if level > 6:
                level = 6
            blocks.append(f"<h{level}>{md_inline(match.group(2))}</h{level}>")
            continue
        ordered = re.match(r"^\s*\d+[.)]\s+(.*)$", line)
        bullet = re.match(r"^\s*[-*]\s+(.*)$", line)
        if bullet or ordered:
            flush_para()
            mode = "ol" if ordered else "ul"
            if list_buf and list_buf[0][0] != mode:
                flush_list()
            list_buf.append((mode, md_inline((ordered or bullet).group(1))))
            continue
        if re.match(r"^\s*(?:-{3,}|\*{3,}|_{3,})\s*$", line):
            flush_all()
            blocks.append("<hr/>")
            continue
        para.append(line)
    flush_all()
    return "\n".join(blocks)


def read_summary(summary_file: Path) -> str:
    if not summary_file.exists():
        return ""
    text = summary_file.read_text(encoding="utf-8", errors="replace").strip()
    return md_to_html(text)


def build_card(generated_at: str, body_html: str, source: str) -> str:
    if body_html:
        status = '<span class="perf-badge ok">ok</span>'
    else:
        body_html = (
            "<p><strong>No summary could be generated.</strong> "
            "The performance tests may have failed or produced no data.</p>"
        )
        status = '<span class="perf-badge none">incomplete</span>'
    return f"""<section id="perf-summary" class="perf-card">
  <style>
    #perf-summary {{ max-width: 1200px; margin: 0 auto; padding: 4px 32px 40px; font: 14px/1.6 "IBM Plex Sans", "Segoe UI", sans-serif; color: #1c1915; }}
    @media (max-width: 900px) {{ #perf-summary {{ padding: 4px 16px 32px; }} }}
    #perf-summary .perf-head {{ display: flex; align-items: baseline; justify-content: space-between; gap: 12px; flex-wrap: wrap; margin-bottom: 10px; }}
    #perf-summary h2 {{ font-size: 18px; margin: 0; font-weight: 650; letter-spacing: -0.02em; }}
    #perf-summary .perf-date {{ color: #6b645b; font-size: 12px; }}
    #perf-summary .perf-badge {{ display: inline-block; padding: 1px 8px; border-radius: 10px; font-size: 11px; font-weight: 600; vertical-align: middle; }}
    #perf-summary .perf-badge.ok {{ background: #e7f4ea; color: #1b5e20; }}
    #perf-summary .perf-badge.none {{ background: #fdeaea; color: #b3261e; }}
    #perf-summary .perf-body {{ background: #fffdf8; border: 1px solid #ddd6c8; border-top: 3px solid #9a3412; padding: 14px 20px; }}
    #perf-summary h3, #perf-summary h4 {{ margin: 14px 0 6px; color: #9a3412; }}
    #perf-summary h3:first-child {{ margin-top: 4px; }}
    #perf-summary h4 {{ font-size: 14px; }}
    #perf-summary p {{ margin: 6px 0; }}
    #perf-summary ul, #perf-summary ol {{ margin: 6px 0; padding-left: 22px; }}
    #perf-summary li {{ margin: 3px 0; }}
    #perf-summary strong {{ color: #1b5e20; }}
    #perf-summary code {{ background: #efe8db; padding: 1px 4px; border-radius: 3px; font-size: 12px; }}
    #perf-summary hr {{ border: 0; border-top: 1px dashed #ddd6c8; margin: 12px 0; }}
  </style>
  <div class="perf-head">
    <h2>Page performance summary — business view</h2>
    <span class="perf-date">Generated {generated_at} · status {status} · from {html.escape(source)}</span>
  </div>
  <div class="perf-body">
{body_html}
  </div>
</section>
"""


def inject_summary(dashboard_file: Path, generated_at: str) -> None:
    text = dashboard_file.read_text(encoding="utf-8", errors="replace")
    body_html = read_summary(SUMMARY_FILE)
    if text.find("id=\"perf-summary\"") != -1:
        text = re.sub(
            r'<section id="perf-summary".*?</section>',
            "",
            text,
            flags=re.S,
        )
    card = build_card(generated_at, body_html, SUMMARY_FILE.name)
    if "</body>" in text:
        text = text.replace("</body>", card + "\n</body>")
    else:
        text += "\n" + card
    dashboard_file.write_text(text, encoding="utf-8")
    log(f"Injected performance summary card into {dashboard_file}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run ICM performance tests and add a business-language summary card to the custom dashboard.")
    parser.add_argument("--prod", action="store_true", help="Test the production environment (icm.pieq.ai) instead of preprod.")
    parser.add_argument("--pre-prod", action="store_true", help="Test the preprod environment (default).")
    parser.add_argument("-n", dest="iterations", type=int, help="Number of sitespeed iterations per page (e.g. 1 or 3).")
    parser.add_argument("--skip-command", action="store_true", help="Skip the test run; reuse the latest existing results.")
    parser.add_argument("--timeout", type=int, default=OPENCODE_TIMEOUT_S, help=f"Max seconds to wait for the opencode summary (default {OPENCODE_TIMEOUT_S}).")
    args = parser.parse_args()

    extra: list[str] = []
    if args.prod:
        extra.append("--prod")
    elif args.pre_prod:
        extra.append("--pre-prod")
    if args.iterations:
        extra.extend(["-n", str(args.iterations)])

    failed = False
    log(f"Working directory: {ROOT}")
    if not args.skip_command:
        code = run_all_roles(extra, RUN_LOG)
        if code not in (0,):
            failed = True
            log("One or more role tests failed - see run-performance.log. The dashboard will note this.")
    else:
        log("--skip-command: reusing latest existing results.")

    if not DASHBOARD_FILE.exists():
        raise SystemExit("No custom dashboard found. Run without --skip-command so results are built first.")

    try:
        payload = extract_dashboard_data(DASHBOARD_FILE)
        DATA_FILE.write_text(payload, encoding="utf-8")
        n_roles = len(json.loads(payload).get("roles", []))
        log(f"Found data for {n_roles} role(s) in the latest dashboard -> {DATA_FILE}")
    except Exception as exc:
        failed = True
        log(f"Could not extract dashboard data: {exc}")

    try:
        summarize_with_opencode(DATA_FILE, SUMMARY_FILE, args.timeout)
    except TimeoutError as exc:
        failed = True
        log(f"ERROR: {exc}")
        SUMMARY_FILE.write_text("", encoding="utf-8")
    except Exception as exc:
        failed = True
        log(f"ERROR: opencode summary failed: {exc}")
        SUMMARY_FILE.write_text("", encoding="utf-8")

    inject_summary(DASHBOARD_FILE, datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    log("Done. Open the summary at:")
    log(f"  {DASHBOARD_FILE}")
    log(f"  {SUMMARY_FILE}")
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()