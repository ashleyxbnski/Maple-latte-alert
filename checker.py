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
TARGET_SHADE = "Maple Latte"
STATE_FILE = "state.json"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}

# Matches the SKU block TikTok embeds for each color, e.g.:
#   "sku_property_value_name":"Maple Latte"}],"sku_quantity":{...,
#   "available_quantity":0},...
STOCK_PATTERN = re.compile(
    r'"sku_property_value_name"\s*:\s*"' + re.escape(TARGET_SHADE) + r'".{0,1000}?'
    r'"available_quantity"\s*:\s*(\d+)',
    re.IGNORECASE | re.DOTALL,
)


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
    Returns True if Maple Latte's available_quantity > 0, False if it's 0,
    None if we couldn't find the field at all (page structure changed).
    """
    resp = requests.get(PRODUCT_URL, headers=HEADERS, timeout=20)
    resp.raise_for_status()
    html = resp.text

    match = STOCK_PATTERN.search(html)
    if not match:
        return None

    available_quantity = int(match.group(1))
    print(f"DEBUG: available_quantity for Maple Latte = {available_quantity}")
    return available_quantity > 0


def send_text(message):
    sender = os.environ["EMAIL_ADDRESS"]
    app_password = os.environ["EMAIL_APP_PASSWORD"]
    gateway_address = os.environ["TEXT_GATEWAY"]

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
