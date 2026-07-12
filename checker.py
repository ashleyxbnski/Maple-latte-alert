#!/usr/bin/env python3
"""
TikTok Shop stock checker for e.l.f. Sheer For It Blush Tint - Maple Latte.

Checks the product page for the "Maple Latte" variant's stock status.
If it's in stock (and it wasn't the last time we checked), sends a text
via your carrier's email-to-SMS gateway.

Run this on a schedule (GitHub Actions, cron, Task Scheduler, etc).
"""

import json
import os
import re
import smtplib
import sys
from email.mime.text import MIMEText

import requests

PRODUCT_URL = (
    "https://shop.tiktok.com/us/pdp/sheer-for-it-blush-tint-by-e-l-f-cosmetics-"
    "multi-use-hydrating-stain/1731162610730111267"
)
TARGET_SHADE = "maple latte"
STATE_FILE = "state.json"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}


def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r") as f:
            return json.load(f)
    return {"in_stock": False}


def save_state(state):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f)


def fetch_stock_status():
    """
    Fetch the product page and look for the embedded JSON payload
    (TikTok Shop server-renders product/SKU data into a <script> tag).
    Returns True if Maple Latte appears in stock, False if sold out,
    None if we couldn't determine it (page structure changed / blocked).
    """
    resp = requests.get(PRODUCT_URL, headers=HEADERS, timeout=20)
    print(f"DEBUG: HTTP status code: {resp.status_code}")
    print(f"DEBUG: response length: {len(resp.text)} characters")
    print(f"DEBUG: first 300 characters of response:\n{resp.text[:300]}")
    resp.raise_for_status()
    html = resp.text

    print(f"DEBUG: does response contain 'maple latte' (any case)? "
          f"{'maple latte' in html.lower()}")
    print(f"DEBUG: does response contain 'captcha'? {'captcha' in html.lower()}")
    print(f"DEBUG: does response contain 'verify'? {'verify' in html.lower()}")

    lowered_html = html.lower()
    occurrence_count = lowered_html.count(TARGET_SHADE)
    print(f"DEBUG: 'maple latte' appears {occurrence_count} time(s) in the page")
    start = 0
    occurrence_num = 0
    while True:
        idx = lowered_html.find(TARGET_SHADE, start)
        if idx == -1 or occurrence_num >= 5:
            break
        occurrence_num += 1
        snippet = html[max(0, idx - 400) : idx + 400]
        print(f"DEBUG: --- occurrence {occurrence_num} (context) ---")
        print(snippet)
        print("DEBUG: --- end occurrence ---")
        start = idx + 1

    # TikTok Shop embeds product data as JSON in a script tag.
    # We search broadly for a block mentioning the shade name and
    # nearby stock/quantity fields rather than relying on one exact key,
    # since TikTok changes its internal schema periodically.
    match = re.search(
        r'\{[^{}]*"' + re.escape(TARGET_SHADE.title()) + r'"[^{}]*\}',
        html,
        re.IGNORECASE,
    )
    if not match:
        # Fallback: case-insensitive search on raw text for shade name
        # plus nearby stock-related keywords.
        idx = html.lower().find(TARGET_SHADE)
        if idx == -1:
            return None
        window = html[max(0, idx - 500) : idx + 500]
    else:
        window = match.group(0)

    lowered = window.lower()
    if "out of stock" in lowered or '"stock":0' in lowered or '"available":false' in lowered:
        return False
    if "in stock" in lowered or '"available":true' in lowered:
        return True

    return None


def send_text(message):
    sender = os.environ["EMAIL_ADDRESS"]
    app_password = os.environ["EMAIL_APP_PASSWORD"]
    gateway_address = os.environ["TEXT_GATEWAY"]  # e.g. 1234567890@vtext.com

    msg = MIMEText(message)
    msg["From"] = sender
    msg["To"] = gateway_address
    msg["Subject"] = ""

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(sender, app_password)
        server.sendmail(sender, [gateway_address], msg.as_string())


def main():
    state = load_state()
    status = fetch_stock_status()

    if status is None:
        print("Could not determine stock status this run (page structure may have "
              "changed, or the request was blocked). No alert sent.")
        save_state(state)
        sys.exit(0)

    print(f"Maple Latte in stock: {status}")

    if status and not state["in_stock"]:
        send_text(
            "Maple Latte (e.l.f. Sheer For It Blush Tint) is BACK IN STOCK on "
            f"TikTok Shop! Grab it: {PRODUCT_URL}"
        )
        print("Alert sent.")

    state["in_stock"] = status
    save_state(state)


if __name__ == "__main__":
    main()
