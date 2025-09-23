# Instructions:

In order to use this tool, follow these instructions:

1. Enable Google Sheets API in Google Cloud Console via this link:
https://console.cloud.google.com/marketplace/product/google/sheets.googleapis.com

2. Go to [API > Credentials](https://console.cloud.google.com/apis/credentials) and go to [Manage service accounts](https://console.cloud.google.com/iam-admin/serviceaccounts).

3. Create a service account then manage its keys. Create a new key with type JSON and download it

4. Put the downloaded `.json` file in the root folder of this project and rename it to `service_account.json`

5. Go to your own sheet and then add the read permission to that service account via its email.

6. `.env` configuration:
Copy the `.env.example` file by

```bash
cp .env.example .env
```

And then add your spreadsheet URL and your target sheetname, for eg:

```env
SPREADSHEET_URL="https://docs.google.com/spreadsheets/d/1aHlwSpm0lzV-ShxF6EGiCvgDC-IrgAZLqwSHMkqXYlo/edit?usp=sharing"
SHEETNAME="test01"
```

7. Install deps:

It is recommended to create a virtual environment on python. Then you can run
```bash
pip install -r requirements.txt
```

8. Collect student's submissions

Just run
```bash
python3 main.py
```

Then the student's submissions will be saved in this folder structure:
```
BaiLam/{Student ID}/{Problem ID}.{ext}
```

Currently the `{ext}` always `c`.