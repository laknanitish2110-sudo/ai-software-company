import os
from dotenv import load_dotenv

load_dotenv()

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "").strip()
OPENROUTER_API_KEY_2 = os.getenv("OPENROUTER_API_KEY_2", "").strip()
OPENROUTER_API_KEY_3 = os.getenv("OPENROUTER_API_KEY_3", "").strip()
OPENROUTER_API_KEY_4 = os.getenv("OPENROUTER_API_KEY_4", "").strip()
OPENROUTER_API_KEY_5 = os.getenv("OPENROUTER_API_KEY_5", "").strip()
OPENROUTER_API_KEY_6 = os.getenv("OPENROUTER_API_KEY_6", "").strip()
OPENROUTER_BASE_URL = os.getenv("LLM_BASE_URL", "https://openrouter.ai/api/v1").strip()

OPENROUTER_KEYS = [k for k in [OPENROUTER_API_KEY, OPENROUTER_API_KEY_2, OPENROUTER_API_KEY_3, OPENROUTER_API_KEY_4, OPENROUTER_API_KEY_5, OPENROUTER_API_KEY_6] if k]
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
OPENAI_BASE_URL = "https://api.openai.com/v1"
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", "").strip()
N8N_WEBHOOK_URL = os.getenv("N8N_WEBHOOK_URL", "").strip()
DATABASE_PATH = os.getenv("DATABASE_PATH", "company.db")
DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
REDIS_URL = os.getenv("REDIS_URL", "").strip()
TASK_WORKER_ENGINE = os.getenv("TASK_WORKER_ENGINE", "in_process").strip().lower()
SMART_MODEL = os.getenv("SMART_MODEL", "openrouter/free")
FALLBACK_MODEL = os.getenv("FALLBACK_MODEL", "openrouter/free")

DEFAULT_DEV_JWT_SECRET = "dev_secret_jwt_key_change_in_production_998877"
KNOWN_INSECURE_SECRETS = {
    DEFAULT_DEV_JWT_SECRET,
    "secret",
    "jwt_secret",
    "change_me",
    "password",
    "123456",
    "dev_secret_jwt_key",
}

JWT_ALGORITHM = "HS256"
JWT_EXPIRATION_HOURS = 24

def get_environment() -> str:
    return os.getenv("ENVIRONMENT", "production").strip().lower()

def get_sandbox_mode() -> str:
    return os.getenv("SANDBOX_MODE", "e2b_required").strip().lower()

ENVIRONMENT = get_environment()
SANDBOX_MODE = get_sandbox_mode()

def get_jwt_secret(env: str | None = None, secret_override: str | None = None) -> str:
    curr_env = (env if env is not None else get_environment()).strip().lower()
    raw_secret = (secret_override if secret_override is not None else os.getenv("JWT_SECRET", "")).strip()

    if curr_env == "production":
        if not raw_secret:
            raise ValueError("Security Violation: JWT_SECRET is required in production and must be a cryptographically strong secret.")
        if raw_secret in KNOWN_INSECURE_SECRETS or len(raw_secret) < 16:
            raise ValueError("Security Violation: JWT_SECRET is set to an insecure or short key. A cryptographically strong secret (minimum 16 characters) is required in production.")
        return raw_secret
    else:
        return raw_secret or DEFAULT_DEV_JWT_SECRET

def validate_jwt_config(env: str | None = None, secret: str | None = None):
    get_jwt_secret(env, secret)

if get_environment() == "production":
    JWT_SECRET = get_jwt_secret()
else:
    try:
        JWT_SECRET = get_jwt_secret()
    except ValueError:
        JWT_SECRET = DEFAULT_DEV_JWT_SECRET

VALID_SANDBOX_MODES = ("e2b_required", "local_dev")

def validate_sandbox_config(env: str | None = None, mode: str | None = None):
    curr_env = (env if env is not None else get_environment()).strip().lower()
    curr_mode = (mode if mode is not None else get_sandbox_mode()).strip().lower()

    if curr_mode not in VALID_SANDBOX_MODES:
        raise ValueError(f"Invalid SANDBOX_MODE: '{curr_mode}'. Must be one of {VALID_SANDBOX_MODES}.")

    if curr_env == "production" and curr_mode == "local_dev":
        raise ValueError("Security Violation: SANDBOX_MODE='local_dev' is strictly forbidden in production environment.")

