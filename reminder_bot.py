#!/usr/bin/env python3
"""Class deadline reminder bot: reads deadlines and posts a digest (@everyone) to a WeCom group webhook.

Env: SUPABASE_URL, SUPABASE_KEY (or SHEET_CSV_URL for a CSV), WECOM_WEBHOOK_URL,
     MODE=daily|weekly, TZ_NAME (default Asia/Shanghai), DRY_RUN=1 to print only.
"""
import csv, io, json, os, sys, urllib.request
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

WEBHOOK = os.environ.get("WECOM_WEBHOOK_URL", "")
MODE = os.environ.get("MODE", "daily").lower()
TZ = ZoneInfo(os.environ.get("TZ_NAME", "Asia/Shanghai"))
DRY = os.environ.get("DRY_RUN") == "1"


def load_rows():
    """Returns sorted tuples: (date, time, course, assignment)."""
    sb, key = os.environ.get("SUPABASE_URL"), os.environ.get("SUPABASE_KEY", "")
    if sb:
        req = urllib.request.Request(sb + "/rest/v1/deadlines?select=*&order=date",
                                     headers={"apikey": key, "Authorization": "Bearer " + key})
        with urllib.request.urlopen(req, timeout=30) as r:
            data = json.load(r)
        rows = [(x["date"], x.get("time"), x.get("course"), x.get("title")) for x in data]
    else:
        src = os.environ.get("SHEET_CSV_URL", "deadlines.csv")
        if src.startswith("http"):
            text = urllib.request.urlopen(src, timeout=30).read().decode("utf-8-sig")
        else:
            text = open(src, encoding="utf-8-sig").read()
        rows = [(r.get("date"), r.get("time"), r.get("course"), r.get("description"))
                for r in csv.DictReader(io.StringIO(text))]
    out = []
    for d, t, c, a in rows:
        try:
            out.append((datetime.strptime((d or "").strip(), "%Y-%m-%d").date(),
                        (t or "").strip()[:5], (c or "").strip(), (a or "").strip()))
        except ValueError:
            continue
    return sorted(out)


def load_infos():
    sb, key = os.environ.get("SUPABASE_URL"), os.environ.get("SUPABASE_KEY", "")
    if not sb:
        return []
    req = urllib.request.Request(sb + "/rest/v1/infos?select=text&order=id",
                                 headers={"apikey": key, "Authorization": "Bearer " + key})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return [x["text"] for x in json.load(r) if x.get("text")]
    except Exception:
        return []


def build(items, today):
    if MODE == "weekly":
        monday = today + timedelta(days=1) if today.weekday() == 6 else today - timedelta(days=today.weekday())
        sunday = monday + timedelta(days=6)
        week = [i for i in items if monday <= i[0] <= sunday]
        lines = ["Hello everyone! Here are the deadlines for the upcoming week:"]
        for day in sorted({i[0] for i in week}):
            lines.append(f"{day:%A, %d %B}")
            for d, t, c, a in week:
                if d == day:
                    lines.append(f"• {c or 'General'} – Deadline for {a}" + (f" ({t})" if t else ""))
        if not week:
            lines.append("• Nothing due this week 🎉")
        infos = load_infos()
        if infos:
            lines += ["", "Other important info:"] + [f"• {x}" for x in infos]
        return "\n".join(lines + ["", "Have a great week!"])

    due = [i for i in items if i[0] == today]
    if not due:
        return ""  # nothing due today: stay quiet
    lines = [f"📅 DAILY REMINDER | {today:%A, %d %B %Y}", "", "🔔 Due today"]
    lines += [f"• {c} | {a} | {t or 'All day'}" for d, t, c, a in due]
    return "\n".join(lines + ["", "That's it for today. Good luck, everyone! 🍀"])


def send(text):
    body = json.dumps({"msgtype": "text", "text": {"content": text, "mentioned_list": ["@all"]}}).encode()
    req = urllib.request.Request(WEBHOOK, body, {"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        resp = json.loads(r.read())
    if resp.get("errcode") != 0:
        sys.exit(f"WeCom error: {resp}")


def main():
    today = datetime.now(TZ).date()
    if os.environ.get("TODAY"):
        today = datetime.strptime(os.environ["TODAY"], "%Y-%m-%d").date()
    msg = build(load_rows(), today)
    if not msg:
        print("Nothing to send.")
        return
    if DRY:
        print(msg)
        return
    if not WEBHOOK:
        sys.exit("Set WECOM_WEBHOOK_URL")
    send(msg)
    print("Sent.")


if __name__ == "__main__":
    main()
