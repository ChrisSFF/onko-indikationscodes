#!/usr/bin/env python3
"""Build the Indikationscode list from the BAG Spezialitätenliste (ePL FHIR export).

Usage:
    python scripts/build.py                 # download latest export, then build
    python scripts/build.py --input FILE    # build from an already downloaded NDJSON

Outputs (in docs/ so GitHub Pages serves them):
    docs/data/codes.json      every SL drug with an indication code
    docs/data/meta.json       build date, counts
    docs/data/changes.json    history of monthly changes
    docs/Indikationscodes_Onkologie_Haematologie.xlsx
"""
import argparse
import datetime as dt
import hashlib
import json
import os
import re
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from config import BAG_URL, group_for_atc  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
DOCS_DATA = ROOT / "docs" / "data"
SHORT_CACHE = ROOT / "data" / "shorttexts.json"
SHORT_MANUAL = ROOT / "data" / "shorttexts_by_text.json"  # {text hash: short text}
XLSX_PATH = ROOT / "docs" / "Indikationscodes_Onkologie_Haematologie.xlsx"

CODE_RE = re.compile(r"^\d{5}\.\d{2}$")


# ---------------------------------------------------------------- download
def download(dest: Path) -> Path:
    print(f"Downloading {BAG_URL}")
    req = urllib.request.Request(BAG_URL, headers={"User-Agent": "onko-indikationscodes"})
    with urllib.request.urlopen(req, timeout=900) as r, open(dest, "wb") as f:
        while chunk := r.read(1 << 20):
            f.write(chunk)
    print(f"  {dest.stat().st_size / 1e6:.1f} MB")
    return dest


# ---------------------------------------------------------------- parsing
def _ext(exts, name):
    for e in exts or []:
        if e.get("url") == name:
            return e
    return None


def parse_bundle(bundle: dict):
    product = None
    ingredients = []
    cuds = {}
    limitations = []
    dossier = None

    for entry in bundle.get("entry", []):
        r = entry.get("resource", {})
        rt = r.get("resourceType")
        if rt == "MedicinalProductDefinition":
            names = [n.get("productName") for n in r.get("name", []) if n.get("productName")]
            atc = (r.get("classification") or [{}])[0].get("coding", [{}])[0].get("code", "")
            product = {"name": names[0] if names else "", "atc": atc}
        elif rt == "Ingredient":
            t = r.get("substance", {}).get("code", {}).get("concept", {}).get("text")
            if t and t not in ingredients:
                ingredients.append(t)
        elif rt == "ClinicalUseDefinition":
            text = (r.get("indication", {}).get("diseaseSymptomProcedure", {})
                    .get("concept", {}).get("text") or "")
            cuds[r.get("id")] = text.strip()
        elif rt == "RegulatedAuthorization":
            if "Reimbursement" not in json.dumps(r.get("type", {})):
                continue
            for e in r.get("extension", []):
                if "reimbursementSL" in e.get("url", ""):
                    d = _ext(e.get("extension"), "FOPHDossierNumber")
                    if d:
                        dossier = d.get("valueIdentifier", {}).get("value")
            for ind in r.get("indication", []) or []:
                for e in ind.get("extension", []):
                    if "regulatedAuthorization-limitation" not in e.get("url", ""):
                        continue
                    sub = e.get("extension", [])
                    code = (_ext(sub, "indicationCode") or {}).get("valueString")
                    if not code:
                        continue
                    period = (_ext(sub, "period") or {}).get("valuePeriod", {})
                    status = ((_ext(sub, "status") or {}).get("valueCodeableConcept", {})
                              .get("coding", [{}])[0].get("display", ""))
                    ref = ((_ext(sub, "limitationIndication") or {})
                           .get("valueReference", {}).get("reference", ""))
                    limitations.append({
                        "code": code.strip(),
                        "cud": ref.split("ClinicalUseDefinition/")[-1],
                        "start": period.get("start", ""),
                        "end": period.get("end", ""),
                        "status": status,
                    })

    if not product or not limitations:
        return []
    rows = []
    for lim in limitations:
        rows.append({
            "code": lim["code"],
            "specific": bool(CODE_RE.match(lim["code"])),
            "brand": brand_from_cud(lim["cud"], product["name"]),
            "product": product["name"],
            "substance": ", ".join(ingredients),
            "atc": product["atc"],
            "group": group_for_atc(product["atc"]),
            "text": cuds.get(lim["cud"], ""),
            "start": lim["start"],
            "end": lim["end"],
            "status": lim["status"],
            "dossier": dossier or "",
            "cud": lim["cud"],
        })
    return rows


