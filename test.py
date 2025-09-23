import re

# Example headers
header = ["Số báo danh (Ví dụ: B56)", "Extension", "Mã bài sth", "Source Code (ko có chữ cái tiếng Việt, kể cả comments)", "Mật khẩu"]

# Function to find column index using regex
def find_col_index(header, pattern):
    for i, col in enumerate(header):
        if re.search(pattern, col, re.IGNORECASE):
            return i
    raise ValueError(f"No column matching pattern '{pattern}' found.")

# Define patterns for each column
idx_sbd = find_col_index(header, r"\b(số báo danh|sbd)\b")
idx_lang = find_col_index(header, r"\b(ngôn ngữ|ext\w*)\b")
idx_password = find_col_index(header, r"\b(pass\w*|mật\w*)\b")

idx_mabai = find_col_index(header, r"mã bài")
idx_code = find_col_index(header, r"\bcode\b")

print("SBD index:", idx_sbd)
print("Language index:", idx_lang)
print("Mã bài index:", idx_mabai)
print("Code index:", idx_code)
print("Password index:", idx_password)