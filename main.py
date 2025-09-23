#!/usr/bin/env python3

import gspread
from google.oauth2.service_account import Credentials
import os
import re
from dotenv import load_dotenv
import random
import datetime
import time
import sys

load_dotenv()
SPREADSHEET_URL = os.getenv("SPREADSHEET_URL")
SHEETNAME = os.getenv("SHEETNAME")

if len(sys.argv) != 2 or sys.argv[1] not in ["collect", "cleanup"]:
    print("Usage: python3 main.py <collect|cleanup>")
    sys.exit(1)

command = sys.argv[1]

if not SHEETNAME:
    raise ValueError("Missing SHEETNAME in environment variables")

if not SPREADSHEET_URL:
    raise ValueError("Missing SPREADSHEET_URL in environment variables")

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
creds = Credentials.from_service_account_file("service_account.json", scopes=SCOPES)
client = gspread.authorize(creds)

try:
    sheet = client.open_by_url(SPREADSHEET_URL).worksheet(SHEETNAME)
except Exception as e:
    raise ValueError(f"Cannot open spreadsheet: {e}, maybe the sheet name is wrong?")

rows = sheet.get_all_values()

# Function to find column index using regex
def find_col_index(header, pattern):
    for i, col in enumerate(header):
        if re.search(pattern, col, re.IGNORECASE):
            return i
    raise ValueError(f"No column matching pattern '{pattern}' found.")

header = rows[0]
idx_timestamp = find_col_index(header, r"\b(dấu thời gian|timestamp)\b")
idx_sbd = find_col_index(header, r"\b(số báo danh|sbd)\b")
idx_lang = find_col_index(header, r"\b(ngôn ngữ|ext\w*)\b")
idx_password = find_col_index(header, r"\b(pass\w*|mật\w*)\b")
idx_mabai = find_col_index(header, r"mã bài")
idx_code = find_col_index(header, r"\bcode\b")

# Read users.txt file and load it into a dict
users = {}
if os.path.exists("users.txt"):
    with open("users.txt", "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                username, password = line.strip().split(":", 1)
                users[username] = password

    print("Loaded users:", users)
else:
    print("No users.txt file found, proceeding without user authentication.")
    exit(1)

if command == "collect":
    # Generate a random number at program starts
    random_number = random.randint(1, int(1e9))

    # Clear old folder before collect subs
    # if os.path.exists("BaiLam"):
    #     import shutil
    #     shutil.rmtree("BaiLam")
    # os.makedirs("BaiLam", exist_ok=True)

for row_num, row in enumerate(rows[1:], start=2):
    sbd = row[idx_sbd]
    timestamp_str = row[idx_timestamp]
    try:
        dt = datetime.datetime.strptime(timestamp_str, "%d/%m/%Y %H:%M:%S")
        unix_ts = int(time.mktime(dt.timetuple()))
        if command == "collect":
            # Do collecting logic
            password = row[idx_password] # Password
            lang = row[idx_lang].lower().strip() # Language
            mabai = row[idx_mabai]
            code = row[idx_code]

            # Prevent some stupid errors.
            # This should never happen unless the one who edit the sheet
            # Makes sth stupid
            if not sbd or not lang or not mabai or not code or not password:
                print(f"⚠️  Incomplete data for SBD {sbd}, skipping...")
                continue

            if sbd not in users:
                print(f"⚠️  Unknown SBD {sbd}, skipping...")
                continue

            if (users[sbd] != password):
                print(f"⚠️  Wrong password for SBD {sbd}, skipping...")
                continue

            if "c" in lang:
                ext = "cpp"
            elif "py" in lang:
                ext = "py"
            else:
                print(f"⚠️  Unknown language '{lang}' for SBD {sbd}, skipping...")
                continue

            # Save as [x][username][mabai].ext in BaiLam folder
            filename = f"[{random_number}][{sbd}][{mabai}].{ext}"
            filepath = os.path.join("BaiLam", filename)

            # If the file already exists, do not override it
            # Because the first row = last sub
            if os.path.exists(filepath):
                print(f"⚠️  File {filepath} already exists, skipping...")
                continue

            with open(filepath, "w", encoding="utf-8") as f:
                f.write(code)

            print(f"✅ Saved {filepath}")

            # Update timestamp to UNIX
            sheet.update_cell(row_num, idx_timestamp + 1, unix_ts)
        elif command == "cleanup":
            # Just update timestamp
            sheet.update_cell(row_num, idx_timestamp + 1, unix_ts)
            print(f"Marked as collected for SBD {sbd}")
    except ValueError:
        print(f"Already collected for SBD {sbd}")
        continue
