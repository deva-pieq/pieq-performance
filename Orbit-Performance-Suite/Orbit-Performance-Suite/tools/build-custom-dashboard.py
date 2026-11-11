#!/usr/bin/env python3
"""Build a focused HTML dashboard from a sitespeed.io result folder."""

from __future__ import annotations

import argparse
import json
import re
import shutil
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent.parent
RESULT_ROOT = ROOT / "sitespeed-result"
OUT_DIR = ROOT / "custom-dashboard"
OUT_FILE = OUT_DIR / "index.html"

PAGE_NAMES = (
    ("/airport-monitor/live-arrivals/JFK", "JFK Airport Monitor Live Arrivals"),
    ("/airport-monitor/airport/JFK", "JFK Airport Monitor Operational"),
    ("/airport-monitor/live-arrivals/IAD", "IAD Live Arrivals Monitor"),
    ("/airport-monitor/airport/IAD", "IAD Operational Command"),
    ("/airport-monitor", "Airport Monitor"),
    ("/region-master", "Region Master"),
    ("/poe-master", "POE Master"),
    ("/campaigns", "Campaign Master"),
    ("/user-management", "User Management"),
)

# Relative to OUT_DIR (custom-dashboard/), the results tree is one level up.
RESULT_LINK = "../sitespeed-result"
ROLES = [
    ("Admin", ("dashboard_admin_js", "dashboard_admin_production_js"), "dashboard_admin.js"),
    ("Airport Manager", ("dashboard_airport_manager_js", "dashboard_airport_manager_production_js"), "dashboard_airport_manager.js"),
    ("Analyst", ("dashboard_analyst_js", "dashboard_analyst_production_js"), "dashboard_analyst.js"),
]


