# 📩 Mail → WhatsApp Forwarder

Get every new email from your Gmail inbox as a clean WhatsApp message, automatically, for free, using **GitHub Actions** + **CallMeBot**. No server, no computer left turned on.

## ✨ What you receive

```
📩 NEW EMAIL
━━━━━━━━━━━━━━
👤 From: John Smith
✉️ Address: john@example.com
📌 Subject: Project meeting tomorrow
🕒 Received: 31/10/2026 14:32
📎 Attachments (1):
  • report.pdf (240.5 KB)
🔗 Links (1):
  • https://meet.example.com/abc
📝 Preview:
Hello, here is the report for tomorrow...
━━━━━━━━━━━━━━
```

- First run: sends your **latest** email, then only **new** ones.
- Your emails are **never marked as read** (read-only access).
- Shows sender name and address, subject, date/time, attachment names and sizes, links, and a short preview.

## 🧰 How it works

1. GitHub Actions starts the script every 5 minutes (`cron`).
2. The script connects to Gmail through **IMAP** and looks for emails newer than the last one it sent.
3. For each new email it builds a formatted message and sends it through the **CallMeBot** WhatsApp API.
4. It saves the last email ID in `state.json` so nothing is sent twice.

## 📋 Requirements

- A Gmail account (or a Google-hosted school email) with **2-Step Verification** enabled
- A WhatsApp number
- A free GitHub account

## 🚀 Setup (step by step)

### 1. Get your Gmail App Password
1. Enable 2-Step Verification: Google Account → Security.
2. Go to Google Account → Security → **App passwords**.
3. Create one (name it `mail-whatsapp`) and copy the 16-character code.
4. Make sure IMAP is on: Gmail → Settings → Forwarding and POP/IMAP → **Enable IMAP**.

> ⚠️ Use an App Password, **never** your real password.

### 2. Get your CallMeBot API key
1. Go to the CallMeBot WhatsApp page at **callmebot.com** and follow the instructions to activate your number.
2. You will receive your **API key** on WhatsApp.

### 3. Fork or create the repository
- Click **Fork** on this repo (or create a new repo and upload the files).
- Make sure the project contains:
  ```
  mail_to_whatsapp.py
  .github/workflows/mail-to-whatsapp.yml
  ```

### 4. Add your secrets
Go to **Settings → Secrets and variables → Actions → New repository secret** and add:

| Secret name | Value |
|---|---|
| `EMAIL_USER` | your email, e.g. `name@gmail.com` |
| `EMAIL_APP_PASSWORD` | the 16-character App Password |
| `IMAP_SERVER` | `imap.gmail.com` |
| `PHONE_NUMBER` | your number with country code, no `+` or spaces, e.g. `22212345678` |
| `CALLMEBOT_API_KEY` | the key CallMeBot sent you |

🔒 Secrets are encrypted by GitHub. **Never** write them in the code or in this README.

### 5. Allow the workflow to save its state
**Settings → Actions → General → Workflow permissions → Read and write permissions → Save.**

### 6. Run it
1. Open the **Actions** tab (click *"I understand my workflows, enable them"* if asked).
2. Choose **Mail to WhatsApp → Run workflow**.
3. Within a minute your latest email arrives on WhatsApp. 🎉

After that it runs automatically every 5 minutes.

## ⚙️ Customization

| What | Where | How |
|---|---|---|
| Check frequency | `.github/workflows/mail-to-whatsapp.yml` | change `*/5 * * * *` (e.g. `*/30 * * * *` = every 30 min) |
| Time zone | `mail_to_whatsapp.py` | change `TIMEZONE = ZoneInfo("Africa/Nouakchott")` |
| Preview length | `mail_to_whatsapp.py` | change `BODY_PREVIEW_CHARS` |
| Max links shown | `mail_to_whatsapp.py` | change `MAX_LINKS` |

## ⚠️ Good to know

- **Not instant:** GitHub scheduled runs can be delayed by 5–15 minutes.
- **Free minutes:** public repos have unlimited Actions minutes. Private repos get 2,000 minutes per month, so use `*/30` there.
- **60-day rule:** GitHub pauses scheduled workflows in inactive repos. The script updates `state.json` daily to avoid this. If it stops, go to Actions and click **Enable workflow**.
- **CallMeBot limits:** messages are limited in length and rate, so the script waits a few seconds between messages.

## 🛠️ Troubleshooting

| Problem | Solution |
|---|---|
| `Missing secret/environment variable` | A secret name is wrong or missing. Check spelling (capital letters, underscores). |
| `AUTHENTICATIONFAILED` | Wrong App Password, or IMAP is disabled. Create a new App Password. |
| `CallMeBot failed` | Wrong API key or phone number, or the number was not activated with CallMeBot. |
| `Permission denied` when saving state | Do step 5 (Read and write permissions). |
| Nothing arrives | Open the failed run in **Actions** and read the log. |

## 🔐 Security tips

- Keep your App Password and API key **secret**. If you ever shared them, delete them and create new ones.
- You can revoke an App Password at any time in your Google Account without changing your real password.

## 📄 License

MIT. Free to use and improve. Made for students 🎓
