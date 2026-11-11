I'll analyze the performance data file to build the report.
# ICM Platform Performance Review

_Measured 22 October 2026 on the pre-production environment (preprod.app.pieq.ai) using sitespeed.io. This run covered 33 screens across three user roles — Ops Manager (15), Agency Owner (15) and Agent (3) — with one measurement per screen. Times below are "time until the page is fully loaded."_

## Executive summary

- **The platform is slow across the board — every single screen misses the mark.** All 33 screens take longer than 4 seconds, which puts them all in the "slow and needs attention" category. The average screen takes just over 10 seconds. There is not one screen that qualifies as fast or merely acceptable. This is a platform-wide issue, not a handful of bad pages.

- **Agents have the worst experience of anyone.** The three screens an agent uses every day average about 12.6 seconds. Even the fastest of them (the agent home screen) takes 11.6 seconds. These are the most customer-facing users in the business, so this is the highest-risk segment.

- **One shared cause explains most of the slowness.** On 11 of 15 screens per role, the page downloads a very large design file (1.3–2.3 MB) plus multiple large script files (1.2–2.7 MB each) before it shows anything useful — roughly 3 to 5 MB per page visit. Because the main content is the *last* thing to arrive, users stare at a loading screen for 10 to 13 seconds before seeing the page they asked for.

- **The single heaviest data pull is the Needs Attention queue.** It takes in the region of 17 MB of exception records in one request, consuming 2.3 to 2.8 seconds on its own before the page can render.

- **There is proven headroom — four screens already show it can be done.** Miscellaneous Charges, Advance Setup, Upload Statement and Disbursement History load in 4.5 to 5.5 seconds using only 11 to 15 requests and about 60–75 KB of data. When the platform stops hauling large packs of scripts and styling, it performs far better. The goal is to bring every other screen to that standard.

## Role by role

**Ops Manager — 15 screens, averaging about 10 seconds**

The Ops Manager role is the platform's admin workhorse and it is consistently slow: 11 of the 15 screens sit between 10 and 13 seconds. The fastest screens are Miscellaneous Charges at roughly 4.5 seconds (11 requests, about 60 KB of data) and Advance Setup at about 4.9 seconds (14 requests), followed by Disbursement History at 5.1 seconds (13 requests) and Upload Statement at 5.5 seconds (15 requests). The slowest are Carriers at about 13.0 seconds (27 requests, roughly 3.3 MB) and User Management at 12.7 seconds (26 requests), with Policy (12.6 seconds, 36 requests) and Statement History (12.5 seconds, 38 requests) close behind — Statement History also downloads the most data of any Ops Manager screen at about 4.7 MB. The landing Dashboard takes 10.4 seconds across 25 requests. In practice, an Ops Manager who hops between Policy, Carriers and Statement History waits 10 to 13 seconds per click, and the temptation to refresh and re-navigate is high — which wastes their time and increases the risk of work being done twice.

**Agency Owner — 15 screens, averaging about 10.6 seconds**

Agency Owners are slightly worse off than Ops Managers, and their heaviest screens are the ones they use to judge performance. The fastest screens are Miscellaneous Charges at about 4.8 seconds (11 requests), Advance Setup at 5.3 seconds (14 requests), Upload Statement at 5.4 seconds (15 requests) and Disbursement History at 5.5 seconds (13 requests). The slowest are Carriers and Agents at roughly 13.5 seconds each (26 requests apiece), Policy at 13.4 seconds (30 requests), and Statement Setup at 13.2 seconds (25 requests, about 4.2 MB of data). Their Dashboard landing page takes 12.4 seconds and fires 37 requests — more than any other Agency Owner screen. Because Agency Owners typically check commissions and policy numbers between client conversations, a 12–13 second wait per screen means they are often looking at stale or partial information when they need it, or they simply stop checking as often.

**Agent — 3 screens, averaging about 12.6 seconds**

