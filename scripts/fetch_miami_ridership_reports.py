#!/usr/bin/env python3
"""Acquire Miami-Dade DTPW monthly Ridership Technical Reports (PDF) — the observed Metromover boardings by station.

Window: 2025-10 .. 2026-07 (ten reports in one layout; the two earlier reports use an older layout with truncated
station names and are not used). Files land under raw/miami/2026-09-17/dtpw_rtr/ with url, bytes, sha256, HTTP
Last-Modified and retrieval time in source_manifest.json; acquisition_validation.json checks that every PDF contains the
"METROMOVER MONTHLY AND AVERAGE DAILY BOARDINGS BY STATION" table with 21 station rows and a TOTAL row.
Idempotent: a PDF whose sha256 already matches the manifest is kept and re-verified.
    python3 scripts/fetch_miami_ridership_reports.py [--validate-only]
"""
import hashlib, json, os, re, subprocess, sys, time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "raw/miami/2026-09-17"
MANIFEST = RAW / "source_manifest.json"
VALIDATION = RAW / "acquisition_validation.json"
MONTHS = ["2025-10", "2025-11", "2025-12", "2026-01", "2026-02", "2026-03", "2026-04", "2026-05", "2026-06", "2026-07"]
URL = "https://www.miamidade.gov/resources/transportation_publicworks/documents/rtr/{m}-monthly-ridership-report.pdf"
INDEX = "https://www.miamidade.gov/global/transportation/ridership-technical-reports.page"
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0 Safari/537.36"
TERMS = "Miami-Dade County public ridership report; cite DTPW and the report month"
NUM = r"-?[\d,]+(?:\.\d+)?%?"


