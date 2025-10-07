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


# Usage: python3 main.py <collect|cleanup> [--first|--last]
if len(sys.argv) < 2 or sys.argv[1] not in ["collect", "cleanup"]:
    print("Usage: python3 main.py <collect|cleanup> [--first|--last]")
    sys.exit(1)

command = sys.argv[1]
sub_order = "last"  # default
if len(sys.argv) > 2:
    if sys.argv[2] == "--first":
        sub_order = "first"
    elif sys.argv[2] == "--last":
        sub_order = "last"
    else:
        print("Unknown option: {}".format(sys.argv[2]))
        print("Usage: python3 main.py <collect|cleanup> [--first|--last]")
        sys.exit(1)

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
idx_sbd = find_col_index(header, r"\b(số báo danh|sbd|mã nộp bài)\b")
idx_lang = find_col_index(header, r"\b(ngôn ngữ|ext\w*)\b")
idx_mabai = find_col_index(header, r"mã bài")
idx_code = find_col_index(header, r"\bcode\b")

# Read users.txt file and load it into a dict
# Also create reverse mapping: password -> username
users = {}  # username -> password
password_to_username = {}  # password -> username (for mapping)
if os.path.exists("users.txt"):
    with open("users.txt", "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                username, password = line.strip().split(":", 1)
                users[username] = password
                
                # Check for duplicate passwords
                if password in password_to_username:
                    print(f"❌ ERROR: Duplicate password '{password}' found for users '{password_to_username[password]}' and '{username}'")
                    print("Please ensure each user has a unique password in users.txt")
                    exit(1)
                
                password_to_username[password] = username

    print(f"Loaded {len(users)} users with unique passwords")
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


# Group submissions by (actual_username, mabai)
subs = {}
row_map = {}
for row_num, row in enumerate(rows[1:], start=2):
    sbd = row[idx_sbd]
    timestamp_str = row[idx_timestamp]
    try:
        dt = datetime.datetime.strptime(timestamp_str, "%d/%m/%Y %H:%M:%S")
    except ValueError:
        continue
    # Map password to username if the SBD is a password
    actual_username = sbd
    if sbd in password_to_username:
        actual_username = password_to_username[sbd]
    elif sbd not in users:
        continue
    mabai = row[idx_mabai]
    key = (actual_username, mabai)
    if key not in subs:
        subs[key] = []
        row_map[key] = []
    subs[key].append((dt, row_num, row))
    row_map[key].append(row_num)

# For each (user, mabai), pick first or last
for key, sublist in subs.items():
    if sub_order == "first":
        chosen = min(sublist, key=lambda x: x[0])
    else:
        chosen = max(sublist, key=lambda x: x[0])
    dt, row_num, row = chosen
    unix_ts = int(time.mktime(dt.timetuple()))
    sbd = row[idx_sbd]
    actual_username = key[0]
    mabai = key[1]
    lang = row[idx_lang].lower().strip()
    code = row[idx_code]
    if command == "collect":
        # Prevent some stupid errors.
        if not sbd or not lang or not mabai or not code:
            print(f"⚠️  Incomplete data for SBD {sbd}, skipping...")
            continue
        if "c" in lang:
            ext = "cpp"
        elif "py" in lang:
            ext = "py"
        else:
            print(f"⚠️  Unknown language '{lang}' for SBD {sbd}, skipping...")
            continue
        filename = f"[{random_number}][{actual_username}][{mabai}].{ext}"
        filepath = os.path.join("BaiLam", filename)
        if os.path.exists(filepath):
            print(f"⚠️  File {filepath} already exists, skipping...")
            continue
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(code)
        print(f"✅ Saved {filepath}")
        sheet.update_cell(row_num, idx_timestamp + 1, unix_ts)
    elif command == "cleanup":
        sheet.update_cell(row_num, idx_timestamp + 1, unix_ts)
        print(f"Marked as collected for SBD {sbd}")
