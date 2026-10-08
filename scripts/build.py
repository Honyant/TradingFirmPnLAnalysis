#!/usr/bin/env python3
"""Merge per-firm research JSON, compute PnL per head with error bars, and render the dashboard."""
import csv
import datetime as dt
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FIRM_DIR = ROOT / "data" / "firms"
META_PATH = ROOT / "data" / "research_log.json"
TEMPLATE = ROOT / "dashboard" / "template.html"
YEARS = list(range(2015, 2027))
Z90 = 1.645

FIRMS = [
    ("jane_street", "Jane Street", "JS", "market_maker"),
    ("hrt", "Hudson River Trading", "HRT", "market_maker"),
    ("citadel_sec", "Citadel Securities", "CitSec", "market_maker"),
    ("renaissance", "Renaissance Technologies", "RenTec", "hedge_fund"),
    ("de_shaw", "D. E. Shaw", "DESCO", "hedge_fund"),
    ("two_sigma", "Two Sigma", "2Σ", "hedge_fund"),
    ("optiver", "Optiver", "Optiver", "market_maker"),
    ("imc", "IMC Trading", "IMC", "market_maker"),
    ("virtu", "Virtu Financial", "Virtu", "public_market_maker"),
    ("xtx", "XTX Markets", "XTX", "market_maker"),
    ("jump", "Jump Trading", "Jump", "market_maker"),
]
PRIMARY_ENTITY = {"renaissance": "firm_total"}
RENTEC_ALIASES = {
    "medallion": "medallion", "medallion_fund": "medallion",
    "rief_rida": "rief_rida", "rief": "rief_rida", "rida": "rief_rida", "rief+rida": "rief_rida",
    "firm_total": "firm_total", "firm": "firm_total", "total": "firm_total",
}

warnings = []


def warn(msg):
    warnings.append(msg)
    print("WARN:", msg, file=sys.stderr)


def band(d, what, ctx):
    if not isinstance(d, dict) or not all(k in d for k in ("low", "mid", "high")):
        return None
    lo, mid, hi = float(d["low"]), float(d["mid"]), float(d["high"])
    if lo > hi:
        warn(f"{ctx}: {what} low>high, swapped")
        lo, hi = hi, lo
    if not lo <= mid <= hi:
        warn(f"{ctx}: {what} mid {mid} outside [{lo},{hi}], clamped")
        mid = min(max(mid, lo), hi)
    return [lo, mid, hi]


def per_head_worst(p, h):
    cands_lo = [p[0] / h[2], p[0] / h[0]]
    cands_hi = [p[2] / h[0], p[2] / h[2]]
    return [min(cands_lo), p[1] / h[1], max(cands_hi)]


def per_head_quad(p, h):
    """Combine the two 90% intervals assuming independent errors.

    Log space (multiplicative errors) when the whole PnL band is positive, linear first-order
    propagation otherwise (bands that cross zero, e.g. losing fund years)."""
    mid = p[1] / h[1]
    if p[0] > 0 and h[0] > 0:
        dn = math.hypot(math.log(p[1] / p[0]), math.log(h[2] / h[1]))
        up = math.hypot(math.log(p[2] / p[1]), math.log(h[1] / h[0]))
        return [mid * math.exp(-dn), mid, mid * math.exp(up)]
    dp_lo, dp_hi = (p[1] - p[0]) / h[1], (p[2] - p[1]) / h[1]
    dh_lo = abs(p[1]) * (h[2] - h[1]) / h[1] ** 2
    dh_hi = abs(p[1]) * (h[1] - h[0]) / h[1] ** 2
    return [mid - math.hypot(dp_lo, dh_lo), mid, mid + math.hypot(dp_hi, dh_hi)]


def parse_date(s):
    try:
        return dt.date.fromisoformat(str(s)[:10])
    except ValueError:
        return None


def norm_entity(firm_key, ent, entity_keys):
    e = str(ent or "").strip().lower().replace(" ", "_").replace("-", "_")
    if firm_key == "renaissance":
        return RENTEC_ALIASES.get(e, e)
    if len(entity_keys) == 1:
        return entity_keys[0]
    return e