Agents have the least choice and the worst experience. Their home screen takes 11.6 seconds and is the single heaviest screen in the entire test — 39 requests and about 5.9 MB of data — and their two working screens, Book of Business (13.2 seconds, 22 requests, about 4.8 MB) and Ledger (13.1 seconds, 23 requests, about 4.4 MB), are both at the slow end. There is no "fast" screen in this role at all. Agents are the people closest to customers, and a 12-second wait before a client record appears is the kind of friction that shows up in abandoned quotes, missed follow-ups and a poor impression of the platform.

## Pages that need attention

- **Carriers (13.0–13.5 seconds, 26–27 requests, about 3.3 MB)** — Every visit re-downloads a 1.3 MB page-design file and roughly 1.3 MB of scripts before anything renders. *Suggestion:* make the shared page design load once and be remembered by the browser, so a second visit to any screen starts instantly.

- **Statement History (12.5–12.8 seconds, 36–38 requests, 3.7–4.7 MB)** — The highest number of separate calls in the whole test, plus a 2.3 MB design file, all pulled before the grid appears. *Suggestion:* show the first screenful of rows immediately and fetch further rows only as the user scrolls or searches, cutting the initial payload by the majority.

- **Needs Attention (6.8–7.5 seconds, only 12 requests)** — Few requests but the heaviest single download: roughly 17 MB of exception records in one go, 2.3 to 2.8 seconds of it just to fetch. *Suggestion:* pull only the exceptions matching the filters and dates on screen, and load the rest on demand.

- **Book of Business and Ledger for agents (13.2 and 13.1 seconds, 4.8 MB and 4.4 MB)** — The agent's entire policy book and ledger are downloaded in one visit. *Suggestion:* show a summary count and headline figures first, then load the full detail only when a client or entry is opened.

- **Agent home screen (11.6 seconds, 39 requests, about 5.9 MB)** — The most requests and the most data of any screen in the platform, with everything arriving at once. *Suggestion:* split the dashboard into separate light cards that arrive independently, so the agent can start working before the whole page has finished.

- **Policy (12.6–13.4 seconds, 30–36 requests, about 3.4 MB)** — A policy search screen that behaves like a heavy report generator, loading a large table component and design file every time. *Suggestion:* let the search box and first results appear first, and defer the heavier table and filtering tools until the user actually uses them.

## Recommended next steps

1. **Make the shared page design load once and be reused, so repeat visits start instantly.** The same 1.3–2.3 MB design file and the same large script bundles are downloaded on every page of every screen. Solving this once in a shared layer lifts all 33 screens at the same time, and is the single highest-value change available.

2. **Stop sending entire datasets up front on the three heaviest tables — Statement History, Book of Business and Ledger.** Bring rows in progressively so users see content immediately. Business outcome: agents and agency owners get their working lists in around 3 seconds instead of 13, and spend their day looking at live information rather than spinners.

3. **Trim the Needs Attention exception download to only what is on screen.** Business outcome: the commission exception queue becomes a genuinely quick triage tool instead of a two-and-a-half second wait that people learn to avoid.

4. **Agree a performance service level — every screen fully loaded in under 4 seconds — and measure it automatically on every release, in the same way quality is checked today.** Business outcome: the business can see speed as a tracked quality measure, and today's slow screens cannot quietly get worse with each release.

5. **Prioritise the Agent experience as the first role to fix.** Agents are the slowest and most customer-facing, at about 12.6 seconds per screen. Business outcome: fewer dropped quotes and missed follow-ups, and a more credible platform when it is used in front of customers.

6. **Hold the four lightweight screens — Miscellaneous Charges, Advance Setup, Upload Statement, Disbursement History — as the design standard.** They prove what is achievable at 4.5 to 5.5 seconds with under 15 requests and minimal data. Business outcome: every future screen is built to a known-good benchmark rather than repeating the heavy pattern.