def sha_file(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def load(p): return json.loads(Path(p).read_text(encoding="utf-8"))
def dump(p, o): Path(p).write_text(json.dumps(o, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def headers(url):
    r = subprocess.run(["curl", "-sSI", "-A", UA, "--location", "--max-time", "60", url], capture_output=True, text=True); h = {}
    for line in r.stdout.replace("\r", "").splitlines():
        if ":" in line: k, v = line.split(":", 1); h[k.strip().lower()] = v.strip()
    return h


def parse_metromover_table(pdf_path):
    """-> {'page', 'month_label', 'prev_label', 'rows': {station: {avg_weekday, avg_saturday, avg_sunday, total_monthly}}} or None."""
    import pypdf
    r = pypdf.PdfReader(str(pdf_path))
    for i, p in enumerate(r.pages):
        t = p.extract_text() or ""
        if "METROMOVER MONTHLY AND AVERAGE DAILY" in t.upper() and "BY STATION" in t.upper():
            rows = {}; hdr = re.search(r"Stations\s+(\w{3}-\d{2})\s+(\w{3}-\d{2})", t)
            for line in t.splitlines():
                toks = line.strip().split()
                if len(toks) >= 13 and all(re.fullmatch(NUM, x) for x in toks[-12:]):
                    name = " ".join(toks[:-12]); n = [x.replace(",", "") for x in toks[-12:]]
                    rows[name] = {"avg_weekday": int(n[0]), "avg_saturday": int(n[3]), "avg_sunday": int(n[6]), "total_monthly": int(n[9]),
                                  "prev_month": {"avg_weekday": int(n[1]), "avg_saturday": int(n[4]), "avg_sunday": int(n[7]), "total_monthly": int(n[10])}}
            return {"page": i + 1, "month_label": hdr.group(1) if hdr else None, "prev_label": hdr.group(2) if hdr else None, "rows": rows}
    return None


def main():
    validate_only = "--validate-only" in sys.argv
    (RAW / "dtpw_rtr").mkdir(parents=True, exist_ok=True)
    prev = {s["file"]: s for s in load(MANIFEST)["sources"]} if MANIFEST.exists() else {}
    sources = []
    for m in MONTHS:
        f = f"dtpw_rtr/{m}-monthly-ridership-report.pdf"; dest = RAW / f; url = URL.format(m=m)
        if not validate_only:
            if dest.exists() and prev.get(f) and prev[f].get("sha256") == sha_file(dest):
                sources.append({**prev[f], "status": "kept_verified"}); print(f"kept_verified  {f}"); continue
            part = dest.with_name(dest.name + ".part")
            r = subprocess.run(["curl", "--fail", "--location", "--silent", "--show-error", "-A", UA, "--max-time", "300", "--retry", "3", url, "--output", str(part)], capture_output=True, text=True)
            if r.returncode != 0 or not part.exists() or part.stat().st_size == 0 or part.read_bytes()[:4] != b"%PDF":
                raise SystemExit(f"download failed or not a PDF: {f}: {r.stderr.strip()[:200]}")
            os.replace(part, dest); h = headers(url)
            sources.append({"source_id": f"dtpw_rtr_{m}", "group": "dtpw_rtr", "file": f, "url": url, "report_month": m, "bytes": dest.stat().st_size, "sha256": sha_file(dest),
                            "retrieved_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "http_last_modified": h.get("last-modified"), "http_etag": h.get("etag"),
                            "terms": TERMS, "status": "downloaded"})
            print(f"downloaded     {f} {dest.stat().st_size:,d} bytes")
        else:
            sources.append(prev[f])
    if not validate_only:
        dump(MANIFEST, {"retrieved_on": "2026-09-17", "acquisition_stage": "miami_ridership_reports", "publisher": "Miami-Dade County Department of Transportation and Public Works (DTPW)",
                        "index_page": INDEX, "window": MONTHS, "layout_note": "reports from 2025-10 onward share one layout with the Metromover station table on one page; "
                        "2025-08 and 2025-09 use an older layout with truncated station names and are excluded",
                        "terms": TERMS, "fetch_script": {"path": "scripts/fetch_miami_ridership_reports.py", "sha256": sha_file(Path(__file__))}, "sources": sources})
    manifest = load(MANIFEST); checks, hard_fail = {}, []
    def hard(name, ok, detail=None):
        checks[name] = {"pass": bool(ok), **({"detail": detail} if detail is not None else {})}
        if not ok: hard_fail.append(name)
    names_ref = None; per_month = {}
    for s in manifest["sources"]:
        p = RAW / s["file"]
        hard(f"{s['report_month']}_present_and_sha256_matches", p.exists() and sha_file(p) == s["sha256"])
        t = parse_metromover_table(p) if p.exists() else None
        if not t: hard(f"{s['report_month']}_metromover_table_found", False); continue
        st = [k for k in t["rows"] if k.upper() != "TOTAL"]; tot = t["rows"].get("TOTAL")
        per_month[s["report_month"]] = {"page": t["page"], "month_label": t["month_label"], "stations": len(st), "total_avg_weekday": tot["avg_weekday"] if tot else None,
                                        "sum_stations_avg_weekday": sum(t["rows"][k]["avg_weekday"] for k in st)}
        hard(f"{s['report_month']}_21_stations_and_total", len(st) == 21 and tot is not None, len(st))
        hard(f"{s['report_month']}_station_sum_matches_total_within_3", tot is not None and abs(per_month[s["report_month"]]["sum_stations_avg_weekday"] - tot["avg_weekday"]) <= 3)
        exp = time.strftime("%b-%y", time.strptime(s["report_month"], "%Y-%m"))
        hard(f"{s['report_month']}_month_label_matches_filename", t["month_label"] == exp, {"label": t["month_label"], "expected": exp})
        if names_ref is None: names_ref = set(st)
        else: hard(f"{s['report_month']}_station_names_identical_to_first_report", set(st) == names_ref, sorted(set(st) ^ names_ref))
    v = {"status": "PASS" if not hard_fail else "FAIL", "failed_checks": hard_fail, "checked_on": "2026-09-17", "per_month": per_month, "station_names": sorted(names_ref or []), "checks": checks,
         "scope": "acquisition integrity and table detection only; the values are DTPW-published boardings, not trips, not OD, not peak-hour"}
    dump(VALIDATION, v); print(f"validation: {v['status']} failed={hard_fail} months={len(per_month)}")
    sys.exit(0 if v["status"] == "PASS" else 1)


if __name__ == "__main__":
    main()