# Rate Limiting & Resource Budget Config (P4.4)
MAX_PROJECTS_PER_WINDOW = int(os.getenv("MAX_PROJECTS_PER_WINDOW", "10"))
MAX_PROJECT_RUNS_PER_WINDOW = int(os.getenv("MAX_PROJECT_RUNS_PER_WINDOW", "20"))
RATE_LIMIT_WINDOW_SECONDS = int(os.getenv("RATE_LIMIT_WINDOW_SECONDS", "3600"))

MAX_LLM_CALLS_PER_PROJECT = int(os.getenv("MAX_LLM_CALLS_PER_PROJECT", "50"))
MAX_E2B_EXECUTIONS_PER_PROJECT = int(os.getenv("MAX_E2B_EXECUTIONS_PER_PROJECT", "10"))
MAX_REPAIR_ATTEMPTS_HARD_LIMIT = 3

# Per-agent provider + model routing
# Provider: "openrouter" | "openai" | "gemini"
# Route everything through OpenRouter — it proxies all models reliably.
# OpenAI direct only for engineer when key is available.

def _or(n: int) -> str:
    """Return provider name for OpenRouter key N (1-6), falling back to 'openrouter'."""
    if n <= 1 or len(OPENROUTER_KEYS) < n:
        return "openrouter"
    return f"openrouter{n}"

# 6 keys = 1 dedicated key per agent, zero sharing
# Key 1: CEO           | Key 2: BA            | Key 3: Researcher
# Key 4: Architect     | Key 5: Engineer fb   | Key 6: PPT
# Cross-reviews rotate through keys not currently in use
PROVIDER_MAP = {
    "ceo": os.getenv("PROVIDER_CEO", _or(1)),
    "business_analyst": os.getenv("PROVIDER_BA", _or(2)),
    "researcher": os.getenv("PROVIDER_RESEARCHER", _or(3)),
    "architect": os.getenv("PROVIDER_ARCHITECT", _or(4)),
    "engineer": os.getenv("PROVIDER_ENGINEER", "openai" if OPENAI_API_KEY else _or(5)),
    "ppt": os.getenv("PROVIDER_PPT", _or(6)),
    "cross_review": os.getenv("PROVIDER_REVIEW", _or(5)),
    "fixer": os.getenv("PROVIDER_FIXER", "openai" if OPENAI_API_KEY else _or(5)),
}

MODEL_MAP = {
    "ceo": os.getenv("MODEL_CEO", "openrouter/free"),
    "business_analyst": os.getenv("MODEL_BA", SMART_MODEL),
    "researcher": os.getenv("MODEL_RESEARCHER", "openrouter/free"),
    "architect": os.getenv("MODEL_ARCHITECT", SMART_MODEL),
    "engineer": os.getenv("MODEL_ENGINEER", "gpt-4o" if OPENAI_API_KEY else SMART_MODEL),
    "ppt": os.getenv("MODEL_PPT", "openrouter/free"),
    "cross_review": os.getenv("MODEL_REVIEW", "openrouter/free"),
    "fixer": os.getenv("MODEL_FIXER", "gpt-4o" if OPENAI_API_KEY else SMART_MODEL),
}

FALLBACK_MAP = {
    "ceo": os.getenv("FALLBACK_CEO", FALLBACK_MODEL),
    "business_analyst": os.getenv("FALLBACK_BA", FALLBACK_MODEL),
    "researcher": os.getenv("FALLBACK_RESEARCHER", FALLBACK_MODEL),
    "architect": os.getenv("FALLBACK_ARCHITECT", FALLBACK_MODEL),
    "engineer": os.getenv("FALLBACK_ENGINEER", SMART_MODEL),
    "ppt": os.getenv("FALLBACK_PPT", FALLBACK_MODEL),
    "cross_review": os.getenv("FALLBACK_REVIEW", FALLBACK_MODEL),
    "fixer": os.getenv("FALLBACK_FIXER", SMART_MODEL),
}

# Fallback provider: each agent falls back to a DIFFERENT dedicated key
FALLBACK_PROVIDER_MAP = {
    "ceo": _or(6),
    "business_analyst": _or(5),
    "researcher": _or(4),
    "architect": _or(3),
    "engineer": _or(6),
    "ppt": _or(1),
    "cross_review": _or(2),
    "fixer": _or(4),
}

import logging as _logging
_logging.getLogger(__name__).info(f"OpenRouter keys loaded: {len(OPENROUTER_KEYS)}/6 | OpenAI: {'yes' if OPENAI_API_KEY else 'no'}")