FORM_WORDS = {
    "inf", "inj", "kaps", "tabl", "filmtabl", "lös", "konz", "trockensub", "susp", "plv",
    "pulver", "fertspr", "fertpen", "durchstf", "amp", "gran", "tropfen", "supp", "salbe",
    "creme", "retard", "ret", "lyophilisat", "lyoph", "dispers", "brausetabl", "schmelztabl",
    "lacktabl", "depottabl", "implant", "implantat", "pen", "sirup", "emuls", "gel", "pfl",
    "stick", "kit", "inhal", "spray", "lösung", "s.c.", "i.v.",
}


def brand_from_product(product_name: str) -> str:
    """'Keytruda Inf Konz 100 mg/4 ml' -> 'Keytruda'; 'Lenalidomid Spirig HC Kaps 5 mg' ->
    'Lenalidomid Spirig HC'."""
    words = []
    for w in (product_name or "").split():
        lw = w.lower().strip(".,")
        if lw in FORM_WORDS or lw.rstrip(".") in FORM_WORDS or re.match(r"^\d", w):
            break
        words.append(w)
    return " ".join(words) or (product_name or "").split(" ")[0]


def brand_from_cud(cud_id: str, product_name: str) -> str:
    return brand_from_product(product_name)


def parse_file(path: Path):
    rows = []
    with open(path, encoding="utf-8") as f:
        for n, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                rows.extend(parse_bundle(json.loads(line)))
            except json.JSONDecodeError:
                print(f"  warning: line {n} is not valid JSON, skipped")
    return rows


def merge_rows(rows):
    """One entry per (indication code, brand); collect package names."""
    today = dt.date.today().isoformat()
    merged = {}
    for r in rows:
        if r["end"] and r["end"] < today:
            continue  # expired limitation
        key = (r["code"], r["brand"])
        m = merged.get(key)
        if not m:
            m = dict(r)
            m["products"] = [r["product"]]
            del m["product"]
            merged[key] = m
        else:
            if r["product"] not in m["products"]:
                m["products"].append(r["product"])
            if len(r["text"]) > len(m["text"]):
                m["text"] = r["text"]
    out = sorted(merged.values(), key=lambda x: (x["brand"], x["code"]))
    for m in out:
        m["products"].sort()
        m["hash"] = hashlib.sha1(m["text"].encode()).hexdigest()[:10]
    return out


# ---------------------------------------------------------------- short texts
SPLIT_PATTERNS = [
    r"\s(?=Nach Kostengutsprache)", r"\s(?=Als Monotherapie)", r"\s(?=Als Kombination)",
    r"\s(?=In Kombination)", r"\s(?=Nur nach)", r"\s(?=Nur auf)", r"\s(?=Zur )",
    r"\s(?=Zum )", r"\s(?=Für die)", r"\s(?=Die Behandlung)", r"\s(?=Behandlung )",
    r"\s(?=Vor Therapiebeginn)", r"\s(?=Es gelten)", r"\s(?=Vergütet wird)",
]


def _tidy(s: str, brand: str = "") -> str:
    s = s.strip(" ,;:-")
    if brand:  # "LENALIDOMID ACCORD in Kombination mit …" -> "In Kombination mit …"
        s = re.sub(rf"^{re.escape(brand)}\s+(?=(in|als)\b)", "", s, flags=re.I)
    s = re.sub(r"\s*\((mit|ohne)( oder ohne)? Preismodell[^)]*\)", "", s)
    # drop a trailing sentence fragment after a title: "3L CLL (Monotherapie) Pirtobrutinib wird …"
    m = re.search(r"\s(?:[A-ZÄÖÜ][\w-]*\s+)?(?:wird|ist)\s+(?:als|vergütet|nur|indiziert|in)\b"
                  r"|\s(?:Als Monotherapie|Die Therapie mit|Folgender)\b", s)
    if m and m.start() >= 10:
        s = s[:m.start()]
        s = re.sub(r"\s+[A-ZÄÖÜ][A-ZÄÖÜ0-9-]{3,}$", "", s)  # stray brand name at the end
    s = re.sub(r"\s+\d{5}\.\d{2}$", "", s).strip(" ,;:-")
    return (s[:1].upper() + s[1:]) if s else s


def heuristic_short(text: str, brand: str = "") -> str:
    t = re.sub(r"\s+", " ", text).strip()
    if brand:  # drop a leading brand name: "LENALIDOMID ACCORD in Kombination …"
        t = re.sub(rf"^{re.escape(brand)}\s+(?=(in|als|wird)\b)", "", t, flags=re.I)
    m = re.search(r"\((mit|ohne)( oder ohne)? Preismodell[^)]*\)", t)
    if m and m.end() < 260:
        return _tidy(t[:m.start()], brand)
    stops = list(SPLIT_PATTERNS)
    if brand:  # title usually ends where the brand name is repeated
        stops.append(rf"\s(?={re.escape(brand.split()[0])}\b)")
    cut = len(t)
    for p in stops:
        mm = re.search(p, t[8:], flags=re.I if p.endswith("\\b)") and brand else 0)
        if mm:
            cut = min(cut, mm.start() + 8)
    s = _tidy(t[:cut], brand)
    if len(s) > 160:
        s = s[:157].rsplit(" ", 1)[0] + " …"
    return s