def parse_iso(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def page_label(url: str) -> str:
    path = urlparse(url).path.rstrip("/") or "/"
    for suffix, name in PAGE_NAMES:
        if path.endswith(suffix) or path == suffix:
            return name
    return path.strip("/").split("/")[-1] or url


def short_url(url: str, limit: int = 72) -> str:
    parsed = urlparse(url)
    text = parsed.path or "/"
    if parsed.query:
        text += "?" + parsed.query
    if len(text) > limit:
        return text[: limit - 3] + "..."
    return text


def header_bytes(headers: list) -> int:
    return sum(len(h.get("name", "") + h.get("value", "")) + 4 for h in headers or [])


def request_size(entry: dict) -> int:
    req = entry.get("request") or {}
    headers_size = req.get("headersSize") or 0
    body_size = req.get("bodySize") or 0
    if headers_size < 0:
        headers_size = 0
    if body_size < 0:
        body_size = 0
    if headers_size == 0:
        headers_size = header_bytes(req.get("headers"))
    return headers_size + body_size


def response_size(entry: dict) -> int:
    res = entry.get("response") or {}
    transfer = res.get("_transferSize")
    if transfer is not None and transfer >= 0:
        return transfer
    headers_size = res.get("headersSize") or 0
    body_size = res.get("bodySize") or 0
    if headers_size < 0:
        headers_size = 0
    if body_size < 0:
        body_size = 0
    if headers_size == 0:
        headers_size = header_bytes(res.get("headers"))
    return headers_size + body_size


def file_size(entry: dict) -> int:
    content = (entry.get("response") or {}).get("content") or {}
    size = content.get("size")
    if size is not None and size >= 0:
        return size
    return response_size(entry)


def timing_parts(entry: dict) -> dict:
    raw = entry.get("timings") or {}
    parts = {}
    for key in ("blocked", "dns", "ssl", "connect", "send", "wait", "receive"):
        value = raw.get(key)
        if value is None or value < 0:
            parts[key] = 0
        else:
            parts[key] = round(value, 3)
    return parts


_RUN_RE = re.compile(r"\d{4}-\d{2}-\d{2}-\d{2}-\d{2}-\d{2}")


def native_page_dirs(run_dir: Path) -> dict[str, str]:
    """Map page URL -> relative path of its native sitespeed report (pages/<host>/<Page>/index.html)."""
    mapping: dict[str, str] = {}
    for report in run_dir.glob("pages/*/*/index.html"):
        try:
            text = report.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        m = re.search(r"<title>Summary for \d+ runs?\s+(https?://[^<\s]+)", text)
        if not m:
            continue
        url = m.group(1).split(" run ")[0].strip()
        rel = RESULT_LINK + "/" + str(report.relative_to(RESULT_ROOT))
        mapping[url] = rel.replace("\\", "/")
    return mapping


def find_latest_run(root: Path) -> Path:
    runs = [p for p in root.glob("*/*") if p.is_dir() and _RUN_RE.match(p.name)]
    if not runs:
        raise SystemExit(f"No sitespeed result folders found under {root}")
    return max(runs, key=lambda p: p.name)


def find_latest_role_run(root: Path, folders: tuple[str, ...]) -> Path | None:
    runs = []
    for folder in folders:
        base = root / folder
        if not base.is_dir():
            continue
        runs.extend(p for p in base.glob("*") if p.is_dir() and _RUN_RE.match(p.name))
    if not runs:
        return None
    return max(runs, key=lambda p: p.name)


def find_latest_role_run_with_data(root: Path, folders: tuple[str, ...]) -> tuple[Path | None, str | None]:
    runs = []
    for folder in folders:
        base = root / folder
        if not base.is_dir():
            continue
        runs.extend(p for p in base.glob("*") if p.is_dir() and _RUN_RE.match(p.name))
    if not runs:
        return None, None
    runs.sort(reverse=True)
    for run in runs:
        if find_har(run):
            newer = runs[0]
            if newer != run:
                return run, f"latest run {newer.name} has no data — showing {run.name}"
            return run, None
    return None, f"no run has data (latest {runs[0].name})"


def find_har(run_dir: Path) -> Path | None:
    hars = sorted(run_dir.glob("pages/**/data/browsertime.har"))
    if not hars:
        return None
    return hars[0]


def prune_results(results_root: Path, keep: int = 5) -> int:
    """Remove old timestamped runs per script folder, keeping only the `keep` newest.

    Run folders are named YYYY-MM-DD-HH-MM-SS, so sorting by name equals sorting by
    time. Stale runs are deleted permanently.
    """
    removed = 0
    for script_dir in sorted(results_root.iterdir()):
        if not script_dir.is_dir():
            continue
        runs = sorted(
            (p for p in script_dir.iterdir() if p.is_dir() and _RUN_RE.match(p.name)),
            reverse=True,
        )
        stale = runs[keep:]
        if not stale:
            continue
        for old in stale:
            shutil.rmtree(old, ignore_errors=True)
            removed += 1
        print(
            f"[PRUNE] {script_dir.relative_to(results_root)}: "
            f"kept {len(runs) - len(stale)} run(s), removed {len(stale)}"
        )
    if removed:
        print(f"[PRUNE] Removed {removed} old run folder(s), keeping up to {keep} per script.")
    return removed


def build_pages(har: dict, run_dir: Path | None) -> list:
    log = har["log"]
    mapping = native_page_dirs(run_dir) if run_dir else {}
    no_run = run_dir is None
    if run_dir is not None:
        try:
            rel = run_dir.relative_to(RESULT_ROOT)
        except ValueError:
            no_run = True
            report_dir = ""
        else:
            report_dir = RESULT_LINK + "/" + str(rel).replace("\\", "/")
    by_ref: dict[str, list] = {}
    for entry in log.get("entries") or []:
        by_ref.setdefault(entry.get("pageref"), []).append(entry)

    pages = []
    for page in log.get("pages") or []:
        url = page.get("_url") or page.get("title") or ""
        url = url.split(" run ")[0].strip()
        entries = by_ref.get(page.get("id"), [])
        page_start = parse_iso(page["startedDateTime"])
        waterfall = []
        for entry in entries:
            start_ms = (parse_iso(entry["startedDateTime"]) - page_start).total_seconds() * 1000
            waterfall.append(
                {
                    "method": (entry.get("request") or {}).get("method", "GET"),
                    "url": (entry.get("request") or {}).get("url", ""),
                    "path": short_url((entry.get("request") or {}).get("url", "")),
                    "status": (entry.get("response") or {}).get("status", 0),
                    "time": round(entry.get("time") or 0, 1),
                    "start": round(max(start_ms, 0), 1),
                    "reqSize": request_size(entry),
                    "resSize": response_size(entry),
                    "fileSize": file_size(entry),
                    "timings": timing_parts(entry),
                }
            )
        waterfall.sort(key=lambda row: row["start"])
        top5 = sorted(waterfall, key=lambda row: row["time"], reverse=True)[:5]
        highest = max(waterfall, key=lambda row: row["fileSize"]) if waterfall else None
        on_load_ms = (page.get("pageTimings") or {}).get("onLoad") or 0
        lcp_ms = (page.get("pageTimings") or {}).get("_largestContentfulPaint") or 0
        # Overall page load = time until the last network call finishes (matches sitespeed waterfall end),
        # not browser loadEventEnd / onLoad which fires much earlier on this SPA.
        last_request_ms = max((row["start"] + row["time"] for row in waterfall), default=0)
        load_ms = max(on_load_ms, last_request_ms, lcp_ms)
        pages.append(
                {
                    "id": page.get("id"),
                    "name": page_label(url),
                    "url": url,
                    "loadMs": round(load_ms, 1),
                    "onLoadMs": round(on_load_ms, 1),
                    "lcpMs": round(lcp_ms, 1) if lcp_ms else 0,
                    "lastRequestMs": round(last_request_ms, 1),
                    "reqSize": sum(row["reqSize"] for row in waterfall),
                    "resSize": sum(row["resSize"] for row in waterfall),
                    "requests": len(waterfall),
                    "highest": {
                        "path": highest["path"] if highest else "—",
                        "url": highest["url"] if highest else "",
                        "fileSize": highest["fileSize"] if highest else 0,
                        "time": highest["time"] if highest else 0,
                    },
                    "top5": top5,
                    "waterfall": waterfall,
                    "reportNoRun": report_dir + "/index.html" if report_dir else "",
                    "reportRun": mapping.get(url, ""),
                }
            )
    return pages


def dedupe_pages(pages: list) -> list:
    by_name: dict[str, list] = {}
    for page in pages:
        by_name.setdefault(page["name"], []).append(page)
    result = []
    for name, group in by_name.items():
        group.sort(key=lambda p: p["loadMs"])
        median = group[len(group) // 2]
        median = dict(median)
        median["runs"] = len(group)
        result.append(median)
    return result


def render_html(roles: list, generated_at: str) -> str:
    payload = json.dumps({"generatedAt": generated_at, "roles": roles}, separators=(",", ":"))
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Orbit custom performance dashboard</title>
  <style>
    :root {{
      --bg: #f4f1ea;
      --ink: #1c1915;
      --muted: #6b645b;
      --line: #ddd6c8;
      --paper: #fffdf8;
      --accent: #9a3412;
      --blocked: #a8a29e;
      --dns: #78716c;
      --connect: #57534e;
      --send: #b45309;
      --wait: #9a3412;
      --receive: #166534;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font: 14px/1.45 "IBM Plex Sans", "Segoe UI", sans-serif;
      color: var(--ink);
      background: var(--bg);
    }}
    header {{
      padding: 28px 32px 8px;
      max-width: 1200px;
      margin: 0 auto;
    }}
    h1 {{
      margin: 0 0 6px;
      font-size: 24px;
      font-weight: 650;
      letter-spacing: -0.02em;
    }}
    .sub {{
      color: var(--muted);
      font-size: 13px;
    }}
    .meta-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
      gap: 8px 24px;
      margin-top: 14px;
      padding: 14px 16px;
      background: var(--paper);
      border: 1px solid var(--line);
    }}
    .meta-cell .label {{
      color: var(--muted);
      font-size: 11px;
      text-transform: uppercase;
      letter-spacing: 0.04em;
      margin-bottom: 2px;
    }}
    .meta-cell .value {{
      font-size: 13px;
      word-break: break-all;
    }}
    .meta-cell .value a {{
      color: var(--accent);
      text-decoration: none;
      border-bottom: 1px dotted var(--accent);
    }}
    .meta-cell .value a:hover {{
      text-decoration: underline;
    }}
    .meta-cell a.ext {{
      color: var(--ink);
    }}
    .meta-badge {{
      display: inline-block;
      padding: 2px 9px;
      border-radius: 10px;
      font-size: 12px;
      font-weight: 600;
      text-transform: none;
      letter-spacing: 0;
    }}
    .meta-badge.ok {{ background: #e7f4ea; color: #1b5e20; }}
    .meta-badge.partial {{ background: #fdf0e8; color: var(--accent); }}
    .meta-badge.none {{ background: #fdeaea; color: #b3261e; }}
    .cell-role .value {{ font-size: 15px; font-weight: 650; }}
    .meta-cell.wide {{ grid-column: 1 / -1; }}
    .meta-note {{
      grid-column: 1 / -1;
      margin-top: 2px;
      padding: 8px 10px;
      background: #fdf0e8;
      border: 1px solid #eccfb5;
      color: var(--accent);
      font-size: 13px;
    }}
    .tabs {{
      display: flex;
      gap: 8px;
      flex-wrap: wrap;
      max-width: 1200px;
      margin: 20px auto 0;
      padding: 0 32px;
    }}
    .tabs button {{
      border: 1px solid var(--line);
      background: transparent;
      color: var(--ink);
      padding: 8px 12px;
      cursor: pointer;
      font: inherit;
    }}
    .tabs button.active {{
      background: var(--ink);
      color: var(--paper);
      border-color: var(--ink);
    }}
    main {{
      max-width: 1200px;
      margin: 0 auto;
      padding: 20px 32px 48px;
    }}
    .kpis {{
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 12px;
    }}
    @media (max-width: 900px) {{
      .kpis {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
    }}
    .kpi {{
      background: var(--paper);
      border: 1px solid var(--line);
      padding: 16px 18px;
    }}
    .kpi .label {{
      color: var(--muted);
      font-size: 12px;
      text-transform: uppercase;
      letter-spacing: 0.04em;
    }}
    .kpi .value {{
      font-size: 22px;
      font-weight: 650;
      margin-top: 6px;
    }}
    .kpi .hint {{
      color: var(--muted);
      font-size: 12px;
      margin-top: 6px;
      word-break: break-all;
    }}
    h2 {{
      font-size: 16px;
      margin: 28px 0 10px;
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      background: var(--paper);
      border: 1px solid var(--line);
    }}
    th, td {{
      text-align: left;
      padding: 8px 10px;
      border-bottom: 1px solid var(--line);
      vertical-align: top;
    }}
    th {{
      font-size: 12px;
      color: var(--muted);
      font-weight: 600;
      text-transform: uppercase;
      letter-spacing: 0.03em;
    }}
    td.num, th.num {{ text-align: right; white-space: nowrap; }}
    .path {{ word-break: break-all; }}
    .wf {{
      background: var(--paper);
      border: 1px solid var(--line);
    }}
    .wf-row {{
      display: grid;
      grid-template-columns: minmax(180px, 280px) 70px 1fr;
      gap: 10px;
      align-items: center;
      padding: 6px 10px;
      border-bottom: 1px solid var(--line);
    }}
    .wf-row:last-child {{ border-bottom: 0; }}
    .wf-label {{
      font-size: 12px;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }}
    .wf-time {{
      font-size: 12px;
      text-align: right;
      color: var(--muted);
    }}
    .track {{
      position: relative;
      height: 14px;
      background: #efe8db;
    }}
    .seg {{
      position: absolute;
      top: 0;
      height: 100%;
    }}
    .legend {{
      display: flex;
      gap: 14px;
      flex-wrap: wrap;
      font-size: 12px;
      color: var(--muted);
      margin: 8px 0 12px;
    }}
    .legend span {{ display: inline-flex; align-items: center; gap: 6px; }}
    .swatch {{ width: 10px; height: 10px; display: inline-block; }}
    .empty {{ color: var(--muted); padding: 16px 0; }}
  </style>
</head>
<body>
  <header>
    <h1>Orbit custom performance dashboard</h1>
    <p class="sub" id="meta"></p>
  </header>
  <nav class="tabs" id="roles"></nav>
  <nav class="tabs" id="tabs"></nav>
  <main>
    <section class="kpis" id="kpis"></section>
    <h2>Top 5 loading time</h2>
    <div id="top5"></div>
    <h2>Waterfall</h2>
    <div class="legend">
      <span><i class="swatch" style="background:var(--blocked)"></i>Blocked / queue</span>
      <span><i class="swatch" style="background:var(--dns)"></i>DNS</span>
      <span><i class="swatch" style="background:var(--connect)"></i>Connect / TLS</span>
      <span><i class="swatch" style="background:var(--send)"></i>Send</span>
      <span><i class="swatch" style="background:var(--wait)"></i>Waiting (TTFB)</span>
      <span><i class="swatch" style="background:var(--receive)"></i>Receive</span>
    </div>
    <div class="wf" id="waterfall"></div>
  </main>
  <script id="data" type="application/json">{payload}</script>
  <script>
    const data = JSON.parse(document.getElementById("data").textContent);
    const rolesEl = document.getElementById("roles");
    const tabs = document.getElementById("tabs");
    const kpis = document.getElementById("kpis");
    const top5 = document.getElementById("top5");
    const waterfall = document.getElementById("waterfall");
    const meta = document.getElementById("meta");
    let activeRole = 0;
    let activePage = 0;

    function roleByIndex(i) {{ return data.roles[i]; }}
    function resize() {{
      activePage = 0;
      render();
    }};

    function fmtBytes(n) {{
      if (n >= 1048576) return (n / 1048576).toFixed(2) + " MB";
      if (n >= 1024) return (n / 1024).toFixed(1) + " KB";
      return n + " B";
    }}
    function fmtMs(n) {{
      if (n >= 1000) return (n / 1000).toFixed(2) + " s";
      return Math.round(n) + " ms";
    }}

    function render() {{
      const role = roleByIndex(activeRole);
      if (!role) return;
      const page = role.pages[activePage];
      rolesEl.innerHTML = data.roles.map((r, i) =>
        `<button class="${{i === activeRole ? "active" : ""}}" data-role="${{i}}">${{r.label}}</button>`
      ).join("");
      tabs.innerHTML = role.pages.map((p, i) =>
        `<button class="${{i === activePage ? "active" : ""}}" data-page="${{i}}">${{p.name}}</button>`
      ).join("");
      let links = [];
      if (page.reportNoRun) links.push(`<a class="ext" href="${{page.reportNoRun}}" target="_blank">native run report ↗</a>`);
      else links.push("<em>(no native report)</em>");
      if (page.reportRun) links.push(`<a class="ext" href="${{page.reportRun}}" target="_blank">native page report ↗</a>`);
      else links.push("<em>(no HAR data)</em>");
      const reportLinks = links.join(" · ");
      const badge = page.reportRun
        ? `<span class="meta-badge ok">data · median of ${{page.runs || 1}} runs</span>`
        : `<span class="meta-badge none">no data</span>`;
      const runLink = role.run
        ? `<a class="ext" href="../${{role.run}}/index.html" target="_blank">${{role.run}} ↗</a>`
        : role.run;
      meta.className = "meta-grid";
      meta.innerHTML = `
        <div class="meta-cell cell-role"><div class="label">Role</div><div class="value">${{role.label}} ${{badge}}</div></div>
        <div class="meta-cell"><div class="label">Page</div><div class="value">${{page.name}}</div></div>
        <div class="meta-cell"><div class="label">Generated</div><div class="value">${{data.generatedAt}}</div></div>
        <div class="meta-cell"><div class="label">Load time (median)</div><div class="value">${{fmtMs(page.loadMs)}}</div></div>
        <div class="meta-cell wide"><div class="label">URL</div><div class="value"><a href="${{page.url}}" target="_blank">${{page.url}} ↗</a></div></div>
        <div class="meta-cell wide"><div class="label">Run folder</div><div class="value">${{runLink}}</div></div>
        <div class="meta-cell wide"><div class="label">Native sitespeed report</div><div class="value">${{reportLinks}}</div></div>
        ${{role.note ? `<div class="meta-note">⚠ ${{role.note}}</div>` : ""}}
      `;
      kpis.innerHTML = `
        <div class="kpi"><div class="label">Page load time</div><div class="value">${{fmtMs(page.loadMs)}}</div><div class="hint">Until last request · onLoad ${{fmtMs(page.onLoadMs || 0)}} · ${{page.requests}} requests</div></div>
        <div class="kpi"><div class="label">Req size</div><div class="value">${{fmtBytes(page.reqSize)}}</div><div class="hint">Request headers + body, all calls</div></div>
        <div class="kpi"><div class="label">Res size</div><div class="value">${{fmtBytes(page.resSize)}}</div><div class="hint">Response transfer size on the wire</div></div>
        <div class="kpi"><div class="label">Highest file size</div><div class="value">${{fmtBytes(page.highest.fileSize)}}</div><div class="hint">${{page.highest.path}}</div></div>
      `;
      top5.innerHTML = `<table><thead><tr><th>#</th><th>Request</th><th class="num">Time</th><th class="num">Req size</th><th class="num">Res size</th></tr></thead><tbody>${{
        page.top5.map((row, i) => `<tr><td>${{i + 1}}</td><td class="path">${{row.method}} ${{row.path}}</td><td class="num">${{fmtMs(row.time)}}</td><td class="num">${{fmtBytes(row.reqSize)}}</td><td class="num">${{fmtBytes(row.resSize)}}</td></tr>`).join("")
      }}</tbody></table>`;

      const maxEnd = Math.max(...page.waterfall.map(r => r.start + r.time), page.loadMs, 1);
      waterfall.innerHTML = page.waterfall.map(row => {{
        const colors = {{
          blocked: "var(--blocked)",
          dns: "var(--dns)",
          ssl: "var(--connect)",
          connect: "var(--connect)",
          send: "var(--send)",
          wait: "var(--wait)",
          receive: "var(--receive)"
        }};
        let offset = row.start;
        const segs = ["blocked","dns","connect","ssl","send","wait","receive"].map(key => {{
          const dur = row.timings[key] || 0;
          const html = `<span class="seg" style="left:${{(offset / maxEnd) * 100}}%;width:${{(dur / maxEnd) * 100}}%;background:${{colors[key]}}"></span>`;
          offset += dur;
          return html;
        }}).join("");
        return `<div class="wf-row"><div class="wf-label" title="${{row.url}}">${{row.method}} ${{row.path}}</div><div class="wf-time">${{fmtMs(row.time)}}</div><div class="track">${{segs}}</div></div>`;
      }}).join("");
    }}

    rolesEl.addEventListener("click", (event) => {{
      const button = event.target.closest("button");
      if (!button) return;
      activeRole = Number(button.dataset.role);
      activePage = 0;
      render();
    }});
    tabs.addEventListener("click", (event) => {{
      const button = event.target.closest("button");
      if (!button) return;
      activePage = Number(button.dataset.page);
      render();
    }});
    render();
  </script>
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Build an aggregated Orbit dashboard for all roles from sitespeed.io results.")
    parser.add_argument(
        "run_dir",
        nargs="?",
        help="Optional single sitespeed result folder to build a one-role dashboard.",
    )
    parser.add_argument(
        "--keep",
        type=int,
        default=5,
        help="Keep only this many latest run folders per script (default 5).",
    )
    parser.add_argument(
        "--no-prune",
        action="store_true",
        help="Do not remove old run folders.",
    )
    args = parser.parse_args()

    if not args.no_prune and not args.run_dir:
        prune_results(RESULT_ROOT, max(1, args.keep))

    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    roles: list[dict] = []

    if args.run_dir:
        run_dir = Path(args.run_dir).resolve()
        if not run_dir.is_dir():
            raise SystemExit(f"Not a directory: {run_dir}")
        rel = run_dir.relative_to(ROOT)
        har_path = find_har(run_dir)
        if not har_path:
            raise SystemExit(f"No browsertime.har files in {run_dir}")
        pages = build_pages(json.loads(har_path.read_text()), run_dir)
        if not pages:
            raise SystemExit("No pages found in HAR")
        roles = [{"label": rel.parts[1], "script": "", "run": str(rel), "pages": dedupe_pages(pages)}]
    else:
        for label, folders, script in ROLES:
            run_dir, note = find_latest_role_run_with_data(RESULT_ROOT, folders)
            if not run_dir:
                note = note or f"No run folder for {label}"
                print(f"[SKIP] {label}: {note}")
                continue
            rel = run_dir.relative_to(RESULT_ROOT)
            run_rel = "sitespeed-result/" + str(rel)
            har_path = find_har(run_dir)
            if har_path:
                pages = dedupe_pages(build_pages(json.loads(har_path.read_text()), run_dir))
            else:
                # No HAR (failed measurement): keep the top5/waterfall renderers happy.
                has_report = (run_dir / "index.html").exists()
                pages = [{
                    "id": "missing",
                    "name": "(no HAR data)",
                    "url": f"{label} failed — no network data captured",
                    "loadMs": 0, "onLoadMs": 0, "lcpMs": 0, "lastRequestMs": 0,
                    "reqSize": 0, "resSize": 0, "requests": 0,
                    "highest": {"path": "—", "url": "", "fileSize": 0, "time": 0},
                    "top5": [],
                    "waterfall": [],
                    "reportNoRun": run_rel + "/index.html" if has_report else "",
                    "reportRun": "",
                }]
            if not pages:
                print(f"[SKIP] No pages parsed for {label} ({rel})")
                continue
            roles.append({
                "label": label,
                "script": script,
                "run": run_rel,
                "note": note or "",
                "pages": pages,
            })

    if not roles:
        raise SystemExit("No roles produced any data.")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    OUT_FILE.write_text(render_html(roles, generated_at), encoding="utf-8")
    print(f"Wrote {OUT_FILE}")
    for role in roles:
        print(f"{role['label']}  ({role['run']}): {', '.join(p['name'] for p in role['pages'])}")


if __name__ == "__main__":
    main()
