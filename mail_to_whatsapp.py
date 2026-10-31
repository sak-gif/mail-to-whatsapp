#!/usr/bin/env python3
"""
Mail -> WhatsApp forwarder (for GitHub Actions).

- Reads your inbox through IMAP (does NOT mark mails as read).
- First run: sends the latest mail, then remembers it.
- Next runs: sends every NEW mail since the last one, oldest first.
- Sends a clean formatted WhatsApp message through CallMeBot.

Secrets (environment variables):
  EMAIL_USER, EMAIL_APP_PASSWORD, IMAP_SERVER, PHONE_NUMBER, CALLMEBOT_API_KEY
"""

import email
import imaplib
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from email.header import decode_header, make_header
from email.utils import parseaddr, parsedate_to_datetime
from html import unescape
from zoneinfo import ZoneInfo

STATE_FILE = "state.json"
TIMEZONE = ZoneInfo("Africa/Nouakchott")  # change if needed
MAX_PER_RUN = 20          # max messages sent per run (rest sent next run)
BODY_PREVIEW_CHARS = 300  # length of the body preview
MAX_LINKS = 5
MAX_MSG_CHARS = 1500
DELAY_BETWEEN_MSG = 4     # seconds, avoids CallMeBot rate limit

URL_RE = re.compile(r"https?://[^\s<>\"')\]]+", re.IGNORECASE)


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------
def env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        sys.exit(f"Missing secret/environment variable: {name}")
    return value


def decode_str(value) -> str:
    if not value:
        return ""
    try:
        return str(make_header(decode_header(value))).strip()
    except Exception:
        return str(value).strip()


def html_to_text(html: str) -> str:
    html = re.sub(r"(?is)<(script|style).*?>.*?</\1>", " ", html)
    html = re.sub(r"(?i)<br\s*/?>|</p>|</div>|</tr>|</li>", "\n", html)
    text = re.sub(r"(?s)<[^>]+>", " ", html)
    return unescape(text)


def clean_text(text: str) -> str:
    text = re.sub(r"[ \t\r\f\v]+", " ", text)
    text = re.sub(r"\n\s*\n+", "\n", text)
    return text.strip()


def human_size(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} TB"


def parse_message(raw: bytes) -> dict:
    msg = email.message_from_bytes(raw)

    name, addr = parseaddr(msg.get("From", ""))
    name = decode_str(name) or addr
    subject = decode_str(msg.get("Subject")) or "(no subject)"

    try:
        dt = parsedate_to_datetime(msg.get("Date"))
        date_str = dt.astimezone(TIMEZONE).strftime("%d/%m/%Y %H:%M")
    except Exception:
        date_str = "unknown"

    text_parts, html_parts, attachments = [], [], []

    for part in msg.walk():
        if part.is_multipart():
            continue
        ctype = part.get_content_type()
        filename = decode_str(part.get_filename())
        disp = str(part.get("Content-Disposition", "")).lower()

        if filename or "attachment" in disp:
            payload = part.get_payload(decode=True) or b""
            attachments.append((filename or "unnamed file", len(payload)))
            continue

        try:
            payload = part.get_payload(decode=True)
            if payload is None:
                continue
            charset = part.get_content_charset() or "utf-8"
            content = payload.decode(charset, errors="replace")
        except Exception:
            continue

        if ctype == "text/plain":
            text_parts.append(content)
        elif ctype == "text/html":
            html_parts.append(content)

    plain = clean_text("\n".join(text_parts))
    if not plain and html_parts:
        plain = clean_text(html_to_text("\n".join(html_parts)))

    # links from both plain text and html hrefs
    links = []
    sources = text_parts + html_parts
    for src in sources:
        for u in URL_RE.findall(src):
            u = unescape(u).rstrip(".,;")
            if u not in links:
                links.append(u)

    preview = plain.replace("\n", " ")
    preview = re.sub(r"https?://\S+", "[link]", preview)
    preview = re.sub(r"\s+", " ", preview).strip()
    if len(preview) > BODY_PREVIEW_CHARS:
        preview = preview[:BODY_PREVIEW_CHARS].rstrip() + "..."

    return {
        "name": name,
        "addr": addr,
        "subject": subject,
        "date": date_str,
        "preview": preview,
        "attachments": attachments,
        "links": links,
    }