def claude_short(items):
    """Optional: shorten with Claude when ANTHROPIC_API_KEY is set. Returns {code|brand: short}."""
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key or not items:
        return {}
    out = {}
    for i in range(0, len(items), 40):
        batch = items[i:i + 40]
        payload = [{"id": f"{it['code']}|{it['brand']}", "text": it["text"][:1500]} for it in batch]
        prompt = (
            "Du erhältst Limitationstexte aus der Schweizer Spezialitätenliste. Erstelle für jeden "
            "einen Kurztext (max. 110 Zeichen) für ein Ankreuzfeld auf einer onkologischen "
            "Chemotherapieverordnung: Indikation, Therapielinie, Mono/Kombination und das "
            "entscheidende Kriterium (z.B. Biomarker). Keine Codes, keine Dosierungen, nichts "
            "erfinden, nur Fachbegriffe aus dem Text. Antworte nur mit JSON: "
            '[{"id": ..., "short": ...}].\n\n' + json.dumps(payload, ensure_ascii=False)
        )
        body = json.dumps({
            "model": "claude-haiku-5-5", "max_tokens": 8000,
            "messages": [{"role": "user", "content": prompt}],
        }).encode()
        req = urllib.request.Request(
            "https://api.anthropic.com/v1/messages", data=body,
            headers={"x-api-key": key, "anthropic-version": "2023-06-01",
                     "content-type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=300) as r:
                resp = json.load(r)
            txt = resp["content"][0]["text"]
            txt = txt[txt.find("["): txt.rfind("]") + 1]
            for o in json.loads(txt):
                out[o["id"]] = o["short"].strip()
        except Exception as e:  # keep the build running; heuristic is the fallback
            print(f"  Claude shortening failed for a batch: {e}")
    return out


def apply_short_texts(rows):
    cache = json.loads(SHORT_CACHE.read_text()) if SHORT_CACHE.exists() else {}
    manual = json.loads(SHORT_MANUAL.read_text()) if SHORT_MANUAL.exists() else {}
    todo = []
    for r in rows:
        k = f"{r['code']}|{r['brand']}"
        c = cache.get(k)
        if c and c.get("hash") == r["hash"] and c.get("status") == "geprüft":
            r["short"], r["short_status"] = c["short"], "geprüft"
        elif r["hash"] in manual:
            r["short"], r["short_status"] = manual[r["hash"]], "KI, ungeprüft"
            cache[k] = {"hash": r["hash"], "short": r["short"], "status": r["short_status"]}
        elif c and c.get("hash") == r["hash"] and c.get("status") != "automatisch":
            r["short"], r["short_status"] = c["short"], c.get("status", "ungeprüft")
        elif r["group"] and r["specific"]:
            todo.append(r)
        else:
            r["short"], r["short_status"] = heuristic_short(r["text"], r["brand"]), "automatisch"

    ai = claude_short(todo)
    for r in todo:
        k = f"{r['code']}|{r['brand']}"
        if k in ai:
            r["short"], r["short_status"] = ai[k], "KI, ungeprüft"
        else:
            r["short"], r["short_status"] = heuristic_short(r["text"], r["brand"]), "automatisch"
        cache[k] = {"hash": r["hash"], "short": r["short"], "status": r["short_status"]}

    SHORT_CACHE.parent.mkdir(parents=True, exist_ok=True)
    SHORT_CACHE.write_text(json.dumps(dict(sorted(cache.items())), ensure_ascii=False, indent=1))
    return rows


# ---------------------------------------------------------------- diff
def diff(old_rows, new_rows):
    def key(r):
        return f"{r['code']}|{r['brand']}"
    old = {key(r): r for r in old_rows}
    new = {key(r): r for r in new_rows}
    added = [new[k] for k in new if k not in old]
    removed = [old[k] for k in old if k not in new]
    changed = [new[k] for k in new if k in old and (
        new[k]["hash"] != old[k]["hash"] or new[k]["end"] != old[k]["end"])]
    slim = lambda r: {"code": r["code"], "brand": r["brand"], "short": r.get("short", ""),
                      "group": r["group"]}
    return {"added": [slim(r) for r in added], "removed": [slim(r) for r in removed],
            "changed": [slim(r) for r in changed]}


# ---------------------------------------------------------------- excel
def ch_date(d: str) -> str:
    p = (d or "").split("-")
    return f"{p[2]}.{p[1]}.{p[0]}" if len(p) == 3 else (d or "")


def write_xlsx(rows, changes, meta):
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.utils import get_column_letter

    wb = Workbook()
    head_fill = PatternFill("solid", fgColor="1F4E5F")
    head_font = Font(bold=True, color="FFFFFF")
    cols = [("Präparat", 18), ("Indikationscode", 15), ("Kurztext Indikation", 60),
            ("Wirkstoff", 24), ("Gruppe", 30), ("ATC", 10), ("Gültig ab", 11),
            ("Befristet bis", 12), ("Kurztext-Status", 14), ("Packungen", 40),
            ("Limitationstext (vollständig, BAG)", 90)]

    def sheet(ws, data):
        ws.append([c for c, _ in cols])
        for i, (_, w) in enumerate(cols, 1):
            ws.column_dimensions[get_column_letter(i)].width = w
            c = ws.cell(row=1, column=i)
            c.fill, c.font = head_fill, head_font
        for r in data:
            ws.append([r["brand"], r["code"], r["short"], r["substance"], r["group"] or "",
                       r["atc"], ch_date(r["start"]), ch_date(r["end"]), r["short_status"],
                       "; ".join(r["products"]), r["text"]])
        for row in ws.iter_rows(min_row=2):
            for c in row:
                c.alignment = Alignment(vertical="top", wrap_text=c.column in (3, 10, 11))
            row[1].font = Font(bold=True)
        ws.freeze_panes = "C2"
        ws.auto_filter.ref = ws.dimensions

    onko = [r for r in rows if r["group"] and r["specific"]]
    ws = wb.active
    ws.title = "Onko-Häma"
    sheet(ws, onko)
    sheet(wb.create_sheet("Alle Präparate mit Code"), [r for r in rows if r["specific"]])

    ws = wb.create_sheet("Änderungen")
    ws.append(["Art", "Präparat", "Indikationscode", "Kurztext"])
    for kind, label in (("added", "neu"), ("changed", "geändert"), ("removed", "entfernt")):
        for r in changes.get(kind, []):
            ws.append([label, r["brand"], r["code"], r["short"]])
    for i, w in enumerate((10, 18, 15, 80), 1):
        ws.column_dimensions[get_column_letter(i)].width = w

    ws = wb.create_sheet("Info")
    for line in [
        "Indikationscodes Onkologie / Hämatologie – Arbeitshilfe",
        f"Stand der Daten: BAG Spezialitätenliste, abgerufen am {ch_date(meta['built'])}",
        "Quelle: BAG ePL, FHIR-Export (öffentlich, CC0). Verbindlich ist allein die "
        "Spezialitätenliste unter sl.bag.admin.ch.",
        "Kurztexte sind gekürzte Fassungen des BAG-Limitationstexts. Status 'automatisch' "
        "oder 'KI, ungeprüft' = noch nicht von Fachperson geprüft.",
        "Codes mit .XX / .RB sind allgemeine Hinweise ohne eigenen Indikationscode und nur "
        "im Blatt 'Alle' bzw. auf der Webseite aufgeführt.",
    ]:
        ws.append([line])
    ws.column_dimensions["A"].width = 120
    wb.save(XLSX_PATH)


# ---------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", type=Path)
    args = ap.parse_args()

    src = args.input or download(ROOT / "sl-de.ndjson")
    rows = merge_rows(parse_file(src))
    rows = apply_short_texts(rows)

    DOCS_DATA.mkdir(parents=True, exist_ok=True)
    codes_path = DOCS_DATA / "codes.json"
    old = json.loads(codes_path.read_text()) if codes_path.exists() else []
    ch = diff(old, rows) if old else {"added": [], "removed": [], "changed": []}

    today = dt.date.today().isoformat()
    meta = {
        "built": today,
        "source": BAG_URL,
        "codes_total": sum(r["specific"] for r in rows),
        "codes_onko": sum(1 for r in rows if r["group"] and r["specific"]),
        "brands_onko": len({r["brand"] for r in rows if r["group"] and r["specific"]}),
    }

    history_path = DOCS_DATA / "changes.json"
    history = json.loads(history_path.read_text()) if history_path.exists() else []
    if any(ch.values()):
        history.insert(0, {"date": today, **ch})
    history = history[:24]

    codes_path.write_text(json.dumps(rows, ensure_ascii=False, separators=(",", ":")))
    (DOCS_DATA / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1))
    history_path.write_text(json.dumps(history, ensure_ascii=False, indent=1))
    write_xlsx(rows, ch, meta)
    print(json.dumps(meta, ensure_ascii=False, indent=1))
    print(f"changes: +{len(ch['added'])} ~{len(ch['changed'])} -{len(ch['removed'])}")


if __name__ == "__main__":
    main()
