#!/usr/bin/env python3
"""
Busca eventos das 9 agendas do Google Calendar via seus links "secretos"
em formato iCal (sem precisar de Google Cloud, API key ou OAuth), aplica
as mesmas regras de técnico/etiqueta do painel original, e gera um
index.html estático e autocontido para o GitHub Pages.

Variável de ambiente esperada:
  ICAL_URLS_JSON  -- JSON mapeando a "key" de cada origem (config/calendars.json)
                     para o link secreto iCal dela, ex:
                     {"gtek": "https://calendar.google.com/calendar/ical/.../private-xxx/basic.ics", ...}
"""
import os
import re
import json
import datetime
import unicodedata
import urllib.parse
import urllib.request

import icalendar
import recurring_ical_events

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_DIR = os.path.join(ROOT, "config")
OUT_PATH = os.path.join(ROOT, "index.html")
LOGO_PATH = os.path.join(ROOT, "assets", "logo.b64")

GTEK_PALETTE = ["#A78BFA", "#FBBF24", "#F43F5E", "#38BDF8", "#34D399", "#E879F9",
                "#22D3EE", "#A3E635", "#F87171", "#818CF8", "#2DD4BF", "#F472B6"]
NO_LABEL_COLOR = "#5B6472"

GITHUB_REPO = os.environ.get("GITHUB_REPOSITORY", "gtekagendas/agendas")

# America/Sao_Paulo has been UTC-3 with no DST since 2019.
TZ_BR = datetime.timezone(datetime.timedelta(hours=-3))


def load_json(name):
    with open(os.path.join(CONFIG_DIR, name), encoding="utf-8") as f:
        return json.load(f)


def slug(s):
    s = s.lower()
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    s = re.sub(r"[^a-z0-9]+", "-", s)
    return s.strip("-")


def hash_color(name):
    h = 0
    for ch in name:
        h = (h * 31 + ord(ch)) & 0xFFFFFFFF
    return GTEK_PALETTE[h % len(GTEK_PALETTE)]


def parse_tech(title, rule):
    delim = rule.get("delimiter") or "-"
    parts = title.split(delim)
    if len(parts) < 2:
        return None
    chosen = parts[0] if rule.get("position") == "first" else parts[-1]
    val = chosen.strip()
    return val or None


def get_ical_urls():
    raw = os.environ.get("ICAL_URLS_JSON")
    if not raw:
        raise SystemExit(
            "Faltando a variável de ambiente ICAL_URLS_JSON "
            "(um JSON com a key de cada origem -> link secreto iCal dela)."
        )
    return json.loads(raw)


def sanitize_id(s):
    return re.sub(r"[^A-Za-z0-9_.~:@+-]", "_", s or "")


