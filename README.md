# Trading Firm PnL per Head

Year-by-year estimates of trading PnL, headcount and PnL per head for eleven quantitative trading firms, 2015 through 2026 year-to-date, with 90% error bars on every figure.

| Key | Firm | PnL definition |
|---|---|---|
| `jane_street` | Jane Street | Net trading revenue |
| `hrt` | Hudson River Trading | Net trading revenue |
| `citadel_sec` | Citadel Securities (the market maker, not the Citadel hedge fund) | Net trading revenue |
| `renaissance` | Renaissance Technologies: Medallion reported separately from RIEF/RIDA | Gross trading P&L of the funds (before fees) |
| `de_shaw` | D. E. Shaw | Gross trading P&L of the funds (before fees) |
| `two_sigma` | Two Sigma | Gross trading P&L of the funds (before fees) |
| `optiver` | Optiver | Net trading income (EUR converted to USD) |
| `imc` | IMC Trading | Net trading income (EUR converted to USD) |
| `virtu` | Virtu Financial | Adjusted Net Trading Income (reported, non-GAAP) |
| `xtx` | XTX Markets | Revenue per UK Companies House accounts |
| `jump` | Jump Trading | Net trading revenue (mostly estimated) |

## Dashboard

Open `dashboard/index.html` in a browser. It is self-contained: data is inlined and there are no chart libraries.

- **Forest plot**: firms ranked for one year, each with its 90% interval. Filled dots are reported figures; hollow dots are estimated or derived.
- **Trajectory**: one firm highlighted against the other ten, 2015 to 2026 YTD.
- **Small multiples**: every firm on its own scale, or on one shared scale.
- **Ledger**: every row, its basis, confidence, notes and sources.

Controls switch between PnL per head, PnL and headcount; between combined and worst-case error bars; between 2026 year-to-date and a naive annualized run-rate; and between linear and log scales.

## Data

- `data/firms/<key>.json`: final per-firm research output (rows, sources, caveats, changelog of the adversarial review).
- `data/dataset.json`: merged dataset with computed PnL-per-head bands.
- `data/pnl_per_head.csv`: flat table of every firm, entity and year.
- `data/raw/`: research audit trail (lens evidence, critic challenges) per firm and round.
- `data/research_log.json`: research rounds and agent counts.

## Definitions

- **PnL** for market makers and prop firms is net trading revenue: trading gains after exchange, clearing and financing costs, before compensation and overheads. For the hedge funds it is the funds' gross dollar gains before management and performance fees (about capital × gross return), which is the closest analog. Hedge-fund figures are therefore derived, not reported.
- **Headcount** is total firm employees. Renaissance's three entity views all divide by the full firm headcount, because the same staff run Medallion and the outside funds.
- **2026** is year-to-date through each firm's latest reliable data point. The cutoff date is stated per firm (`ytd_2026.cutoff_date`).

## Error bars

Each PnL and headcount figure carries a 90% credible interval chosen by the research agents under a shared calibration guide:

| Evidence | Typical half-width |
|---|---|
| Primary filing, matching definition | ±2–5% |
| Top-tier press citing documents | ±5–15% |
| Single source / "people familiar" | ±15–30% |
| Derived (AUM × return, interpolation) | ±20–40% |
| Pure estimate (peers, market regime) | ±40–100%+ |

PnL per head is computed in `scripts/build.py`, not by the agents:

```
mid        = PnL_mid / HC_mid
combined   = mid · exp(∓ sqrt(ln(PnL band)^2 + ln(HC band)^2))   # independent errors, log scale
             (linear first-order propagation when the PnL band crosses zero)
worst case = PnL_low / HC_high  …  PnL_high / HC_low
```

## How the research was done

Each firm had its own multi-agent workflow:

1. **Sweep**: four independent search agents (financial press; primary documents such as filings, ratings and debt-deal coverage; headcount history; most recent 2025–2026 data).
2. **Synthesize**: one agent built the 2015–2026 table with intervals from all evidence.
3. **Challenge**: two adversarial critics. A source auditor re-verified load-bearing numbers against their sources. A consistency critic attacked definitions, FX arithmetic, headcount jumps, per-head plausibility and interval calibration.
4. **Reconcile**: a final agent ruled on every challenge and logged the changes.

**Status of this edition:** research was stopped early to save budget. The search lenses that finished (one to four per firm, recorded in `data/raw/<key>_round1.json` and each firm's `review_status`) were synthesized into tables. Steps 3 and 4 did not run, so no firm's table has been adversarially reviewed. Optiver's consistency critic did finish, and its challenges are saved in the raw file but were not applied.

Agents ranked sources by trust: filings and official documents first, then Bloomberg, FT, WSJ and Reuters reporting from documents, then trade press. Blogs, wikis, forums and AI-written pages served only as leads. Agents were told to trace recycled claims back to their origin. Most private-firm figures still rest on press reports of debt-offering documents, which are informative but are not audited public disclosures.

## Rebuild

```
python3 scripts/build.py
```

The script reads `data/firms/*.json` and writes `data/dataset.json`, `data/pnl_per_head.csv`, `dashboard/index.html` (standalone) and `dashboard/artifact.html` (page fragment for hosting).
