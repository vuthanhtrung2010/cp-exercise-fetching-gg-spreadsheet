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
python3 main.py collect
```

You can also mark uncollected submissions to collected without collecting them by
```bash
python3 main.py cleanup
```

Then the student's submissions will be saved in this folder structure:
```
BaiLam/[x][Student ID][Problem ID].ext

While:
- `x` is a random number, from 1 -> 1e9.
- Student ID is the Student ID in the form
- Problem ID is the problem ID. Typically problem code.
- `ext` is the extension mapped to the language the student's chose to submit with. For eg: `C / C++` -> `cpp`, `Python` -> `py`,...
```

Currently the `{ext}` always `c`.

# User file format

The users file is the `users.txt` file.

Example:
```txt
user1:pass1
user2:pass2
user3:pass3
```

Will create following users:
- Username: `user1`, password: `pass1`
- Username: `user2`, password: `pass2`
- Username: `user3`, password: `pass3`