def fetch_ical_events(url, start_date, end_date):
    """Baixa o .ics e devolve as ocorrências (já expandindo recorrências)
    entre start_date e end_date (objetos date, inclusive)."""
    req = urllib.request.Request(url, headers={"User-Agent": "painel-agendas-bot/1.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        raw_bytes = resp.read()

    calendar = icalendar.Calendar.from_ical(raw_bytes)
    start_dt = datetime.datetime.combine(start_date, datetime.time.min, tzinfo=TZ_BR)
    end_dt = datetime.datetime.combine(end_date, datetime.time.max, tzinfo=TZ_BR)

    occurrences = recurring_ical_events.of(calendar).between(start_dt, end_dt)

    events = []
    for occ in occurrences:
        status = str(occ.get("STATUS", "")).upper()
        if status == "CANCELLED":
            continue
        summary = str(occ.get("SUMMARY", "") or "")
        dtstart = occ.get("DTSTART").dt
        if isinstance(dtstart, datetime.datetime):
            if dtstart.tzinfo is not None:
                dtstart = dtstart.astimezone(TZ_BR)
            date_str = dtstart.strftime("%Y-%m-%d")
        else:
            date_str = dtstart.strftime("%Y-%m-%d")  # all-day event (date only)
        uid = str(occ.get("UID", ""))
        instance_id = sanitize_id(uid + "_" + date_str)
        events.append({"id": instance_id, "summary": summary, "date": date_str})
    return events


def build_snapshot():
    calendars_cfg = load_json("calendars.json")
    settings = load_json("settings.json")
    event_overrides = load_json("event_overrides.json")
    rule = settings.get("detectionRule", {"delimiter": "-", "position": "last"})
    urls = get_ical_urls()

    today = datetime.date.today()
    months_back = calendars_cfg.get("fetchRangeMonthsBack", 1)
    months_fwd = calendars_cfg.get("fetchRangeMonthsForward", 2)

    start_month_idx = today.month - 1 - months_back
    start_date = datetime.date(today.year + start_month_idx // 12, start_month_idx % 12 + 1, 1)

    end_month_idx = today.month - 1 + months_fwd + 1
    end_year = today.year + end_month_idx // 12
    end_month = end_month_idx % 12 + 1
    end_date = datetime.date(end_year, end_month, 1) - datetime.timedelta(days=1)

    events_out = []
    errors = []

    for src in calendars_cfg["sources"]:
        url = urls.get(src["key"])
        if not url:
            errors.append(f"{src['name']}: sem link iCal configurado (chave '{src['key']}')")
            continue
        try:
            raw_items = fetch_ical_events(url, start_date, end_date)
        except Exception as exc:  # noqa: BLE001 - report and keep going
            errors.append(f"{src['name']}: {exc}")
            continue

        for ev in raw_items:
            title = ev["summary"]
            date_str = ev["date"]

            if src.get("parseTechnician"):
                tech = parse_tech(title, rule) or "Não identificado"
                src_key = "gtek_" + slug(tech)
                default_name = tech
                default_color = hash_color(tech)
            else:
                src_key = src["key"]
                default_name = src["name"]
                default_color = src["color"]

            if src_key in settings.get("hiddenKeys", {}):
                continue

            ov_source = settings.get("overrides", {}).get(src_key)
            name = ov_source["name"] if ov_source else default_name
            color = ov_source["color"] if ov_source else default_color

            doc_id = src["key"] + "__" + ev["id"]
            ev_ov = event_overrides.get(doc_id)
            no_label = bool(ev_ov and ev_ov.get("noLabel"))
            comment = ev_ov.get("comment", "") if ev_ov else ""

            if no_label:
                label, out_color, group_key = "Sem etiqueta", NO_LABEL_COLOR, "no_label"
            else:
                label = (ev_ov or {}).get("label") or name
                out_color = (ev_ov or {}).get("color") or color
                group_key = src_key

            events_out.append({
                "date": date_str,
                "key": group_key,
                "label": label,
                "color": out_color,
                "title": title,
                "comment": comment,
                "view": src.get("view", "perif"),
            })

    events_out.sort(key=lambda e: e["date"])
    return events_out, errors


def render_html(events, errors):
    template_path = os.path.join(os.path.dirname(__file__), "template.html")
    with open(template_path, encoding="utf-8") as f:
        html = f.read()

    logo_b64 = ""
    if os.path.exists(LOGO_PATH):
        with open(LOGO_PATH, encoding="utf-8") as f:
            logo_b64 = f.read().strip()

    generated_at = datetime.datetime.now().strftime("%d/%m/%Y %H:%M")
    issue_title = "Solicitar atualização do painel"
    issue_body = "Por favor, gere uma nova versão do instantâneo do painel com os dados mais recentes."
    issue_url = (
        f"https://github.com/{GITHUB_REPO}/issues/new"
        f"?title={urllib.parse.quote(issue_title)}&body={urllib.parse.quote(issue_body)}"
    )

    note = f"🤖 Atualizado automaticamente em {generated_at}."
    if errors:
        note += " Atenção: " + "; ".join(errors)

    html = html.replace("__LOGO__", logo_b64)
    html = html.replace("__GENERATED_NOTE__", note)
    html = html.replace("__ISSUE_URL__", issue_url)
    html = html.replace("__EVENTS_JSON__", json.dumps(events, ensure_ascii=False))
    return html


def main():
    events, errors = build_snapshot()
    html = render_html(events, errors)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"OK: {len(events)} eventos escritos em {OUT_PATH}")
    if errors:
        print("Avisos:")
        for e in errors:
            print(" -", e)


if __name__ == "__main__":
    main()
