import os
import re

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PIPELINES_DIR = os.path.join(BASE_DIR, "pipelines")
CORE_DIR = os.path.join(BASE_DIR, "core")

# Find all python files
py_files = []
for root, _, files in os.walk(BASE_DIR):
    for f in files:
        if f.endswith(".py") and f != "database.py" and f != "refactor.py":
            py_files.append(os.path.join(root, f))

# Pattern to replace reading draft courses
read_draft_pattern = re.compile(
    r'(?:if\s+not\s+os\.path\.exists\(DRAFT_COURSES_FILE\):\s+.*?\s+)?'
    r'with\s+open\(DRAFT_COURSES_FILE,\s*[\'"]r[\'"].*?\)\s+as\s+\w+:\s+'
    r'(\w+)\s*=\s*json\.load\(\w+\)',
    re.DOTALL
)

read_draft_pattern_2 = re.compile(
    r'if\s+os\.path\.exists\(DRAFT_COURSES_FILE\):\s+'
    r'with\s+open\(DRAFT_COURSES_FILE,\s*[\'"]r[\'"].*?\)\s+as\s+\w+:\s+'
    r'(\w+)\s*=\s*json\.load\(\w+\)',
    re.DOTALL
)

# Pattern to replace reading published courses
read_pub_pattern = re.compile(
    r'(?:if\s+not\s+os\.path\.exists\(PUBLISHED_COURSES_FILE\):\s+.*?\s+)?'
    r'with\s+open\(PUBLISHED_COURSES_FILE,\s*[\'"]r[\'"].*?\)\s+as\s+\w+:\s+'
    r'(\w+)\s*=\s*json\.load\(\w+\)',
    re.DOTALL
)

# Pattern to replace atomic write
write_draft_pattern = re.compile(r'atomic_write_json\(DRAFT_COURSES_FILE,\s*([\w]+)\)')
write_pub_pattern = re.compile(r'atomic_write_json\(PUBLISHED_COURSES_FILE,\s*([\w]+)\)')

for path in py_files:
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()

    original = content

    # Replace writes
    content = write_draft_pattern.sub(r'save_all_courses(\1, "draft")', content)
    content = write_pub_pattern.sub(r'save_all_courses(\1, "published")', content)

    # Replace reads
    # This is trickier because of indentation, but we can just replace the whole block
    def read_draft_replacer(match):
        var_name = match.group(1)
        return f"{var_name} = get_all_courses('draft')"
        
    def read_draft_replacer_2(match):
        var_name = match.group(1)
        return f"{var_name} = get_all_courses('draft')"

    def read_pub_replacer(match):
        var_name = match.group(1)
        return f"{var_name} = get_all_courses('published')"

    content = read_draft_pattern.sub(read_draft_replacer, content)
    content = read_draft_pattern_2.sub(read_draft_replacer_2, content)
    content = read_pub_pattern.sub(read_pub_replacer, content)

    if content != original:
        # Add import if needed
        if "from core.database import" not in content:
            imports = "from core.database import get_all_courses, save_all_courses\n"
            content = imports + content
            
        with open(path, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"Refactored {path}")

print("Done refactoring.")
