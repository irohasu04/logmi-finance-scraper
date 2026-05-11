from playwright.sync_api import sync_playwright
import pandas as pd
import re
from datetime import datetime
import gspread
from google.oauth2.service_account import Credentials
import json
import os

# =========================
# Google Credentials
# =========================

google_credentials = json.loads(
    os.environ["GOOGLE_CREDENTIALS"]
)

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

creds = Credentials.from_service_account_info(
    google_credentials,
    scopes=SCOPES
)

client = gspread.authorize(creds)

SPREADSHEET_NAME = "ログミー決算一覧"

sheet = client.open(SPREADSHEET_NAME).sheet1

# =========================
# Scraping
# =========================

BASE_URL = "https://finance.logmi.jp/search?tags=%E6%B1%BA%E7%AE%97%E8%AA%AC%E6%98%8E%E4%BC%9A"

all_data = []

with sync_playwright() as p:

    browser = p.chromium.launch(headless=True)

    page = browser.new_page()

    for page_num in range(1, 10):

        target_url = f"{BASE_URL}&page={page_num}"

        print("取得:", target_url)

        page.goto(target_url)

        page.wait_for_timeout(3000)

        html = page.content()

        articles = re.findall(
            r'<article.*?</article>',
            html,
            re.DOTALL
        )

        for article in articles:

            text = re.sub(r'<.*?>', ' ', article)
            text = re.sub(r'\s+', ' ', text)

            title_match = re.search(
                r'title=\"([^\"]+)\"',
                article
            )

            title = title_match.group(1) if title_match else ""

            url_match = re.search(
                r'href=\"([^\"]+)\"',
                article
            )

            url = url_match.group(1) if url_match else ""

            if url.startswith("/"):
                url = "https://finance.logmi.jp" + url

            date_match = re.search(
                r'(\d{4}/\d{1,2}/\d{1,2})',
                text
            )

            if date_match:
                date_str = date_match.group(1)

                dt = datetime.strptime(
                    date_str,
                    "%Y/%m/%d"
                )

                month = dt.strftime("%Y-%m")

            else:
                date_str = ""
                month = ""

            code_match = re.search(
                r'\((\d{4})\)',
                text
            )

            code = code_match.group(1) if code_match else ""

            all_data.append({
                "月": month,
                "掲載日": date_str,
                "証券コード": code,
                "タイトル": title,
                "URL": url
            })

browser.close()

# =========================
# DataFrame
# =========================

df = pd.DataFrame(all_data)

df = df.drop_duplicates(subset=["URL"])

df = df.sort_values(
    ["月", "掲載日"],
    ascending=[False, False]
)

# =========================
# Google Sheets Update
# =========================

sheet.clear()

sheet.update(
    [df.columns.values.tolist()] + df.values.tolist()
)

print("更新完了")
