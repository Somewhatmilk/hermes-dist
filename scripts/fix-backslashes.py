#!/usr/bin/env python3
"""Fix double-backslashes in denylist.yaml so they read as single \\\\ in grep."""
import sys
from pathlib import Path

path = Path(sys.argv[1])
content = path.read_text(encoding='utf-8')
# Replace \\\\ with \\ (i.e. in the file, replace 2-char "\\" with 1-char "\")
fixed = content.replace('\\\\', '\\')
path.write_text(fixed, encoding='utf-8')
print(f"Fixed: {path}")
print(f"Size: {len(content)} -> {len(fixed)} bytes")
