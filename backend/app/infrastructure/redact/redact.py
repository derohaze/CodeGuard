import re


BEARER_RE = re.compile(r"(?i)(Bearer\s+)([A-Za-z0-9._-]{12,})")
AWS_KEY_RE = re.compile(r"(?i)(AKIA[0-9A-Z]{16})")
AWS_SECRET_RE = re.compile(r"(?i)((?<![A-Za-z0-9+/=])[A-Za-z0-9+/]{40}(?![A-Za-z0-9+/=]))")
PRIVATE_KEY_RE = re.compile(r"-----BEGIN\s+(?:RSA\s+)?PRIVATE\s+KEY-----")
JWT_RE = re.compile(r"eyJ[A-Za-z0-9_-]+\.eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+")
GENERIC_SECRET_RE = re.compile(r"(?i)((?:api[_-]?key|secret|password|token|credential)\s*[=:]\s*['\"]?)([A-Za-z0-9_.!@#$%^&*()=+-]{8,})")
ENV_VAR_RE = re.compile(r"(?i)((?:API_KEY|SECRET|TOKEN|PASSWORD|CREDENTIAL|SK|KEY)_[A-Z0-9_]{3,})")
GITHUB_TOKEN_RE = re.compile(r"(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9_]{36,}")
SLACK_TOKEN_RE = re.compile(r"xox[baprs]-[A-Za-z0-9-]{10,}")


PATTERNS = [
    (BEARER_RE, lambda m: m.group(1) + "<redacted-bearer>"),
    (AWS_KEY_RE, lambda m: "<redacted-aws-key>"),
    (AWS_SECRET_RE, lambda m: "<redacted-aws-secret>"),
    (PRIVATE_KEY_RE, lambda _m: "<redacted-private-key>"),
    (JWT_RE, lambda _m: "<redacted-jwt>"),
    (GENERIC_SECRET_RE, lambda m: m.group(1) + "<redacted>"),
    (ENV_VAR_RE, lambda _m: "<redacted-env-var>"),
    (GITHUB_TOKEN_RE, lambda _m: "<redacted-github-token>"),
    (SLACK_TOKEN_RE, lambda _m: "<redacted-slack-token>"),
]


def redact_text(text: str) -> str:
    for pattern, replacer in PATTERNS:
        text = pattern.sub(replacer, text)
    return text
