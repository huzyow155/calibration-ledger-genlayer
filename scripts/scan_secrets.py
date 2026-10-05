import os
import re
import sys

SECRET_PATTERNS = [
    re.compile(r'(?:private_key|privatekey|secret_key|secretkey|privkey|seed_phrase|mnemonic)\s*[:=]\s*["\']?[0-9a-zA-Z\s]{24,128}["\']?', re.I),
    re.compile(r'(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9_]{36}'),
    re.compile(r'-----BEGIN (?:EC|RSA|OPENSSH|DSA|PGP)?\s*PRIVATE KEY-----'),
]

IGNORE_DIRS = {'.git', 'node_modules', '__pycache__', '.venv', 'venv'}

def scan_file(filepath):
    findings = []
    try:
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            for i, line in enumerate(f, 1):
                for pat in SECRET_PATTERNS:
                    if pat.search(line):
                        findings.append((i, line.strip()[:80]))
    except Exception:
        pass
    return findings

def main():
    root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    found_any = False
    for root, dirs, files in os.walk(root_dir):
        dirs[:] = [d for d in dirs if d not in IGNORE_DIRS]
        for f in files:
            path = os.path.join(root, f)
            findings = scan_file(path)
            if findings:
                print(f"POTENTIAL SECRET FOUND in {path}:")
                for line_no, text in findings:
                    print(f"  Line {line_no}: {text}")
                found_any = True
    if found_any:
        print("FAIL: Secrets detected.")
        sys.exit(1)
    else:
        print("PASS: No secrets detected.")
        sys.exit(0)

if __name__ == '__main__':
    main()
