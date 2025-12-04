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


# Usage: python3 main.py <collect|cleanup> [--first|--last] [--row=N] [--watch]
if len(sys.argv) < 2 or sys.argv[1] not in ["collect", "cleanup"]:
    print("Usage: python3 main.py <collect|cleanup> [--first|--last] [--row=N] [--watch]")
    sys.exit(1)

command = sys.argv[1]
sub_order = "last"  # default
start_row = 2  # default (skip header at row 1)
watch_mode = False  # default

# Parse optional arguments
if len(sys.argv) > 2:
    for arg in sys.argv[2:]:
        if arg == "--first":
            sub_order = "first"
        elif arg == "--last":
            sub_order = "last"
        elif arg == "--watch":
            watch_mode = True
        elif arg.startswith("--row="):
            try:
                start_row = int(arg.split("=")[1])
                if start_row < 2:
                    print("ERROR: --row must be >= 2 (row 1 is the header)")
                    sys.exit(1)
            except (ValueError, IndexError):
                print("ERROR: Invalid --row format. Use --row=N where N is a number >= 2")
                sys.exit(1)
        else:
            print("Unknown option: {}".format(arg))
            print("Usage: python3 main.py <collect|cleanup> [--first|--last] [--row=N] [--watch]")
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
print(f"Sheet has {len(rows)} total rows (including header)")

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

print(f"Column indices: timestamp={idx_timestamp}, sbd={idx_sbd}, lang={idx_lang}, mabai={idx_mabai}, code={idx_code}")

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

def run_collect():
    """Execute the collect command"""
    # Generate a random number at program starts
    random_number = random.randint(1, int(1e9))

    # Clear old folder before collect subs
    # if os.path.exists("BaiLam"):
    #     import shutil
    #     shutil.rmtree("BaiLam")
    # os.makedirs("BaiLam", exist_ok=True)

    # For collect: process ALL submissions, not just unique combinations
    print(f"Reading from row {start_row} to end...")
    
    # First pass: collect all valid submissions with timestamps
    submissions = []
    for row_num, row in enumerate(rows[start_row-1:], start=start_row):
        # Skip empty rows or rows that are too short
        if not row or len(row) <= max(idx_timestamp, idx_sbd, idx_lang, idx_mabai, idx_code):
            continue
        
        try:
            sbd = row[idx_sbd].strip() if idx_sbd < len(row) else ""
            timestamp_str = row[idx_timestamp].strip() if idx_timestamp < len(row) else ""
            
            # Skip if essential fields are empty
            if not sbd or not timestamp_str:
                continue
                
            # Try multiple date formats
            dt = None
            for date_format in ["%d/%m/%Y %H:%M:%S", "%m/%d/%Y %H:%M:%S", "%Y-%m-%d %H:%M:%S", "%d-%m-%Y %H:%M:%S"]:
                try:
                    dt = datetime.datetime.strptime(timestamp_str, date_format)
                    break
                except ValueError:
                    continue
            
            if dt is None:
                continue
        except (ValueError, IndexError):
            continue
        
        # Map password to username if the SBD is a password
        actual_username = sbd
        if sbd in password_to_username:
            actual_username = password_to_username[sbd]
        elif sbd not in users:
            continue
        
        mabai = row[idx_mabai].strip() if idx_mabai < len(row) else ""
        lang = row[idx_lang].strip() if idx_lang < len(row) else ""
        code = row[idx_code].strip() if idx_code < len(row) else ""
        
        # Make mabai uppercase
        mabai = mabai.upper()
        
        # Prevent some stupid errors.
        if not sbd or not lang or not mabai or not code:
            continue
        
        if "c" in lang.lower():
            ext = "cpp"
        elif "py" in lang.lower():
            ext = "py"
        else:
            continue
        
        submissions.append((dt, row_num, sbd, actual_username, mabai, ext, code))
    
    # Sort submissions by timestamp (ascending = oldest first, descending = newest first)
    if sub_order == "first":
        submissions.sort(key=lambda x: x[0])  # Oldest first, so first occurrences are processed first
    else:
        submissions.sort(key=lambda x: x[0])  # Same order, but later ones will overwrite
    
    print(f"Found {len(submissions)} valid submissions to process (order: {sub_order})")
    
    # Second pass: process submissions in sorted order
    processed_count = 0
    skipped_count = len(rows) - start_row + 1 - len(submissions)
    os.makedirs("BaiLam", exist_ok=True)
    
    # Batch updates for Google Sheets
    batch_updates = []
    
    for dt, row_num, sbd, actual_username, mabai, ext, code in submissions:
        filename = f"[{random_number}][{actual_username}][{mabai}].{ext}"
        filepath = os.path.join("BaiLam", filename)
        
        if sub_order == "first":
            # For --first: keep the first submission, skip if file exists
            if os.path.exists(filepath):
                print(f"⚠️  File {filepath} already exists (keeping first submission), skipping...")
                batch_updates.append((row_num, idx_timestamp + 1, int(time.mktime(dt.timetuple()))))
                continue
        # For --last: always overwrite to keep the latest submission
        
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(code)
        print(f"✅ Saved {filepath}")
        batch_updates.append((row_num, idx_timestamp + 1, int(time.mktime(dt.timetuple()))))
        processed_count += 1
    
    # Batch update all timestamps at once
    if batch_updates:
        print(f"Updating {len(batch_updates)} timestamps in Google Sheets...")
        for row_num, col_num, value in batch_updates:
            sheet.update_cell(row_num, col_num, value)
        print("✅ All timestamps updated")
    
    print(f"✅ Collect complete. Processed {processed_count} submissions, skipped {skipped_count} rows.")

