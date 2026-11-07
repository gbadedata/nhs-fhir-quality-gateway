"""Static HTML report for the ODS GP practice directory run."""
from __future__ import annotations

from html import escape
from pathlib import Path

from . import svgcharts

PAGE_CSS = """
:root{color-scheme:light dark}*{box-sizing:border-box}
body{margin:0;font:16px/1.6 system-ui,-apple-system,"Segoe UI",sans-serif;background:#f9f9f7;color:#0b0b0b}
@media (prefers-color-scheme:dark){body{background:#0d0d0d;color:#f0efec}.card,.note,table.plain{background:#1a1a19!important;border-color:rgba(255,255,255,.1)!important}
.muted{color:#c3c2b7!important}a{color:#86b6ef}}
header{background:#005eb8;color:#fff;padding:36px max(22px,calc((100vw - 1000px)/2)) 30px}
header h1{margin:0 0 6px;font-size:clamp(1.7rem,3.4vw,2.5rem)}header p{margin:0;max-width:760px;opacity:.95}
main{max-width:1000px;margin:auto;padding:22px 20px 70px}
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:14px;margin:20px 0}
.card{background:#fcfcfb;border:1px solid rgba(11,11,11,.10);border-radius:12px;padding:16px 18px}
.card .v{font-size:1.9rem;font-weight:650;line-height:1.2}.card .l{font-size:.9rem}.muted{color:#52514e}
.note{background:#fcfcfb;border:1px solid rgba(11,11,11,.10);border-left:4px solid #005eb8;border-radius:8px;padding:14px 18px;margin:18px 0}
h2{margin:34px 0 6px;font-size:1.35rem}
table.plain{border-collapse:collapse;width:100%;background:#fcfcfb;border:1px solid rgba(11,11,11,.10);font-variant-numeric:tabular-nums}
table.plain th,table.plain td{padding:8px 12px;border-bottom:1px solid rgba(127,127,127,.25);text-align:left}
code{font-size:.85em;word-break:break-all}footer{margin-top:40px;font-size:.85rem}
"""


def _n(value: int) -> str:
    return f"{value:,}"


def render(summary: dict, manifest: dict, conformance: dict | None, output: Path) -> None:
    current = summary["current_gp_practices_england"]
    records = summary["gp_practice_records"]
    status = summary["by_status"]
    regions = summary["current_gp_practices_england_by_region"]
    flows = summary["england_openings_and_closures_by_financial_year"]

    cards = "".join(
        f"<div class='card'><div class='v'>{escape(v)}</div><div class='l muted'>{escape(l)}</div></div>" for v, l in (
            (_n(current), "Active GP practices in England"),
            (_n(records), "GP practice (RO76) records in the file, all statuses and nations"),
            (_n(summary["non_gp_prescribing_cost_centres"]), "Other prescribing cost centres set aside"),
            (_n(summary["gp_practice_records_rejected"]), "Records failing the ODS specification checks"),
        ))

    region_chart = svgcharts.hbar(
        "Active GP practices by NHS England region",
        f"{_n(current)} practices; region taken from the practice postcode (ODS column 3)",
        [(name, count, f"{name}: {count:,} active practices") for name, count in
         sorted(regions.items(), key=lambda kv: -kv[1])],
        lambda v: f"{v:,.0f}", "Active practices")

    partial = summary.get("latest_year_is_partial")
    flow_chart = svgcharts.columns(
        "GP practice codes opened and closed in England, by financial year",
        "Closures include mergers, where a practice code is retired but services continue under another code."
        + (" The latest year is part-year." if partial else ""),
        [f["financial_year"] for f in flows],
        [("Closed", [f["closed"] for f in flows]), ("Opened", [f["opened"] for f in flows])],
        lambda v: f"{v:,.0f}")
    closed_total = sum(f["closed"] for f in flows)
    opened_total = sum(f["opened"] for f in flows)

    status_rows = "".join(f"<tr><td>{escape(k)}</td><td>{v:,}</td></tr>" for k, v in summary["by_nation_and_status"].items())
    reasons = summary["rejection_reasons"] or {"none": 0}
    reason_rows = "".join(f"<tr><td>{escape(k.replace('_', ' '))}</td><td>{v:,}</td></tr>" for k, v in reasons.items())
    warn_rows = "".join(f"<tr><td>{escape(k.replace('_', ' '))}</td><td>{v:,}</td></tr>" for k, v in
                        (summary["warnings"] or {"none": 0}).items())

    if conformance:
        conf_html = (
            f"<p>The full Bundle of {conformance['resources']:,} Organization resources was checked with the official "
            f"HL7 FHIR validator ({escape(conformance['validator'])}) against <code>{escape(conformance['profile'])}</code> "
            f"from <code>{escape(conformance['package'])}</code>.</p>"
            f"<table class='plain'><thead><tr><th>Severity</th><th>Issues</th></tr></thead><tbody>"
            + "".join(f"<tr><td>{escape(k)}</td><td>{v:,}</td></tr>" for k, v in conformance["by_severity"].items())
            + "</tbody></table>"
            f"<p class='muted'>{escape(conformance['note'])}</p>")
    else:
        conf_html = "<p>Run <code>conformance/run_validator.sh</code> to check the Bundle against UK Core.</p>"

    source = manifest["files"][0]
    html = f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>NHS ODS GP practice directory: quality audit and UK Core mapping</title><style>{PAGE_CSS}{svgcharts.CSS}</style></head><body>
