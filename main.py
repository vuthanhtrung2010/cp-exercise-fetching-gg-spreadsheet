import gspread
from google.oauth2.service_account import Credentials
import os
from dotenv import load_dotenv

load_dotenv()
SPREADSHEET_URL = os.getenv("SPREADSHEET_URL")
if not SPREADSHEET_URL:
    raise ValueError("Missing SPREADSHEET_URL in environment variables")

SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly"]
creds = Credentials.from_service_account_file("service_account.json", scopes=SCOPES)
client = gspread.authorize(creds)

sheet = client.open_by_url(SPREADSHEET_URL).sheet1
rows = sheet.get_all_values()

header = rows[0]
idx_sbd = header.index("Số báo danh")
idx_lang = header.index("Ngôn ngữ")
idx_mabai = header.index("Mã bài")
idx_code = header.index("Code")

for row in rows[1:]:
    sbd = row[idx_sbd]
    lang = row[idx_lang].lower()
    mabai = row[idx_mabai]
    code = row[idx_code]

    ext_map = {"c++": "cpp", "cpp": "cpp", "python": "py"}
    ext = ext_map.get(lang, lang)

    folder = os.path.join("BaiLam", sbd)
    os.makedirs(folder, exist_ok=True)

    filename = f"{mabai}.{ext}"
    filepath = os.path.join(folder, filename)

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(code)

    print(f"✅ Saved {filepath}")
