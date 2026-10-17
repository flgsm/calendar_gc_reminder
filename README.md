# Class calendar + WeCom reminder bot

## 1. Database (Supabase, free)
1. Create a project at supabase.com. Open SQL Editor, paste `setup.sql`, run.
2. Settings > API: copy the **Project URL** and the **anon public key**.

## 2. Calendar app
Open `index.html`, paste the URL and key into `CFG` at the top of the script.
Host it free on GitHub Pages / Netlify / Cloudflare Pages and share the link with the class.
(Without a URL it runs in demo mode, saving only in your browser.)
Anyone with the link can add and edit, so keep the link within the class.

## 3. Bot (GitHub Actions)
Push this folder to a private repo. Add Actions secrets:
`SUPABASE_URL`, `SUPABASE_KEY`, `WECOM_WEBHOOK_URL`.
Daily 08:00 digest (Mon-Sat) and Sunday 20:00 week-ahead, Shanghai time. Test via Actions > Run workflow.

## Local test
    SUPABASE_URL=... SUPABASE_KEY=... DRY_RUN=1 python reminder_bot.py
