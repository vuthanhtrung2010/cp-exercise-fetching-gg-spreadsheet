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


def parse_time_interval(time_str):
    """Parse time interval string (e.g., '5s', '5m', '1h') to seconds"""
    time_str = time_str.strip().lower()
    if not time_str:
        return 5  # default 5 seconds
    
    # Extract number and unit
    match = re.match(r'^(\d+\.?\d*)([smh]?)$', time_str)
    if not match:
        print(f"ERROR: Invalid time format '{time_str}'. Use formats like: 5s, 5m, 1h")
        sys.exit(1)
    
    value = float(match.group(1))
    unit = match.group(2) or 's'  # default to seconds if no unit
    
    if unit == 's':
        return int(value)
    elif unit == 'm':
        return int(value * 60)
    elif unit == 'h':
        return int(value * 3600)

# Usage: python3 main.py <collect|cleanup> [--first|--last] [--row=N] [--watch[=interval]]
if len(sys.argv) < 2 or sys.argv[1] not in ["collect", "cleanup"]:
    print("Usage: python3 main.py <collect|cleanup> [--first|--last] [--row=N] [--watch[=interval]]")
    print("  --watch interval can be: 5s, 5m, 1h (default: 5s)")
    sys.exit(1)

command = sys.argv[1]
sub_order = "last"  # default
start_row = 2  # default (skip header at row 1)
watch_mode = False  # default
watch_interval = 5  # default 5 seconds

# Parse optional arguments
i = 2
while i < len(sys.argv):
    arg = sys.argv[i]
    
    if arg == "--first":
        sub_order = "first"
    elif arg == "--last":
        sub_order = "last"
    elif arg == "--watch":
        watch_mode = True
        # Check if next arg is a time interval (not starting with --)
        if i + 1 < len(sys.argv) and not sys.argv[i + 1].startswith("--"):
            watch_interval = parse_time_interval(sys.argv[i + 1])
            i += 1  # skip the interval arg
        else:
            watch_interval = 5  # default
    elif arg.startswith("--watch="):
        watch_mode = True
        interval_str = arg.split("=", 1)[1]
        watch_interval = parse_time_interval(interval_str)
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
        print("Usage: python3 main.py <collect|cleanup> [--first|--last] [--row=N] [--watch[=interval]]")
        print("  --watch interval can be: 5s, 5m, 1h (default: 5s)")
        sys.exit(1)
    
    i += 1

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

# Function to find column index using regex
def find_col_index(header, pattern):
    for i, col in enumerate(header):
        if re.search(pattern, col, re.IGNORECASE):
            return i
    raise ValueError(f"No column matching pattern '{pattern}' found.")

# Efficient data fetching using batch_get
def get_sheet_data(start_row_num=1, end_row_num=None):
    """Fetch sheet data efficiently using batch_get"""
    # Don't include sheet name in range - worksheet.batch_get() already operates on this sheet
    if end_row_num is None:
        range_str = f"A{start_row_num}:Z"
    else:
        range_str = f"A{start_row_num}:Z{end_row_num}"
    
    try:
        data = sheet.batch_get([range_str])
        if data and len(data) > 0:
            return data[0]
        return []
    except Exception as e:
        print(f"⚠️ Error fetching data: {e}")
        # Exponential backoff on error
        time.sleep(random.uniform(1, 3))
        raise

# Initial data load
rows = get_sheet_data()
print(f"Sheet has {len(rows)} total rows (including header)")

header = rows[0]
idx_timestamp = find_col_index(header, r"\b(dấu thời gian|timestamp)\b")
idx_sbd = find_col_index(header, r"\b(số báo danh|sbd|mã nộp bài)\b")
idx_lang = find_col_index(header, r"\b(ngôn ngữ|ext\w*)\b")
idx_mabai = find_col_index(header, r"mã bài")
idx_code = find_col_index(header, r"\bcode\b")

print(f"Column indices: timestamp={idx_timestamp}, sbd={idx_sbd}, lang={idx_lang}, mabai={idx_mabai}, code={idx_code}")

# Track last checked timestamp for incremental processing
last_checked_timestamp = 0

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

def run_collect(incremental=False):
    """Execute the collect command
    
    Args:
        incremental: If True, only process rows with timestamp > last_checked_timestamp
    """
    global last_checked_timestamp
    
    # Generate a random number at program starts
    random_number = random.randint(1, int(1e9))

    # Clear old folder before collect subs
    # if os.path.exists("BaiLam"):
    #     import shutil
    #     shutil.rmtree("BaiLam")
    # os.makedirs("BaiLam", exist_ok=True)

    # For collect: process ALL submissions, not just unique combinations
    if incremental:
        print(f"Reading from row {start_row} to end (incremental mode: timestamp > {last_checked_timestamp})...")
    else:
        print(f"Reading from row {start_row} to end...")
    
    # First pass: collect all valid submissions with timestamps
    submissions = []
    current_max_timestamp = last_checked_timestamp
    
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
            
            # Convert to UNIX timestamp for comparison
            unix_timestamp = int(time.mktime(dt.timetuple()))
            
            # Skip if incremental mode and timestamp is not newer
            if incremental and unix_timestamp <= last_checked_timestamp:
                continue
            
            # Track the maximum timestamp seen
            current_max_timestamp = max(current_max_timestamp, unix_timestamp)
            
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
    
    # Batch update all timestamps at once using a single API call
    if batch_updates:
        print(f"Updating {len(batch_updates)} timestamps in Google Sheets (single API call)...")
        try:
            # Use gspread.Cell for efficient batch updates in one request
            cells = [gspread.Cell(r, c, v) for (r, c, v) in batch_updates]
            sheet.update_cells(cells, value_input_option="USER_ENTERED")
            print("✅ All timestamps updated in one batch")
        except Exception as e:
            print(f"⚠️ Error updating timestamps: {e}")
            # Exponential backoff on error
            time.sleep(random.uniform(1, 3))
            raise
    
    # Update last checked timestamp for incremental mode
    if current_max_timestamp > last_checked_timestamp:
        last_checked_timestamp = current_max_timestamp
        print(f"📊 Updated last checked timestamp to: {last_checked_timestamp}")
    
    print(f"✅ Collect complete. Processed {processed_count} submissions, skipped {skipped_count} rows.")

