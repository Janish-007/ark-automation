import logging
from playwright.sync_api import sync_playwright
import pandas as pd
from datetime import datetime
import time
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# === ✅ Logging Setup ===
logging.basicConfig(
    filename="ark_automation.log",
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
console = logging.StreamHandler()
console.setLevel(logging.INFO)
formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
console.setFormatter(formatter)
logging.getLogger().addHandler(console)

# === ✅ Config ===
GOOGLE_SHEET_NAME = "Ark Automation Testing - Updated"
CREDENTIALS_FILE = "credentials(1).json"

def read_google_sheet(sheet_name):
    logging.info(f"📄 Reading Google Sheet: {sheet_name}")
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive"
    ]
    creds = ServiceAccountCredentials.from_json_keyfile_name(CREDENTIALS_FILE, scope)
    client = gspread.authorize(creds)
    sheet = client.open(sheet_name).sheet1
    data = sheet.get_all_records()
    logging.info(f"✅ Sheet read successfully: {len(data)} rows.")
    return sheet, data

def mark_as_posted(sheet, row_index):
    headers = sheet.row_values(1)
    try:
        status_col_index = headers.index("Status") + 1
        sheet.update_cell(row_index + 2, status_col_index, "Posted")
        logging.info(f"✅ Row {row_index + 2} marked as 'Posted' in 'Status' column.")
    except ValueError:
        logging.error("❌ 'Status' column not found in the sheet header.")

def post_to_ark(row, index, sheet):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, slow_mo=100)
        context = browser.new_context(
            viewport={"width": 390, "height": 844},
            user_agent="Mozilla/5.0 (Linux; Android 11...) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/94.0.4606.61 Mobile Safari/537.36"
        )
        page = context.new_page()

        ARK_URL = "https://app-dev.thearkofrevival.com/auth/login"
        EMAIL = "admin@justomerchantz.com"
        PASSWORD = "P@ssword0123"

        description = str(row.get("Description", "")).strip()
        image_path = str(row.get("Image", "")).strip()
        org_name = str(row.get("Organization", "")).strip()

        if not description or not image_path or not org_name:
            logging.warning(f"⚠️ Row {index+2}: Missing required fields.")
            browser.close()
            return

        try:
            logging.info(f"🔐 Row {index+2}: Logging into Ark platform...")
            page.goto(ARK_URL)
            page.wait_for_load_state("domcontentloaded")
            page.locator("input").nth(0).fill(EMAIL)
            page.locator("input").nth(1).fill(PASSWORD)
            page.get_by_role("button", name="Login").click()
            page.wait_for_load_state("networkidle")
            time.sleep(2)

            logging.info(f"🏢 Row {index+2}: Selecting organization '{org_name}'...")
            try:
                page.get_by_role("button", name=org_name).click()
            except:
                org_button = page.get_by_text(org_name, exact=True)
                if org_button:
                    org_button.click()
                else:
                    logging.error(f"❌ Row {index+2}: Organization '{org_name}' not found.")
                    browser.close()
                    return

            time.sleep(2)
            page.get_by_test_id("org-navigate-dashboard-post-icon").click()
            time.sleep(2)
            page.get_by_test_id("organization-post-tab-create-btn").click()
            time.sleep(2)

            try:
                page.get_by_label("Public").check()
            except:
                page.locator("input[type='radio']").nth(0).check()

            page.locator("textarea").first.fill(description)
            page.locator("input[testid='post-edit-drawer-image-upload-input']").set_input_files(image_path)

            page.get_by_role("button", name="Submit").click()
            time.sleep(5)

            page.get_by_test_id("post-edit-drawer-active-radio-inp").check()
            page.get_by_test_id("post-edit-drawer-create-btn").click()
            page.wait_for_load_state("networkidle")
            time.sleep(5)

            screenshot_path = f"post_confirmation_{index+1}.png"
            page.screenshot(path=screenshot_path)
            logging.info(f"📸 Row {index+2}: Screenshot saved to {screenshot_path}")

            logging.info(f"✅ Row {index+2}: Post submitted successfully.")
            mark_as_posted(sheet, index)

        except Exception as e:
            logging.exception(f"❌ Row {index+2} Error: {e}")

        finally:
            browser.close()
            logging.info(f"🧹 Row {index+2}: Browser closed.\n")

def main():
    try:
        sheet, data = read_google_sheet(GOOGLE_SHEET_NAME)
        for index, row in enumerate(data):
            if str(row.get("Submit", "")).strip().lower() == "yes":
                schedule_time = row.get("Schedule")
                if isinstance(schedule_time, str):
                    schedule_time = pd.to_datetime(schedule_time)

                if isinstance(schedule_time, pd.Timestamp) and schedule_time <= datetime.now():
                    logging.info(f"▶️ Row {index+2}: Scheduled time reached. Posting...")
                    post_to_ark(row, index, sheet)
                else:
                    logging.info(f"⏳ Row {index+2}: Future schedule ({schedule_time}). Skipping.")
            else:
                logging.info(f"⏩ Row {index+2}: Skipped (Submit != 'yes').")
    except Exception as e:
        logging.exception(f"❌ Fatal error: {e}")

if __name__ == "__main__":
    main()