#!/usr/bin/env python3
"""Build a focused HTML dashboard from a sitespeed.io result folder."""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent
RESULT_ROOT = ROOT / "sitespeed-result"
OUT_DIR = ROOT / "custom-dashboard"
OUT_FILE = OUT_DIR / "index.html"

PAGE_NAMES = (
    ("/dashboard/ops-manager", "Dashboard"),
    ("/dashboard/agency-owner", "Agency Owner"),
    ("/policy", "Policy"),
    ("/commission-processing/statement-history", "Statement History"),
    ("/commission-processing/needs-attention", "Needs Attention"),
    ("/payment-processing/payable-line-items", "Payable"),
)


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


def find_latest_run(root: Path) -> Path:
    runs = [p for p in root.glob("*/*") if p.is_dir() and re.match(r"\d{4}-\d{2}-\d{2}-\d{2}-\d{2}-\d{2}", p.name)]
    if not runs:
        raise SystemExit(f"No sitespeed result folders found under {root}")
    return max(runs, key=lambda p: p.name)


def find_har(run_dir: Path) -> Path:
    hars = sorted(run_dir.glob("pages/**/data/browsertime.har"))
    if not hars:
        raise SystemExit(f"No browsertime.har files in {run_dir}")
    return hars[0]


def build_pages(har: dict) -> list:
    log = har["log"]
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
            }
        )
    return pages


def render_html(run_dir: Path, generated_at: str, pages: list) -> str:
    payload = json.dumps(
        {
            "run": str(run_dir.relative_to(ROOT)) if run_dir.is_relative_to(ROOT) else str(run_dir),
            "generatedAt": generated_at,
            "pages": pages,
        },
        separators=(",", ":"),
    )
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>ICM custom performance dashboard</title>
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
    <h1>ICM custom performance dashboard</h1>
    <p class="sub" id="meta"></p>
  </header>
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
    const tabs = document.getElementById("tabs");
    const kpis = document.getElementById("kpis");
    const top5 = document.getElementById("top5");
    const waterfall = document.getElementById("waterfall");
    const meta = document.getElementById("meta");
    let active = 0;

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
      const page = data.pages[active];
      meta.textContent = data.run + " · generated " + data.generatedAt + " · " + page.url;
      tabs.innerHTML = data.pages.map((p, i) =>
        `<button class="${{i === active ? "active" : ""}}" data-i="${{i}}">${{p.name}}</button>`
      ).join("");
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

    tabs.addEventListener("click", (event) => {{
      const button = event.target.closest("button");
      if (!button) return;
      active = Number(button.dataset.i);
      render();
    }});
    render();
  </script>
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a custom ICM dashboard from a sitespeed.io result.")
    parser.add_argument(
        "run_dir",
        nargs="?",
        help="Path to a sitespeed result folder (default: latest under sitespeed-result/)",
    )
    args = parser.parse_args()
    run_dir = Path(args.run_dir).resolve() if args.run_dir else find_latest_run(RESULT_ROOT)
    if not run_dir.is_dir():
        raise SystemExit(f"Not a directory: {run_dir}")

    har_path = find_har(run_dir)
    har = json.loads(har_path.read_text())
    pages = build_pages(har)
    if not pages:
        raise SystemExit("No pages found in HAR")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    OUT_FILE.write_text(render_html(run_dir, generated_at, pages), encoding="utf-8")
    print(f"Wrote {OUT_FILE}")
    print(f"Source {run_dir}")
    print(f"Pages: {', '.join(p['name'] for p in pages)}")


if __name__ == "__main__":
    main()