def build_firm(key, name, short, ftype):
    path = FIRM_DIR / f"{key}.json"
    if not path.exists():
        warn(f"{key}: no data file")
        return None
    raw = json.loads(path.read_text())
    entities = raw.get("entities") or [{"key": "firm", "name": name, "description": ""}]
    if key == "renaissance":
        entities = [
            {"key": "medallion", "name": "Medallion", "description": "Employee-only flagship fund"},
            {"key": "rief_rida", "name": "RIEF + RIDA", "description": "Outside-investor funds (RIEF, RIDA, RIDGE while open)"},
            {"key": "firm_total", "name": "Firm total", "description": "Medallion + outside funds"},
        ]
    elif len(entities) != 1:
        entities = [{"key": "firm", "name": name, "description": "Firm-wide"}]
    ekeys = [e["key"] for e in entities]

    cutoff = parse_date((raw.get("ytd_2026") or {}).get("cutoff_date"))
    ann = None
    if cutoff and cutoff.year == 2026:
        frac = ((cutoff - dt.date(2026, 1, 1)).days + 1) / 365.0
        ann = 1.0 / frac if frac > 0 else None
    else:
        warn(f"{key}: bad 2026 cutoff {cutoff}")

    series = {k: {} for k in ekeys}
    for r in raw.get("rows", []):
        ek = norm_entity(key, r.get("entity"), ekeys)
        yr = r.get("year")
        if ek not in series or yr not in YEARS:
            warn(f"{key}: dropped row entity={r.get('entity')} year={yr}")
            continue
        ctx = f"{key}/{ek}/{yr}"
        p = band(r.get("pnl_usd_m"), "pnl", ctx)
        h = band(r.get("headcount"), "headcount", ctx)
        if p is None or h is None or h[0] <= 0:
            warn(f"{ctx}: missing/invalid band")
            continue
        out = {
            "year": yr,
            "pnl": p,
            "hc": h,
            "ph_quad": per_head_quad(p, h),
            "ph_worst": per_head_worst(p, h),
            "partial": bool(r.get("is_partial_year")) or yr == 2026,
            "period": r.get("period_label", ""),
            "pnl_basis": r.get("pnl_basis", "estimated"),
            "hc_basis": r.get("headcount_basis", "estimated"),
            "confidence": r.get("confidence", "low"),
            "sources": r.get("source_ids", []),
            "notes": r.get("notes", ""),
        }
        for opt, field in (("net_income_usd_m", "ni"), ("aum_usd_m", "aum")):
            b = band(r.get(opt), opt, ctx)
            if b:
                out[field] = b
        if yr == 2026 and ann:
            out["ann"] = ann
        if yr in series[ek]:
            warn(f"{ctx}: duplicate row, keeping first")
            continue
        series[ek][yr] = out
    for ek in ekeys:
        missing = [y for y in YEARS if y not in series[ek]]
        if missing:
            warn(f"{key}/{ek}: missing years {missing}")
        series[ek] = [series[ek][y] for y in YEARS if y in series[ek]]

    return {
        "key": key,
        "name": name,
        "short": short,
        "type": ftype,
        "primary_entity": PRIMARY_ENTITY.get(key, ekeys[0]),
        "entities": entities,
        "series": series,
        "pnl_definition": raw.get("pnl_definition", ""),
        "headcount_definition": raw.get("headcount_definition", ""),
        "fx_note": raw.get("fx_note", ""),
        "methodology": raw.get("methodology", ""),
        "overall_confidence": raw.get("overall_confidence", "low"),
        "ytd_cutoff": cutoff.isoformat() if cutoff else None,
        "ytd_period": (raw.get("ytd_2026") or {}).get("period_label", ""),
        "ytd_description": (raw.get("ytd_2026") or {}).get("description", ""),
        "caveats": raw.get("caveats", []),
        "open_questions": raw.get("open_questions", []),
        "changelog": raw.get("changelog", []),
        "review_status": raw.get("review_status", "final"),
        "sources": raw.get("sources", []),
    }


def main():
    firms = [f for f in (build_firm(*spec) for spec in FIRMS) if f]
    log = json.loads(META_PATH.read_text()) if META_PATH.exists() else {}
    dataset = {
        "generated_at": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "years": YEARS,
        "default_year": 2025,
        "research": log,
        "firms": firms,
        "build_warnings": warnings,
    }
    (ROOT / "data" / "dataset.json").write_text(json.dumps(dataset, indent=1))

    with open(ROOT / "data" / "pnl_per_head.csv", "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["firm", "entity", "year", "period", "partial",
                    "pnl_usd_m_low", "pnl_usd_m_mid", "pnl_usd_m_high",
                    "headcount_low", "headcount_mid", "headcount_high",
                    "pnl_per_head_usd_m_low", "pnl_per_head_usd_m_mid", "pnl_per_head_usd_m_high",
                    "pnl_per_head_worstcase_low", "pnl_per_head_worstcase_high",
                    "pnl_basis", "headcount_basis", "confidence", "source_ids"])
        for f in firms:
            for ek, rows in f["series"].items():
                for r in rows:
                    w.writerow([f["key"], ek, r["year"], r["period"], r["partial"],
                                *[round(x, 1) for x in r["pnl"]], *[round(x) for x in r["hc"]],
                                *[round(x, 3) for x in r["ph_quad"]],
                                round(r["ph_worst"][0], 3), round(r["ph_worst"][2], 3),
                                r["pnl_basis"], r["hc_basis"], r["confidence"], " ".join(r["sources"])])

    blob = json.dumps(dataset, separators=(",", ":")).replace("</", "<\\/")
    fragment = TEMPLATE.read_text().replace("/*__DATA__*/{}", blob)
    (ROOT / "dashboard" / "artifact.html").write_text(fragment)
    full = ("<!doctype html>\n<html lang=\"en\">\n<head>\n<meta charset=\"utf-8\">\n"
            "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1, viewport-fit=cover\">\n"
            "</head>\n<body>\n" + fragment + "\n</body>\n</html>\n")
    (ROOT / "dashboard" / "index.html").write_text(full)
    print(f"built {len(firms)} firms, {len(warnings)} warnings")


if __name__ == "__main__":
    main()
