import os
import re
import sys

# Comprehensive banned words list per GenLayer Studionet project rules:
# - 'cryptographic proof'
# - 'tamper-proof' / 'tamperproof'
# - 'bytecode'
# - 'finalized' (unless actual status_name literally equals FINALIZED)
# - 'testnet'
# - 'Live' / 'live' (say 'studionet' / 'Preview')
# - 'unanimous' / 'unanimously'
# - 'revolutionary'

BANNED_PATTERNS = [
    (r'\bcryptographic\s+proof\b', 'cryptographic proof'),
    (r'\btamper-?proof\b', 'tamper-proof'),
    (r'\bbytecode\b', 'bytecode'),
    (r'\btestnet\b', 'testnet'),
    (r'\bunanimous(ly)?\b', 'unanimous'),
    (r'\blive\b', 'live'),
    (r'\bfinalized\b', 'finalized'),
    (r'\brevolutionary\b', 'revolutionary'),
]

IGNORE_DIRS = {'.git', 'node_modules', 'dist', '__pycache__', '.vercel'}
ALLOWED_FILES = {'scan_banned_words.py', 'tx_raw.json'}

def scan():
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    violations = []
    
    for r, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d not in IGNORE_DIRS]
        for f in files:
            if f in ALLOWED_FILES:
                continue
            if not f.endswith(('.ts', '.tsx', '.js', '.jsx', '.json', '.md', '.html', '.py', '.css', '.mjs')):
                continue
            path = os.path.join(r, f)
            rel_path = os.path.relpath(path, root).replace('\\', '/')
            
            with open(path, 'r', encoding='utf-8', errors='ignore') as fp:
                for line_idx, line in enumerate(fp, 1):
                    for pat, name in BANNED_PATTERNS:
                        # Allowed check for literal status code check: e.g. status_name === 'FINALIZED'
                        if name == 'finalized' and ("=== 'FINALIZED'" in line or '=== "FINALIZED"' in line or "=== `FINALIZED`" in line or "'FINALIZED'" in line or '"FINALIZED"' in line):
                            continue
                        # Allow live in filenames like run_live_evidence.js or live_evidence.json if inside scripts/
                        if name == 'live' and ('live_evidence' in line or 'run_live' in line):
                            continue
                        
                        m = re.search(pat, line, re.IGNORECASE)
                        if m:
                            violations.append((rel_path, line_idx, m.group(0), line.strip()))
    
    if violations:
        print(f"FAILED: Found {len(violations)} banned word violations:")
        for path, line_no, matched, text in violations:
            print(f"  {path}:{line_no} [{matched}] -> {text[:100]}")
        sys.exit(1)
    else:
        print("PASSED: Zero banned words detected across codebase and docs.")
        sys.exit(0)

if __name__ == '__main__':
    scan()