<header><h1>How many GP practices does England have?</h1>
<p>A quality audit of the NHS Organisation Data Service GP practice file, mapped to FHIR UK Core Organization resources.
Snapshot retrieved {escape(source['retrieved'])}. Public organisation data only; no patient records.</p></header>
<main>
<div class="cards">{cards}</div>
<div class="note"><strong>Why the answer is {_n(current)}, not {_n(records)}.</strong> The file lists every prescribing cost centre:
{_n(summary['non_gp_prescribing_cost_centres'])} non-GP settings (community services, prisons, walk-in centres and others) are set aside by
role code. Of the {_n(records)} GP practice records left, {_n(status.get('INACTIVE', 0))} are closed, {_n(status.get('DORMANT', 0))} are dormant and
{_n(summary['by_nation_and_status'].get('Wales / ACTIVE', 0))} active ones are in Wales. The first version of this project counted all
{_n(records)} as current, because it did not recognise the file's <code>INACTIVE</code> and <code>DORMANT</code> status values. Running it on the
real file is what exposed that.</div>

{region_chart}
{flow_chart}
<p>Since April 2017, {_n(closed_total)} English GP practice codes have closed and {_n(opened_total)} have opened. ODS warns that closures before
April 2017 are incomplete in this file, so the series starts there. A closed code often means a merger rather than a lost service, so this is a measure of
consolidation, not of access.</p>

<h2>Records by nation and status</h2>
<table class="plain"><thead><tr><th>Nation / ODS status</th><th>GP practice records</th></tr></thead><tbody>{status_rows}</tbody></table>

<h2>Specification checks</h2>
<p>Each GP practice row is checked against the ODS Reference Data Catalogue: 27 columns, code format by nation, mandatory fields, valid dates,
close date after open date, and status consistent with the close date. Failing rows go to <code>quarantine.json</code> with reasons.</p>
<table class="plain"><thead><tr><th>Rejection reason</th><th>Rows</th></tr></thead><tbody>{reason_rows}</tbody></table>
<p class="muted">Soft warnings (kept, but flagged):</p>
<table class="plain"><thead><tr><th>Warning</th><th>Rows</th></tr></thead><tbody>{warn_rows}</tbody></table>

<h2>UK Core conformance</h2>
{conf_html}

<h2>Provenance</h2>
<p>Source: <a href="{escape(source['landing_page'])}">{escape(source['title'])}</a>, {escape(source['publisher'])}.
Retrieved {escape(source['retrieved'])}; {source['bytes']:,} bytes; SHA-256 <code>{escape(source['sha256'])}</code>.
Field layout: <a href="{escape(source['specification'])}">ODS Reference Data Catalogue</a>. {escape(source['licence'])}.</p>
<footer class="muted">Independent portfolio project. Not affiliated with or endorsed by NHS England. Telephone numbers in the source are
practice prescribing contacts published by ODS.</footer>
</main>{svgcharts.SCRIPT}</body></html>"""
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(html, encoding="utf-8")