def format_whatsapp(m: dict) -> str:
    lines = [
        "📩 *NEW EMAIL*",
        "━━━━━━━━━━━━━━",
        f"👤 *From:* {m['name']}",
        f"✉️ *Address:* {m['addr']}",
        f"📌 *Subject:* {m['subject']}",
        f"🕒 *Received:* {m['date']}",
    ]

    if m["attachments"]:
        lines.append("")
        lines.append(f"📎 *Attachments ({len(m['attachments'])}):*")
        for fname, size in m["attachments"]:
            lines.append(f"  • {fname} ({human_size(size)})")
    else:
        lines.append("📎 *Attachments:* none")

    if m["links"]:
        lines.append("")
        lines.append(f"🔗 *Links ({len(m['links'])}):*")
        for link in m["links"][:MAX_LINKS]:
            lines.append(f"  • {link}")
        if len(m["links"]) > MAX_LINKS:
            lines.append(f"  … +{len(m['links']) - MAX_LINKS} more")

    if m["preview"]:
        lines.append("")
        lines.append("📝 *Preview:*")
        lines.append(m["preview"])

    lines.append("━━━━━━━━━━━━━━")
    text = "\n".join(lines)
    if len(text) > MAX_MSG_CHARS:
        text = text[: MAX_MSG_CHARS - 3] + "..."
    return text


def send_whatsapp(phone: str, api_key: str, text: str) -> None:
    phone = phone if phone.startswith("+") else "+" + phone
    url = (
        "https://api.callmebot.com/whatsapp.php?"
        + urllib.parse.urlencode({"phone": phone, "text": text, "apikey": api_key})
    )
    last_err = None
    for attempt in range(3):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "mail-to-wa/1.0"})
            with urllib.request.urlopen(req, timeout=40) as resp:
                body = resp.read().decode("utf-8", errors="replace")
                if resp.status == 200 and "error" not in body.lower()[:200]:
                    return
                last_err = f"HTTP {resp.status}: {body[:200]}"
        except urllib.error.HTTPError as e:
            last_err = f"HTTP {e.code}: {e.read().decode('utf-8', 'replace')[:200]}"
        except Exception as e:  # network error
            last_err = str(e)
        time.sleep(5 * (attempt + 1))
    raise RuntimeError(f"CallMeBot failed: {last_err}")


# --------------------------------------------------------------------------
# State
# --------------------------------------------------------------------------
def load_state() -> dict:
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_state(state: dict) -> None:
    state["last_run"] = datetime.now(TIMEZONE).strftime("%Y-%m-%d")  # keeps repo active
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)


# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------
def main() -> None:
    user = env("EMAIL_USER")
    password = env("EMAIL_APP_PASSWORD").replace(" ", "")
    server = env("IMAP_SERVER")
    phone = env("PHONE_NUMBER")
    api_key = env("CALLMEBOT_API_KEY")

    mail = imaplib.IMAP4_SSL(server)
    mail.login(user, password)
    mail.select("INBOX", readonly=True)  # readonly => never marks as read

    uidvalidity = int(mail.response("UIDVALIDITY")[1][0])

    state = load_state()
    first_run = (
        "last_uid" not in state or state.get("uidvalidity") != uidvalidity
    )

    typ, data = mail.uid("SEARCH", None, "ALL")
    all_uids = [int(x) for x in data[0].split()] if data and data[0] else []

    if first_run:
        # send only the latest mail, then continue with new ones
        to_send = all_uids[-1:]
        print("First run: sending the latest email.")
    else:
        last_uid = int(state["last_uid"])
        to_send = [u for u in all_uids if u > last_uid]

    print(f"{len(to_send)} email(s) to send.")
    to_send = to_send[:MAX_PER_RUN]

    state["uidvalidity"] = uidvalidity
    if first_run and not all_uids:
        state["last_uid"] = 0

    failed = False
    try:
        for uid in to_send:
            typ, msg_data = mail.uid("FETCH", str(uid), "(BODY.PEEK[])")
            raw = None
            for item in msg_data:
                if isinstance(item, tuple):
                    raw = item[1]
                    break
            if raw is None:
                print(f"UID {uid}: could not fetch, skipping.")
                state["last_uid"] = uid
                continue

            parsed = parse_message(raw)
            send_whatsapp(phone, api_key, format_whatsapp(parsed))
            print(f"Sent UID {uid}: {parsed['subject']}")
            state["last_uid"] = uid
            time.sleep(DELAY_BETWEEN_MSG)
    except Exception as e:
        failed = True
        print(f"ERROR: {e}", file=sys.stderr)
    finally:
        if "last_uid" not in state and all_uids:
            state["last_uid"] = all_uids[-1]
        save_state(state)
        try:
            mail.logout()
        except Exception:
            pass

    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
