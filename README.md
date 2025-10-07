# CP Exercise Fetching from Google Sheets

A tool to collect programming exercise submissions from Google Sheets.

## Installation

### Option 1: From Source

1. Clone the repository:
```bash
git clone https://github.com/vuthanhtrung2010/cp-exercise-fetching-gg-spreadsheet.git
cd cp-exercise-fetching-gg-spreadsheet
```

2. Create a virtual environment:
```bash
python3 -m venv venv

# Source command is for linux
# On Windows (Command prompt): venv\Scripts\activate
# On Windows (Powershell): venv\Scripts\activate.ps1
source venv/bin/activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

### Option 2: Prebuilt Binaries

Download the latest release from: https://github.com/vuthanhtrung2010/cp-exercise-fetching-gg-spreadsheet/releases

Extract the zip file for your platform and architecture. The executable is standalone but requires `.env` configuration.

## Setup

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

## User Authentication

Create a `users.txt` file with student credentials:

```txt
student1:secretpass123
student2:mypassword456
student3:pass789
```

Format: `username:password` (one per line)

### Password Mapping

If a student enters their **password** instead of their **username** in the Google Form's SBD field, the tool will automatically map it back to their username:

- Form entry: `secretpass123` → Mapped to: `student1`
- Files will be saved with the correct username: `[random][student1][problem].ext`

**Important**: Each password must be unique. The tool will exit with an error if duplicate passwords are detected in `users.txt`.

## Usage

### Collect Submissions

Collect submissions from the Google Sheet:

```bash
python3 main.py collect [--first|--last]
```

**Options:**
- `--last` (default): Collect the **latest submission** for each student per problem
- `--first`: Collect the **earliest submission** for each student per problem

**Examples:**
```bash
python3 main.py collect              # Collects last submission (default)
python3 main.py collect --last       # Same as above
python3 main.py collect --first      # Collects first submission
```

**What it does:**
- Groups submissions by student and problem
- Selects either first or last submission based on timestamp
- Downloads code for submissions with date-format timestamps
- Saves files to `BaiLam/` folder with format: `[random][StudentID][ProblemID].ext`
- Updates timestamps to UNIX format to mark as collected
- Supported languages: C/C++ (.cpp), Python (.py)

### Cleanup Submissions

Mark uncollected submissions as collected without downloading files:

```bash
python3 main.py cleanup [--first|--last]
```

**Options:**
- `--last` (default): Mark the **latest submission** for each student per problem
- `--first`: Mark the **earliest submission** for each student per problem

This will convert selected date-format timestamps to UNIX format, effectively marking them as processed without collecting the code.

## Output Structure

Collected submissions are saved in:
```
BaiLam/[random_number][StudentID][ProblemID].ext
```

Where:
- `random_number`: Random number from 1 to 1e9
- `StudentID`: Student identifier from sheet
- `ProblemID`: Problem/exercise identifier
- `ext`: File extension based on language (cpp, py, etc.)
