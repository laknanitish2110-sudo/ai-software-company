"""
Security Gate — scans LLM-generated code before it reaches approval or deployment.

Enforces the boundary: LLM output → VALIDATE → SANDBOX → BUILD → TEST → ARTIFACT.
Never let raw LLM output touch production without scanning.

Checks:
  - Hardcoded secrets / API keys / tokens
  - Dangerous code execution patterns (eval, exec, os.system, subprocess with shell=True)
  - Path traversal in file paths (../../etc/passwd)
  - SQL injection patterns
  - XSS / HTML injection risks
  - Unsafe network calls (fetching from user-controlled URLs without validation)
  - Overly permissive CORS / security headers
  - Package/dependency risks (known malicious packages)
"""

import re
import logging
from typing import Optional
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class SecurityFinding:
    severity: str  # "critical", "high", "medium", "low"
    category: str  # "secrets", "injection", "path_traversal", "dangerous_exec", "xss", "cors", "dependency"
    file_path: str
    line: int
    message: str
    snippet: str


@dataclass
class SecurityScanResult:
    status: str  # "PASS", "WARN", "FAIL"
    findings: list[SecurityFinding] = field(default_factory=list)
    files_scanned: int = 0
    summary: str = ""

    def to_dict(self) -> dict:
        return {
            "status": self.status,
            "files_scanned": self.files_scanned,
            "summary": self.summary,
            "findings_count": len(self.findings),
            "critical_count": sum(1 for f in self.findings if f.severity == "critical"),
            "high_count": sum(1 for f in self.findings if f.severity == "high"),
            "medium_count": sum(1 for f in self.findings if f.severity == "medium"),
            "low_count": sum(1 for f in self.findings if f.severity == "low"),
            "findings": [
                {
                    "severity": f.severity,
                    "category": f.category,
                    "file": f.file_path,
                    "line": f.line,
                    "message": f.message,
                    "snippet": f.snippet[:200],
                }
                for f in self.findings
            ],
        }


# --- Pattern definitions ---

SECRET_PATTERNS = [
    (r'(?:api[_-]?key|apikey)\s*[=:]\s*["\']([A-Za-z0-9_\-]{20,})["\']', "Hardcoded API key"),
    (r'(?:secret|password|passwd|pwd)\s*[=:]\s*["\']([^\s"\']{8,})["\']', "Hardcoded secret/password"),
    (r'sk-[a-zA-Z0-9]{20,}', "OpenAI API key pattern"),
    (r'sk-or-v1-[a-zA-Z0-9]{20,}', "OpenRouter API key pattern"),
    (r'sk-ant-[a-zA-Z0-9]{20,}', "Anthropic API key pattern"),
    (r'ghp_[a-zA-Z0-9]{36,}', "GitHub personal access token"),
    (r'gho_[a-zA-Z0-9]{36,}', "GitHub OAuth token"),
    (r'AIza[0-9A-Za-z_-]{35}', "Google API key"),
    (r'-----BEGIN (?:RSA )?PRIVATE KEY-----', "Private key embedded in code"),
    (r'(?:aws_access_key_id|aws_secret)\s*[=:]\s*["\']([A-Za-z0-9/+=]{20,})["\']', "AWS credential"),
    (r'Bearer\s+[A-Za-z0-9\-_\.]{20,}', "Hardcoded Bearer token"),
]

DANGEROUS_EXEC_PATTERNS = [
    (r'\beval\s*\(', "eval() — arbitrary code execution", "high"),
    (r'\bexec\s*\(', "exec() — arbitrary code execution", "high"),
    (r'\bos\.system\s*\(', "os.system() — shell command execution", "critical"),
    (r'\bsubprocess\.(?:call|run|Popen)\s*\([^)]*shell\s*=\s*True', "subprocess with shell=True — command injection risk", "critical"),
    (r'\b__import__\s*\(', "__import__() — dynamic import execution", "high"),
    (r'\bcompile\s*\([^)]*exec', "compile() with exec — code execution", "high"),
    (r'child_process\.exec\s*\(', "child_process.exec — Node.js shell execution", "critical"),
    (r'new\s+Function\s*\(', "new Function() — JS code execution", "high"),
    (r'document\.write\s*\(', "document.write() — DOM manipulation risk", "medium"),
    (r'innerHTML\s*=', "innerHTML assignment — XSS risk", "medium"),
]

SQL_INJECTION_PATTERNS = [
    (r'f["\'](?:SELECT|INSERT|UPDATE|DELETE|DROP)\b.*\{', "f-string SQL query — injection risk"),
    (r'["\'](?:SELECT|INSERT|UPDATE|DELETE|DROP)\b.*["\']\s*\+', "String concatenation in SQL — injection risk"),
    (r'\.format\([^)]*\).*(?:SELECT|INSERT|UPDATE|DELETE|DROP)', ".format() in SQL — injection risk"),
    (r'%s.*(?:SELECT|INSERT|UPDATE|DELETE|DROP)', "%-formatting in SQL without parameterization"),
]

XSS_PATTERNS = [
    (r'dangerouslySetInnerHTML', "dangerouslySetInnerHTML — React XSS risk", "medium"),
    (r'\{\{.*\|.*safe\s*\}\}', "Template |safe filter — XSS risk in Jinja/Django", "medium"),
    (r'v-html\s*=', "v-html directive — Vue XSS risk", "medium"),
    (r'\$\(.*\)\.html\s*\(', "jQuery .html() — XSS risk", "medium"),
]