def run_cleanup():
    """Execute the cleanup command"""
    # Group submissions by (actual_username, mabai) for cleanup
    subs = {}
    row_map = {}
    print(f"Reading from row {start_row} to end...")
    processed_count = 0
    skipped_count = 0
    for row_num, row in enumerate(rows[start_row-1:], start=start_row):
        # Skip empty rows or rows that are too short
        if not row or len(row) <= max(idx_timestamp, idx_sbd, idx_lang, idx_mabai, idx_code):
            skipped_count += 1
            continue
        
        try:
            sbd = row[idx_sbd].strip() if idx_sbd < len(row) else ""
            timestamp_str = row[idx_timestamp].strip() if idx_timestamp < len(row) else ""
            
            # Skip if essential fields are empty
            if not sbd or not timestamp_str:
                skipped_count += 1
                continue
                
            # Try multiple date formats
            dt = None
            for date_format in ["%d/%m/%Y %H:%M:%S", "%m/%d/%Y %H:%M:%S", "%Y-%m-%d %H:%M:%S", "%d-%m-%Y %H:%M:%S"]:
                try:
                    dt = datetime.datetime.strptime(timestamp_str, date_format)
                    break
                except ValueError:
                    continue
            
            if dt is None:
                skipped_count += 1
                continue
        except (ValueError, IndexError):
            skipped_count += 1
            continue
        
        # Map password to username if the SBD is a password
        actual_username = sbd
        if sbd in password_to_username:
            actual_username = password_to_username[sbd]
        elif sbd not in users:
            skipped_count += 1
            continue
        
        mabai = row[idx_mabai].strip().upper() if idx_mabai < len(row) else ""
        if not mabai:
            skipped_count += 1
            continue
            
        key = (actual_username, mabai)
        if key not in subs:
            subs[key] = []
            row_map[key] = []
        subs[key].append((dt, row_num, row))
        row_map[key].append(row_num)
        processed_count += 1

    print(f"Found {len(subs)} unique (user, problem) combinations to process from {processed_count} valid rows (skipped {skipped_count} rows)")

    # Batch updates for Google Sheets
    batch_updates = []
    
    # For each (user, mabai), pick first or last
    for key, sublist in subs.items():
        if sub_order == "first":
            chosen = min(sublist, key=lambda x: x[0])
        else:
            chosen = max(sublist, key=lambda x: x[0])
        dt, row_num, row = chosen
        unix_ts = int(time.mktime(dt.timetuple()))
        sbd = row[idx_sbd].strip() if idx_sbd < len(row) else ""
        batch_updates.append((row_num, idx_timestamp + 1, unix_ts))
        print(f"Marked as collected for SBD {sbd}")

    # Batch update all timestamps at once
    if batch_updates:
        print(f"Updating {len(batch_updates)} timestamps in Google Sheets...")
        for row_num, col_num, value in batch_updates:
            sheet.update_cell(row_num, col_num, value)
        print("✅ All timestamps updated")
    
    print(f"✅ Cleanup complete. Processed {len(subs)} unique (user, problem) combinations.")

# Main execution
if watch_mode:
    print(f"🔄 Watch mode enabled. Running {command} every 5 minutes. Press Ctrl+C to stop.")
    iteration = 1
    while True:
        try:
            print(f"\n{'='*60}")
            print(f"🔄 Watch iteration #{iteration} - {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"{'='*60}\n")
            
            # Refresh data from sheet
            rows = sheet.get_all_values()
            
            if command == "collect":
                run_collect()
            elif command == "cleanup":
                run_cleanup()
            
            print("\n⏳ Waiting 5 minutes until next check...")
            time.sleep(300)  # 5 minutes
            iteration += 1
        except KeyboardInterrupt:
            print(f"\n\n🛑 Watch mode stopped by user. Total iterations: {iteration}")
            sys.exit(0)
        except Exception as e:
            print(f"\n❌ Error during iteration #{iteration}: {e}")
            print("⏳ Retrying in 5 minutes...")
            time.sleep(300)
            iteration += 1
else:
    # Single run
    if command == "collect":
        run_collect()
    elif command == "cleanup":
        run_cleanup()