def run_cleanup(incremental=False):
    """Execute the cleanup command
    
    Args:
        incremental: If True, only process rows with timestamp > last_checked_timestamp
    """
    global last_checked_timestamp
    
    # Group submissions by (actual_username, mabai) for cleanup
    subs = {}
    row_map = {}
    
    if incremental:
        print(f"Reading from row {start_row} to end (incremental mode: timestamp > {last_checked_timestamp})...")
    else:
        print(f"Reading from row {start_row} to end...")
    
    processed_count = 0
    skipped_count = 0
    current_max_timestamp = last_checked_timestamp
    
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
            
            # Convert to UNIX timestamp for comparison
            unix_timestamp = int(time.mktime(dt.timetuple()))
            
            # Skip if incremental mode and timestamp is not newer
            if incremental and unix_timestamp <= last_checked_timestamp:
                skipped_count += 1
                continue
            
            # Track the maximum timestamp seen
            current_max_timestamp = max(current_max_timestamp, unix_timestamp)
            
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

    # Batch update all timestamps at once using a single API call
    if batch_updates:
        print(f"Updating {len(batch_updates)} timestamps in Google Sheets (single API call)...")
        try:
            # Use gspread.Cell for efficient batch updates in one request
            cells = [gspread.Cell(r, c, v) for (r, c, v) in batch_updates]
            sheet.update_cells(cells, value_input_option="USER_ENTERED")
            print("✅ All timestamps updated in one batch")
        except Exception as e:
            print(f"⚠️ Error updating timestamps: {e}")
            # Exponential backoff on error
            time.sleep(random.uniform(1, 3))
            raise
    
    # Update last checked timestamp for incremental mode
    if current_max_timestamp > last_checked_timestamp:
        last_checked_timestamp = current_max_timestamp
        print(f"📊 Updated last checked timestamp to: {last_checked_timestamp}")
    
    print(f"✅ Cleanup complete. Processed {len(subs)} unique (user, problem) combinations.")

# Main execution
if watch_mode:
    # Format interval display
    if watch_interval < 60:
        interval_str = f"{watch_interval}s"
    elif watch_interval < 3600:
        interval_str = f"{watch_interval // 60}m"
    else:
        interval_str = f"{watch_interval // 3600}h"
    
    print(f"🔄 Watch mode enabled. Running {command} every {interval_str}. Press Ctrl+C to stop.")
    print(f"🚀 Using incremental mode for better performance")
    iteration = 1
    
    # First run - full scan
    if command == "collect":
        run_collect(incremental=False)
    elif command == "cleanup":
        run_cleanup(incremental=False)
    
    iteration += 1
    
    while True:
        try:
            print(f"\n{'='*60}")
            print(f"🔄 Watch iteration #{iteration} - {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"{'='*60}\n")
            
            # Check if there are new rows by checking total row count
            current_row_count = len(rows)
            
            # First, quickly check row count to see if anything changed
            try:
                # Get just the first cell to check total rows efficiently
                all_data = sheet.batch_get(["A:A"])
                new_row_count = len(all_data[0]) if all_data and len(all_data) > 0 else 0
                
                if new_row_count > current_row_count:
                    print(f"📥 Detected {new_row_count - current_row_count} new rows")
                    rows = get_sheet_data()
                    print(f"📊 Sheet now has {len(rows)} total rows")
                elif new_row_count < current_row_count:
                    print("📥 Detected row deletion, refreshing data...")
                    rows = get_sheet_data()
                    print(f"📊 Sheet now has {len(rows)} total rows")
                else:
                    # No new rows, check if last row content changed
                    if current_row_count > 0:
                        last_row_data = sheet.batch_get([f"A{current_row_count}:Z{current_row_count}"])
                        if last_row_data and len(last_row_data) > 0 and len(last_row_data[0]) > 0:
                            last_row_new = last_row_data[0][0]
                            last_row_old = rows[-1]
                            # Compare row contents
                            if last_row_new != last_row_old:
                                print("📥 Detected changes in existing rows, fetching latest data...")
                                rows = get_sheet_data()
                                print(f"📊 Sheet now has {len(rows)} total rows")
                            else:
                                print("✓ No changes detected, using incremental mode")
            except Exception as e:
                print(f"⚠️ Error checking for changes: {e}, doing full refresh...")
                time.sleep(random.uniform(1, 3))
                rows = get_sheet_data()
            
            # Run with incremental mode (only process new timestamps)
            if command == "collect":
                run_collect(incremental=True)
            elif command == "cleanup":
                run_cleanup(incremental=True)
            
            print(f"\n⏳ Waiting {interval_str} until next check...")
            time.sleep(watch_interval)
            iteration += 1
        except KeyboardInterrupt:
            print(f"\n\n🛑 Watch mode stopped by user. Total iterations: {iteration}")
            sys.exit(0)
        except Exception as e:
            print(f"\n❌ Error during iteration #{iteration}: {e}")
            print(f"⏳ Retrying in {interval_str} with exponential backoff...")
            time.sleep(random.uniform(1, 3))
            time.sleep(watch_interval)
            iteration += 1
else:
    # Single run
    if command == "collect":
        run_collect()
    elif command == "cleanup":
        run_cleanup()