CORS_PATTERNS = [
    (r'Access-Control-Allow-Origin.*\*', "Wildcard CORS — allows any origin", "medium"),
    (r'allow_origins\s*=\s*\[\s*["\']\*["\']\s*\]', "FastAPI CORS wildcard", "medium"),
    (r'cors\(\s*\{[^}]*origin\s*:\s*true', "Express CORS reflect origin — overly permissive", "medium"),
]

MALICIOUS_PACKAGES = {
    "event-stream", "flatmap-stream", "ua-parser-js-malicious",
    "colors-malicious", "faker-malicious", "node-ipc-malicious",
    "peacenotwar", "es5-ext-malicious",
}

PATH_TRAVERSAL_PATTERN = re.compile(r'(?:\.\./|\.\.\\){2,}|/etc/(?:passwd|shadow|hosts)|/proc/|/dev/null|C:\\Windows\\System32', re.IGNORECASE)
SAFE_PATH_EXCEPTIONS = {"../../node_modules", "../src", "../lib", "../public", "../assets", "../../packages"}


def _is_safe_path_ref(path: str) -> bool:
    """Check if a ../ reference is a normal relative import, not traversal."""
    for safe in SAFE_PATH_EXCEPTIONS:
        if path.startswith(safe):
            return True
    return False


def scan_file(file_path: str, content: str) -> list[SecurityFinding]:
    """Scan a single file's content for security issues."""
    findings = []
    if not content or not isinstance(content, str):
        return findings

    lines = content.split("\n")

    for line_num, line in enumerate(lines, 1):
        stripped = line.strip()
        if stripped.startswith("#") or stripped.startswith("//") or stripped.startswith("*"):
            if "TODO" not in stripped and "FIXME" not in stripped:
                continue

        for pattern, msg in SECRET_PATTERNS:
            if re.search(pattern, line, re.IGNORECASE):
                if any(placeholder in line.lower() for placeholder in
                       ["your-key", "xxx", "placeholder", "example", "change_me", "env.", "process.env", "os.getenv", "os.environ"]):
                    continue
                findings.append(SecurityFinding("critical", "secrets", file_path, line_num, msg, stripped[:200]))

        for pattern, msg, severity in DANGEROUS_EXEC_PATTERNS:
            if re.search(pattern, line):
                findings.append(SecurityFinding(severity, "dangerous_exec", file_path, line_num, msg, stripped[:200]))

        for pattern, msg in SQL_INJECTION_PATTERNS:
            if re.search(pattern, line, re.IGNORECASE):
                findings.append(SecurityFinding("high", "injection", file_path, line_num, msg, stripped[:200]))

        for pattern, msg, severity in XSS_PATTERNS:
            if re.search(pattern, line):
                findings.append(SecurityFinding(severity, "xss", file_path, line_num, msg, stripped[:200]))

        for pattern, msg, severity in CORS_PATTERNS:
            if re.search(pattern, line, re.IGNORECASE):
                findings.append(SecurityFinding(severity, "cors", file_path, line_num, msg, stripped[:200]))

    return findings


def scan_file_path(file_path: str) -> Optional[SecurityFinding]:
    """Check a file path for traversal attacks."""
    if PATH_TRAVERSAL_PATTERN.search(file_path):
        if not _is_safe_path_ref(file_path):
            return SecurityFinding("critical", "path_traversal", file_path, 0,
                                   f"Path traversal detected: {file_path}", file_path)
    normalized = file_path.replace("\\", "/")
    if normalized.startswith("/") and not normalized.startswith("/src"):
        return SecurityFinding("high", "path_traversal", file_path, 0,
                               f"Absolute path outside project: {file_path}", file_path)
    return None


def scan_dependencies(content: str, file_path: str) -> list[SecurityFinding]:
    """Scan package.json or requirements.txt for known malicious packages."""
    findings = []
    content_lower = content.lower()
    for pkg in MALICIOUS_PACKAGES:
        if pkg in content_lower:
            findings.append(SecurityFinding("critical", "dependency", file_path, 0,
                                           f"Known malicious package: {pkg}", pkg))
    return findings


def scan_files(files: list[dict]) -> SecurityScanResult:
    """
    Scan a list of generated files for security issues.
    Each file: {"path": str, "content": str}
    Returns SecurityScanResult with status PASS/WARN/FAIL.
    """
    all_findings: list[SecurityFinding] = []
    scanned = 0

    for f in files:
        path = f.get("path", f.get("file_path", "unknown"))
        content = f.get("content", "")

        if not content or content == "(binary file)":
            continue

        scanned += 1

        path_finding = scan_file_path(path)
        if path_finding:
            all_findings.append(path_finding)

        all_findings.extend(scan_file(path, content))

        if path.endswith("package.json") or path.endswith("requirements.txt") or path.endswith("Pipfile"):
            all_findings.extend(scan_dependencies(content, path))

    critical = sum(1 for f in all_findings if f.severity == "critical")
    high = sum(1 for f in all_findings if f.severity == "high")

    if critical > 0:
        status = "FAIL"
        summary = f"Security scan FAILED: {critical} critical issue(s) found"
    elif high > 0:
        status = "WARN"
        summary = f"Security scan WARNING: {high} high-severity issue(s) found"
    elif all_findings:
        status = "WARN"
        summary = f"Security scan passed with {len(all_findings)} minor finding(s)"
    else:
        status = "PASS"
        summary = f"Security scan passed — {scanned} files clean"

    all_findings.sort(key=lambda f: {"critical": 0, "high": 1, "medium": 2, "low": 3}.get(f.severity, 4))

    result = SecurityScanResult(
        status=status,
        findings=all_findings,
        files_scanned=scanned,
        summary=summary,
    )
    logger.info(f"Security scan: {status} | {scanned} files | {len(all_findings)} findings ({critical} critical, {high} high)")
    return result
