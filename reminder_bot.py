#!/usr/bin/env python3
"""Class deadline reminder bot: reads a CSV of deadlines, posts a digest to a WeCom group webhook.

Env vars:
  SHEET_CSV_URL        URL of the published CSV (or a local file path). Default: deadlines.csv
  WECOM_WEBHOOK_URL    WeCom group bot webhook URL (not needed with DRY_RUN=1)
  MODE                 "daily" or "weekly" (default: daily)
  TZ_NAME              Timezone (default: Asia/Shanghai)
  DRY_RUN              "1" prints the message instead of sending
CSV columns: date (YYYY-MM-DD), time (optional, HH:MM), course, description
"""
import csv, io, json, os, sys, urllib.request
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

SHEET = os.environ.get("SHEET_CSV_URL", "deadlines.csv")
WEBHOOK = os.environ.get("WECOM_WEBHOOK_URL", "")
MODE = os.environ.get("MODE", "daily").lower()
TZ = ZoneInfo(os.environ.get("TZ_NAME", "Asia/Shanghai"))
DRY = os.environ.get("DRY_RUN") == "1"


def load_rows():
    sb, key = os.environ.get("SUPABASE_URL"), os.environ.get("SUPABASE_KEY", "")
    if sb:  # calendar app database
        req = urllib.request.Request(sb + "/rest/v1/deadlines?select=*&order=date",
                                     headers={"apikey": key, "Authorization": "Bearer " + key})
        with urllib.request.urlopen(req, timeout=30) as r:
            data = json.load(r)
        return sorted((datetime.strptime(x["date"], "%Y-%m-%d").date(), (x.get("time") or "")[:5],
                       x.get("course") or "", x.get("title") or "") for x in data)
    if SHEET.startswith("http"):
        with urllib.request.urlopen(SHEET, timeout=30) as r:
            text = r.read().decode("utf-8-sig")
    else:
        with open(SHEET, encoding="utf-8-sig") as f:
            text = f.read()
    items = []
    for row in csv.DictReader(io.StringIO(text)):
        row = {(k or "").strip().lower(): (v or "").strip() for k, v in row.items()}
        try:
            d = datetime.strptime(row["date"], "%Y-%m-%d").date()
        except (KeyError, ValueError):
            continue  # skip blank/malformed rows
        items.append((d, row.get("time", ""), row.get("course", ""), row.get("description", "")))
    return sorted(items, key=lambda x: (x[0], x[1]))


def fmt(item, with_date=False):
    d, t, course, desc = item
    when = (d.strftime("%a %d %b") + " ") if with_date else ""
    when += t
    parts = [p for p in (f"**{course}**" if course else "", desc) if p]
    return f"- {when.strip()} {' · '.join(parts)}".replace("-  ", "- ")


def build(items, today):
    if MODE == "weekly":
        end = today + timedelta(days=7)
        week = [i for i in items if today <= i[0] <= end]
        lines = [f"## 🗓 Week ahead ({today:%d %b} – {end:%d %b})"]
        lines += [fmt(i, True) for i in week] or ["Nothing due. Enjoy the week!"]
        return "\n".join(lines)

    due_today = [i for i in items if i[0] == today]
    tomorrow = [i for i in items if i[0] == today + timedelta(days=1)]
    soon = [i for i in items if today + timedelta(days=2) <= i[0] <= today + timedelta(days=7)]
    if not (due_today or tomorrow or soon):
        return ""  # stay quiet when nothing is coming up
    lines = [f"## 📅 {today:%A %d %b}"]
    if due_today:
        lines += ["**Today**"] + [fmt(i) for i in due_today]
    if tomorrow:
        lines += ["**⚠️ Tomorrow**"] + [fmt(i) for i in tomorrow]
    if soon:
        lines += ["**Next 7 days**"] + [fmt(i, True) for i in soon]
    return "\n".join(lines)


def send(text):
    body = json.dumps({"msgtype": "markdown", "markdown": {"content": text}}).encode()
    req = urllib.request.Request(WEBHOOK, body, {"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        resp = json.loads(r.read())
    if resp.get("errcode") != 0:
        sys.exit(f"WeCom error: {resp}")


def main():
    today = datetime.now(TZ).date()
    if os.environ.get("TODAY"):  # for testing
        today = datetime.strptime(os.environ["TODAY"], "%Y-%m-%d").date()
    msg = build(load_rows(), today)
    if not msg:
        print("Nothing to send.")
        return
    if DRY:
        print(msg)
    else:
        if not WEBHOOK:
            sys.exit("Set WECOM_WEBHOOK_URL")
        send(msg)
        print("Sent.")


if __name__ == "__main__":
    main()
