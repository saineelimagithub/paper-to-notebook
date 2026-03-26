"""
Notebook Scanner — inspects generated code cells for suspicious patterns
before delivering the notebook to the user.
"""
from __future__ import annotations

import re

# Each rule: (compiled_regex, severity, description)
_RULES: list[tuple[re.Pattern, str, str, str]] = [
    # (pattern, pattern_name, severity, description)
    (
        re.compile(r"\bos\.system\s*\("),
        "os.system",
        "critical",
        "Arbitrary shell command execution via os.system()",
    ),
    (
        re.compile(r"\bsubprocess\.\w+\s*\("),
        "subprocess",
        "critical",
        "Shell command execution via subprocess module",
    ),
    (
        re.compile(r"\bPopen\s*\("),
        "subprocess.Popen",
        "critical",
        "Shell command execution via Popen",
    ),
    (
        re.compile(r"(?<!\w)eval\s*\("),
        "eval",
        "critical",
        "Arbitrary code execution via eval()",
    ),
    (
        re.compile(r"(?<!\w)exec\s*\("),
        "exec",
        "critical",
        "Arbitrary code execution via exec()",
    ),
    (
        re.compile(r"\b__import__\s*\("),
        "__import__",
        "warning",
        "Dynamic module import via __import__()",
    ),
    (
        re.compile(r"\bopen\s*\([^)]*(?:/etc/|\.env|\.ssh|~/|\\etc\\)"),
        "open (sensitive path)",
        "critical",
        "File access targeting sensitive paths (/etc/, .env, .ssh)",
    ),
    (
        re.compile(r"\brequests\.(?:get|post|put|delete|patch)\s*\("),
        "requests.get/post",
        "warning",
        "HTTP request to external URL via requests library",
    ),
    (
        re.compile(r"\burllib\.request\.urlopen\s*\("),
        "urllib.request",
        "warning",
        "HTTP request via urllib",
    ),
    (
        re.compile(r"\.connect\s*\(\s*\("),
        "socket.connect",
        "critical",
        "Raw socket connection to remote host",
    ),
    (
        re.compile(r"\bshutil\.rmtree\s*\("),
        "shutil.rmtree",
        "critical",
        "Recursive directory deletion via shutil.rmtree()",
    ),
    (
        re.compile(r"\bos\.remove\s*\("),
        "os.remove",
        "warning",
        "File deletion via os.remove()",
    ),
]


def scan_notebook(cells: list[dict]) -> list[dict]:
    """
    Scan code cells for suspicious patterns.

    Args:
        cells: List of {"type": "markdown"|"code", "source": str}

    Returns:
        List of findings, each:
        {
            "cell_index": int,
            "line": int,
            "pattern": str,
            "severity": "critical" | "warning",
            "description": str,
        }
        Empty list if clean.
    """
    findings: list[dict] = []

    for cell_idx, cell in enumerate(cells):
        if cell.get("type") != "code":
            continue

        source = cell.get("source", "")
        lines = source.split("\n")

        for line_idx, line in enumerate(lines, start=1):
            for regex, pattern_name, severity, description in _RULES:
                if regex.search(line):
                    findings.append({
                        "cell_index": cell_idx,
                        "line": line_idx,
                        "pattern": pattern_name,
                        "severity": severity,
                        "description": description,
                    })

    return findings
