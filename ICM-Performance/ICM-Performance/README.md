# ICM Performance Tests

sitespeed.io scripts that log into PieQ ICM and measure authenticated pages. Login is not measured. Reports are written as HTML under `sitespeed-result/`.

## Prerequisites

- **macOS, Linux, or Windows**
- **Homebrew** (macOS only) — [https://brew.sh](https://brew.sh)
- **Python 3**
- **ffmpeg** (used by sitespeed/browsertime for video and visual metrics)
- **Node.js 18+** (verified with Node.js 22)
- **npm**
- **Google Chrome** (stable)
- Network access to:
  - Prod: `https://icm.pieq.ai`
  - Preprod: `https://preprod.app.pieq.ai`
- A valid ICM test user (email and password are set at the top of each script)

Check versions (macOS / Linux):

```bash
python3 --version
ffmpeg -version
node -v
npm -v
```

Check versions (Windows, Command Prompt or PowerShell):

```powershell
python --version
ffmpeg -version
node -v
npm -v
```

## Install

### macOS (Homebrew)

```bash
# Homebrew (if not already installed)
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

brew install python
brew install ffmpeg
```

Confirm:

```bash
python3 --version
ffmpeg -version
```

### Windows

Homebrew is not available on Windows. Install the same tools with **winget** (Windows 10/11) or the official installers.

**1. Python**

```powershell
winget install Python.Python.3.12
```

Or install from [python.org](https://www.python.org/downloads/) and tick **Add python.exe to PATH**.

Close and reopen the terminal, then:

```powershell
python --version
```

**2. ffmpeg**

```powershell
winget install Gyan.FFmpeg
```

Close and reopen the terminal so PATH updates, then:

```powershell
ffmpeg -version
```

If `ffmpeg` is not found, add the ffmpeg `bin` folder to **Settings → System → About → Advanced system settings → Environment Variables → Path**.

**3. Node.js and npm**

```powershell
winget install OpenJS.NodeJS.LTS
```

Or install LTS from [nodejs.org](https://nodejs.org/). Reopen the terminal:

```powershell
node -v
npm -v
```

**4. Google Chrome**

Install Chrome from [google.com/chrome](https://www.google.com/chrome/) if it is not already installed. sitespeed.io drives Chrome; Chromium-only setups can fail.

**5. sitespeed.io**

```powershell
npm install -g sitespeed.io
sitespeed.io --version
```

Run commands from **Command Prompt** or **PowerShell** in this project folder. To open a report:

```powershell
start sitespeed-result\dashboard_op_prod_js\<latest-folder>\index.html
```

If Chrome or ffmpeg is not picked up after install, restart the terminal (or the machine) so PATH is reloaded.

### sitespeed.io (macOS / Linux)

```bash
npm install -g sitespeed.io
```

Confirm:

```bash
sitespeed.io --version
```

These scripts were last run with **sitespeed.io 42.6.0**.

## Customize the report

You cannot draw arbitrary widgets on the HTML report. You **can** choose Pages columns, show waterfalls, and limit the toplist. That is all in `sitespeed.config.json`. Always pass it:

```bash
sitespeed.io dashboard_op_prod.js --config sitespeed.config.json -n 1
```

| What you want | How sitespeed names it | Where to look |
|---|---|---|
| Page load time | `timings.pageLoadTime` (also `timings.fullyLoaded`) | **Pages** table, and each page metrics |
| Request size (bytes sent) | Not a summary column | Each page **waterfall** / HAR — request headers + body (usually small for GET APIs) |
| Response size (bytes received) | `transferSize.total` = on the wire (often gzipped). `contentSize.total` = uncompressed | **Pages** table |
| Highest file size | Toplist largest assets | **Toplist** tab (limited to 5 by `topListSize`) |
| Top 5 slowest request/response | Toplist slowest assets | **Toplist** tab |
| Waterfall | HAR waterfall | Each page run (`1.html`), also on the page summary because `showAllWaterfallSummary` is on |

`sitespeed.config.json` currently sets:

- Pages columns: load time, fully loaded, request count, transfer size, content size, LCP, TTFB, TBT
- `showAllWaterfallSummary: true` — waterfall on the page summary
- `topListSize: 5` — top 5 largest and slowest assets

After a run, open:

1. `pages.html` — load time, transfer size, content size, request count
2. `toplist.html` — highest file size and top 5 slowest calls
3. `pages/<site>/<PageName>/1.html` — full waterfall (every call, timing, size)
4. `pages/<site>/<PageName>/data/browsertime.har` — raw request/response list

## Custom dashboard (load time, sizes, top 5, waterfall)

`./run-sitespeed.sh` (or `run-sitespeed.cmd`) runs sitespeed, then builds the custom dashboard automatically.

Each build writes:

- `custom-dashboard/index.html` — always the **latest** run (replaced)
- `custom-dashboard/<script>-<timestamp>.html` — **kept** copy for that run
- `custom-dashboard/history.html` — list of kept copies

```bash
open custom-dashboard/index.html
open custom-dashboard/history.html
```

Windows:

```powershell
start custom-dashboard\index.html
start custom-dashboard\history.html
```

To rebuild from an existing result without running sitespeed again:

```bash
python3 build-custom-dashboard.py
python3 build-custom-dashboard.py sitespeed-result/dashboard_op_prod_js/2026-08-19-07-46-44
```

## How to run

Always run from this project directory. Use the wrapper so the custom dashboard is built automatically after sitespeed finishes.

### Combined prod report (recommended)

Logs in once on prod, then measures Dashboard, Policy, Statement History, Needs Attention, and Payable.

macOS / Linux:

```bash
chmod +x run-sitespeed.sh
./run-sitespeed.sh dashboard_op_prod.js -n 1
```

Windows:

```cmd
run-sitespeed.cmd dashboard_op_prod.js -n 1
```

`-n 1` is one browser iteration. Use `-n 3` (or higher) for more stable medians.

If you run `sitespeed.io ...` yourself, the custom dashboard is **not** updated. Then run:

```bash
python3 build-custom-dashboard.py
```

### Preprod (single page)

Preprod login uses **Continue** (`#kc-continue-email`) then **Sign In** (`#kc-login`).

```bash
sitespeed.io dashboard_op_preprod.js --config sitespeed.config.json -n 1
```

Single-page preprod scripts:

```bash
sitespeed.io dashboard_op_policy_preprod.js --config sitespeed.config.json -n 1
sitespeed.io dashboard_op_history_preprod.js --config sitespeed.config.json -n 1
sitespeed.io dashboard_op_need_attention_preprod.js --config sitespeed.config.json -n 1
sitespeed.io dashboard_ao_preprod.js --config sitespeed.config.json -n 1
```

### Other scripts

| Script | Environment | What it measures |
|---|---|---|
| `dashboard_op_prod.js` | Prod (`icm.pieq.ai`) | Combined OP pages (one report) |
| `dashboard_op.js` | Prod | Ops Manager dashboard only |
| `dashboard_ao.js` | Prod | Agency Owner dashboard |
| `dashboard_op_preprod.js` | Preprod | Ops Manager dashboard |
| `dashboard_op_policy_preprod.js` | Preprod | Policy |
| `dashboard_op_history_preprod.js` | Preprod | Statement History |
| `dashboard_op_need_attention_preprod.js` | Preprod | Needs Attention |
| `dashboard_ao_preprod.js` | Preprod | Agency Owner dashboard |

## Where to find the report

Each run creates a timestamped folder:

```text
sitespeed-result/<script_name>/<YYYY-MM-DD-HH-MM-SS>/
```

Example:

```text
sitespeed-result/dashboard_op_prod_js/2026-08-17-13-46-38/index.html
```

Open:

- `index.html` — summary / scorecard
- `pages.html` — one row per measured page (requests, load time, LCP, TTFB, TBT, transfer size)
- Each page folder — waterfall, assets, and `data/browsertime.har` (the list of calls)

```bash
open sitespeed-result/dashboard_op_prod_js/<latest-folder>/index.html
```

## Useful flags

```bash
# More iterations
sitespeed.io dashboard_op_prod.js --config sitespeed.config.json -n 3

# Include waterfalls on the page summary
sitespeed.io dashboard_op_prod.js --config sitespeed.config.json -n 1 --html.showAllWaterfallSummary

# CPU / long-task metrics
sitespeed.io dashboard_op_prod.js --config sitespeed.config.json -n 1 --cpu
```

## Notes

- Update `email` and `password` in the script before you run it.
- Prod username step uses `#kc-login`. Preprod username step uses `#kc-continue-email`.
- Login and navigation to Keycloak are setup only. Timing starts at `commands.measure.start(...)`.
- Existing HTML reports are not updated when you change `sitespeed.config.json`. Run again to get new columns.

Custome report run
Mac
./run-sitespeed.sh <File_Name> -n 1
eg: ./run-sitespeed.sh dashboard_op_prod1_js.js -n 1

Windows
run-sitespeed.cmd <File_Name> -n 1
eg: run-sitespeed.cmd dashboard_op_prod1_js.js -n 1

