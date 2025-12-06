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
python3 main.py collect [--first|--last] [--row=N] [--watch[=interval]] [--contest-id=ID]
```

**Options:**
- `--last` (default): Collect the **latest submission** for each student per problem
- `--first`: Collect the **earliest submission** for each student per problem
- `--row=N`: Start reading from row N (must be >= 2, default is 2)
- `--watch[=interval]`: Enable watch mode with custom interval (default: 5s)
  - Supports: `5s` (seconds), `5m` (minutes), `1h` (hours)
  - Can use `--watch=5m` or `--watch 5m` syntax
- `--contest-id=ID`: Custom contest/exam ID for file naming (default: random number)

**Examples:**
```bash
python3 main.py collect              # Collects last submission from row 2 onwards
python3 main.py collect --last       # Same as above
python3 main.py collect --first      # Collects first submission from row 2 onwards
python3 main.py collect --row=10     # Collects from row 10 to end (skips rows 2-9)
python3 main.py collect --first --row=5  # Collects first submission from row 5 onwards
python3 main.py collect --watch      # Runs continuously, checking every 5 seconds (default)
python3 main.py collect --watch=5m   # Watch mode with 5-minute interval
python3 main.py collect --watch 10m  # Alternative syntax for 10-minute interval
python3 main.py collect --watch=1h   # Watch mode with 1-hour interval
python3 main.py collect --contest-id=EXAM2024  # Use custom contest ID instead of random number
```

**What it does:**
- Processes ALL submissions individually (no grouping)
- Downloads code for submissions with date-format timestamps
- Saves files to `BaiLam/` folder with format: `[ID][StudentID][ProblemID].ext`
  - ID is either the custom `--contest-id` or a random number (1 to 1,000,000,000)
- Updates timestamps to UNIX format to mark as collected
- Supported languages: C/C++ (.cpp), Python (.py)

### Cleanup Submissions

Mark uncollected submissions as collected without downloading files:

```bash
python3 main.py cleanup [--first|--last] [--row=N] [--watch[=interval]]
```

**Options:**
- `--last` (default): Mark the **latest submission** for each student per problem
- `--first`: Mark the **earliest submission** for each student per problem
- `--row=N`: Start processing from row N (must be >= 2, default is 2)
- `--watch[=interval]`: Enable watch mode with custom interval (default: 5s)

**Examples:**
```bash
python3 main.py cleanup              # Mark last submission from row 2 onwards
python3 main.py cleanup --row=20     # Mark submissions from row 20 to end
python3 main.py cleanup --watch      # Runs continuously, checking every 5 seconds
python3 main.py cleanup --watch=5m   # Watch mode with 5-minute interval
```

**What it does:**
- Groups submissions by student and problem
- Selects either first or last submission based on timestamp
- Converts selected date-format timestamps to UNIX format
- Effectively marks them as processed without collecting the code

### Watch Mode

Both `collect` and `cleanup` commands support watch mode with customizable intervals:

```bash
python3 main.py collect --watch              # Default: 5 seconds
python3 main.py collect --watch=5m           # 5 minutes
python3 main.py collect --watch 10m          # 10 minutes (alternative syntax)
python3 main.py cleanup --watch=1h           # 1 hour
```

**Watch mode features:**
- **Default interval**: 5 seconds (if no interval specified)
- **Custom intervals**: Supports seconds (`5s`), minutes (`5m`), hours (`1h`)
- **Two syntax styles**: `--watch=5m` or `--watch 5m` (both work)
- **Incremental processing**: Only processes new submissions (timestamp-based)
- **Smart data fetching**: Uses batch API for faster reads
- **Change detection**: Checks last row for changes before full refresh
- **Error resilience**: Exponential backoff on API errors
- Displays iteration number and timestamp for each run
- Press **Ctrl+C** to stop gracefully
- Combines with other options: `--first`, `--last`, `--row=N`

**Performance optimizations:**
- First iteration does a full scan to establish baseline
- Subsequent iterations only process rows with timestamps newer than last check
- **Single batch update**: All timestamp updates in ONE API call (prevents rate limiting)
- Batch read API (`batch_get`) is significantly faster than `get_all_values()`
- Automatic retry with exponential backoff on transient errors
- Incremental change detection reduces unnecessary data transfers
- **No API flooding**: Updates 300 rows = 1 request (not 300 requests)

**Use cases:**
- **Quick testing**: Use default 5s for rapid development feedback
- **Active monitoring**: Use 1-5 minutes during exams or contests
- **Background sync**: Use 30m-1h for periodic updates without manual intervention

## Output Structure

Collected submissions are saved in:
```
BaiLam/[ID][StudentID][ProblemID].ext
```

Where:
- `ID`: Contest/exam ID (custom via `--contest-id` or random number 1 to 1,000,000,000)
- `StudentID`: Student identifier from sheet
- `ProblemID`: Problem/exercise identifier (uppercase)
- `ext`: File extension based on language (cpp, py, etc.)

**Examples:**
- With `--contest-id=FINAL2024`: `BaiLam/[FINAL2024][student1][KNIGHTGAME].cpp`
- Without contest ID: `BaiLam/[748392156][student1][KNIGHTGAME].cpp`
