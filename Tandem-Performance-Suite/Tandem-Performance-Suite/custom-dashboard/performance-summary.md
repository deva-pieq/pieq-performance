## Executive summary

- **Orbit is functional but feels slow for everyone.** Across the three roles measured, most pages take 4 to 10 seconds to fully load — well past the point where users notice and get impatient.
- **Live flight screens are the biggest problem.** The Live Arrivals pages fire **513 separate data requests** per visit and send over **1.2 MB**, making them 5.5 to 6.8 seconds to load on every role tested.
- **Region Master is the heaviest page in the product**, hitting 6.9 seconds for Admin and **10.5 seconds for Analyst** because it fetches country data in 267 separate calls.
- **Experiences vary widely for the same page.** POE Master loads in 3.8 seconds for Admin but **8.9 seconds for Airport Manager** — the same screen, more than twice as slow, depending on role and run.
- **The underlying app shell is a fixed cost.** Nearly every page spends about 1.2 seconds just getting the initial page from the server, before any useful content appears.

## Role by role

**Admin**
Admin users get a mixed experience. The quicker screens are **User Management (about 3.6 seconds, 27 requests — acceptable)** and **POE Master (about 3.8 seconds, 32 requests — acceptable)**. Everything else crosses into slow territory: **Airport Monitor (4.3 seconds, 22 requests)**, **Campaign Master (4.4 seconds, 25 requests)** and **JFK Operational (4.5 seconds, 21 requests)**. The real pain is **JFK Live Arrivals (6.8 seconds, 513 requests)** and **Region Master (6.9 seconds, 267 requests)**. In practice, an administrator switching between screens spends a noticeable pause on almost every move, and the live and master-data screens feel like the app has stalled.

**Airport Manager**
This is the slowest role overall, and no page reaches the "fast" category. The best cases are **IAD Operational (4.2 seconds, 21 requests)** and **JFK Operational (4.2 seconds, 21 requests)**, both still slow. **Airport Monitor (4.5 seconds, 42 requests)** and **IAD Live Arrivals (6.5 seconds, 513 requests)** follow. The worst is **POE Master at 8.9 seconds with only 24 requests**, where the main content only becomes visible after 8.4 seconds. For airport managers working under time pressure, even routine navigation feels unresponsive, and the operational screens they rely on most are the ones that drag.

**Analyst**
Analysts see the widest spread. **POE Master (about 3.9 seconds, 32 requests — acceptable)** and **Airport Monitor (4.2 seconds, 22 requests — slow)** are the more usable screens. But **JFK Operational (5.3 seconds, 22 requests)**, **JFK Live Arrivals (6.8 seconds, 513 requests)**, **User Management (8.9 seconds, 27 requests)**, **Campaign Master (9.2 seconds, 25 requests)** and **Region Master (10.5 seconds, 267 requests)** are all poor. An analyst doing investigative work will repeatedly hit multi-second waits, and the two master-data screens used for setup and reference become genuinely disruptive.

## Pages that need attention

- **Region Master — 6.9 seconds (Admin) and 10.5 seconds (Analyst), 267 requests, roughly 0.8 to 0.9 MB sent.** The page asks the server for every country individually instead of in one batch, so the load time grows with the size of the list. *Suggestion: request region and country data in a single combined call, or load it once and cache it for the session.*
- **Live Arrivals (JFK and IAD) — 5.5 to 6.8 seconds, 513 requests, over 1.2 MB sent per visit.** This is death by a thousand calls: one request per country, all fired at once, which overwhelms the connection and delays the final result. *Suggestion: consolidate the country lookups into one or two grouped requests and refresh only what changed.*
- **Campaign Master — up to 9.2 seconds (Analyst), 25 requests.** Only a small number of requests, but a very large application file is downloaded late in the load, so users stare at an incomplete screen. *Suggestion: shrink the main campaign bundle and show the page frame first, filling in details afterwards.*
- **User Management — up to 8.9 seconds (Analyst), 27 requests.** Same pattern: a large application file arrives late and the screen stays blank until it finishes. *Suggestion: split the screen so the user list appears before the heavier editing tools load.*
- **POE Master for Airport Manager — 8.9 seconds, 24 requests.** Few requests but a slow main content reveal, showing the page is waiting on large files rather than network volume. *Suggestion: review why this role loads the same page more slowly and cache or pre-load the shared files.*
- **Shared page shell — about 1.2 seconds on every page, with the same 51 KB layout file fetched twice.** This is a constant tax paid on every single navigation. *Suggestion: load the shared layout once and reuse it instead of re-downloading it on each page.*

## Recommended next steps

1. **Make Live Arrivals feel instant again** by collapsing the hundreds of per-country lookups into a small number of grouped requests — target under 4 seconds for every role.
2. **Bring Region Master under 4 seconds** by loading country and region data in one batch and reusing it, so the page no longer gets slower as the data set grows.
3. **Fix the "blank screen" pages (Campaign Master, User Management, POE Master)** by showing the page structure and key content first, then loading heavier tools in the background.
4. **Remove the repeated shared-file download** that adds roughly a second to every page, so all navigation feels quicker without changing any features.
5. **Set a simple performance target and track it monthly** — every page fully loaded in under 4 seconds for every role — and re-measure after these fixes to confirm the improvement in business terms.
