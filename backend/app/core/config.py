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
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "").strip()
ANTHROPIC_BASE_URL = "https://api.anthropic.com/v1/"
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", "").strip()
N8N_WEBHOOK_URL = os.getenv("N8N_WEBHOOK_URL", "").strip()
DATABASE_PATH = os.getenv("DATABASE_PATH", "company.db")
DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
REDIS_URL = os.getenv("REDIS_URL", "").strip()
TASK_WORKER_ENGINE = os.getenv("TASK_WORKER_ENGINE", "in_process").strip().lower()
SMART_MODEL = os.getenv("SMART_MODEL", "deepseek/deepseek-chat-v3-0324:free")
FALLBACK_MODEL = os.getenv("FALLBACK_MODEL", "nvidia/nemotron-3.5-lightning:free")

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

# OAuth Provider Config
GITHUB_CLIENT_ID = os.getenv("GITHUB_CLIENT_ID", "").strip()
GITHUB_CLIENT_SECRET = os.getenv("GITHUB_CLIENT_SECRET", "").strip()
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "").strip()
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "").strip()
OAUTH_FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000").strip().rstrip("/")
OAUTH_BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000").strip().rstrip("/")

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

# ── Specialized model defaults per agent ──────────────────────────────
# Best FREE models for each job — specialized via OpenRouter free tier.
# DeepSeek V3 for reasoning/coding, Nemotron 120B for analysis, Lightning for speed.
# When provider-specific keys are available, agents can use them directly.

def _best_provider(preferred: str, role_idx: int) -> str:
    """Pick the best available provider for an agent."""
    if preferred == "openai" and OPENAI_API_KEY:
        return "openai"
    if preferred == "anthropic" and ANTHROPIC_API_KEY:
        return "anthropic"
    if preferred == "gemini" and GEMINI_API_KEY:
        return "gemini"
    return _or(role_idx)

# 6 OR keys = 1 dedicated key per agent, zero sharing
# Key 1: CEO  |  Key 2: BA  |  Key 3: Researcher
# Key 4: Architect  |  Key 5: Engineer fb  |  Key 6: PPT
PROVIDER_MAP = {
    "ceo":              os.getenv("PROVIDER_CEO",        _or(1)),
    "business_analyst": os.getenv("PROVIDER_BA",         _or(2)),
    "researcher":       os.getenv("PROVIDER_RESEARCHER", _or(3)),
    "architect":        os.getenv("PROVIDER_ARCHITECT",  _or(4)),
    "engineer":         os.getenv("PROVIDER_ENGINEER",   _or(5)),
    "ppt":              os.getenv("PROVIDER_PPT",        _or(6)),
    "cross_review":     os.getenv("PROVIDER_REVIEW",     _or(5)),
    "fixer":            os.getenv("PROVIDER_FIXER",      _or(5)),
}

# Best free models per role — all OpenRouter free tier
# DeepSeek V3: best free model for reasoning + coding (671B MoE)
# Nemotron 120B: strong analysis, large param count
# Nemotron Lightning: fast, good for simple generation tasks
MODEL_MAP = {
    "ceo":              os.getenv("MODEL_CEO",        "deepseek/deepseek-chat-v3-0324:free"),
    "business_analyst": os.getenv("MODEL_BA",         "nvidia/nemotron-3-super-120b-a12b:free"),
    "researcher":       os.getenv("MODEL_RESEARCHER", "nvidia/nemotron-3-super-120b-a12b:free"),
    "architect":        os.getenv("MODEL_ARCHITECT",  "deepseek/deepseek-chat-v3-0324:free"),
    "engineer":         os.getenv("MODEL_ENGINEER",   "deepseek/deepseek-chat-v3-0324:free"),
    "ppt":              os.getenv("MODEL_PPT",        "nvidia/nemotron-3.5-lightning:free"),
    "cross_review":     os.getenv("MODEL_REVIEW",     "nvidia/nemotron-3-super-120b-a12b:free"),
    "fixer":            os.getenv("MODEL_FIXER",      "deepseek/deepseek-chat-v3-0324:free"),
}

FALLBACK_MAP = {
    "ceo":              os.getenv("FALLBACK_CEO",        FALLBACK_MODEL),
    "business_analyst": os.getenv("FALLBACK_BA",         FALLBACK_MODEL),
    "researcher":       os.getenv("FALLBACK_RESEARCHER",  FALLBACK_MODEL),
    "architect":        os.getenv("FALLBACK_ARCHITECT",   FALLBACK_MODEL),
    "engineer":         os.getenv("FALLBACK_ENGINEER",    SMART_MODEL),
    "ppt":              os.getenv("FALLBACK_PPT",         FALLBACK_MODEL),
    "cross_review":     os.getenv("FALLBACK_REVIEW",      FALLBACK_MODEL),
    "fixer":            os.getenv("FALLBACK_FIXER",       SMART_MODEL),
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

# ── Model metadata for frontend display ──────────────────────────────
def _model_display(model_id: str) -> dict:
    """Extract human-readable label and provider from a model identifier."""
    m = model_id.lower()
    if "gpt-4.1" in m or "gpt-5" in m or "gpt-4o" in m or "codex" in m:
        label = model_id.split("/")[-1] if "/" in model_id else model_id
        return {"model": label.upper(), "provider": "OpenAI", "providerColor": "#10a37f"}
    if "claude" in m:
        label = model_id.split("/")[-1] if "/" in model_id else model_id
        return {"model": label.replace("anthropic/", "").title(), "provider": "Anthropic", "providerColor": "#d4a27f"}
    if "gemini" in m or "gemma" in m:
        label = model_id.split("/")[-1] if "/" in model_id else model_id
        return {"model": label.title(), "provider": "Google", "providerColor": "#4285f4"}
    if "nemotron" in m or "nvidia" in m:
        label = model_id.split("/")[-1] if "/" in model_id else model_id
        return {"model": label.split(":")[0].title(), "provider": "Nvidia", "providerColor": "#76b900"}
    if "deepseek" in m:
        label = model_id.split("/")[-1] if "/" in model_id else model_id
        return {"model": label.split(":")[0].title(), "provider": "DeepSeek", "providerColor": "#5b7ee5"}
    if "cohere" in m or "north" in m:
        label = model_id.split("/")[-1] if "/" in model_id else model_id
        return {"model": label.split(":")[0].title(), "provider": "Cohere", "providerColor": "#d18ee2"}
    if "openrouter/free" in m:
        return {"model": "Auto (Free)", "provider": "OpenRouter", "providerColor": "#6366f1"}
    return {"model": model_id.split("/")[-1] if "/" in model_id else model_id, "provider": "OpenRouter", "providerColor": "#6366f1"}

MODEL_INFO = {role: _model_display(model) for role, model in MODEL_MAP.items()}

# ── Cost Governor: per-model pricing ($ per 1M tokens) ──────────────
# Free-tier models have zero cost; pricing here for budget tracking
# and future paid-model support. Input/output split where available.
MODEL_PRICING: dict[str, dict[str, float]] = {
    # Free models — $0
    "deepseek/deepseek-chat-v3-0324:free":        {"input": 0.0, "output": 0.0},
    "nvidia/nemotron-3-super-120b-a12b:free":     {"input": 0.0, "output": 0.0},
    "nvidia/nemotron-3.5-lightning:free":          {"input": 0.0, "output": 0.0},
    # Paid models (if keys ever added) — per-1M-token pricing
    "deepseek/deepseek-chat-v3-0324":             {"input": 0.27, "output": 1.10},
    "openai/gpt-4.1":                             {"input": 2.00, "output": 8.00},
    "openai/gpt-4o":                              {"input": 2.50, "output": 10.00},
    "anthropic/claude-sonnet-4":                   {"input": 3.00, "output": 15.00},
    "google/gemini-2.5-pro":                      {"input": 1.25, "output": 10.00},
    "google/gemini-2.5-flash":                    {"input": 0.15, "output": 0.60},
}

# Token budget per project (0 = unlimited, which is default for free tier)
MAX_TOKENS_PER_PROJECT = int(os.getenv("MAX_TOKENS_PER_PROJECT", "500000"))
MAX_COST_PER_PROJECT = float(os.getenv("MAX_COST_PER_PROJECT", "0.0"))

def estimate_cost(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    """Estimate cost in dollars for a single LLM call."""
    pricing = MODEL_PRICING.get(model)
    if not pricing:
        for key, val in MODEL_PRICING.items():
            if key.split("/")[-1].split(":")[0] in model:
                pricing = val
                break
    if not pricing:
        pricing = {"input": 0.0, "output": 0.0}
    return (prompt_tokens * pricing["input"] + completion_tokens * pricing["output"]) / 1_000_000

import logging as _logging
_logging.getLogger(__name__).info(
    f"Model router: OpenRouter keys={len(OPENROUTER_KEYS)}/6 | "
    f"OpenAI={'yes' if OPENAI_API_KEY else 'no'} | "
    f"Anthropic={'yes' if ANTHROPIC_API_KEY else 'no'} | "
    f"Gemini={'yes' if GEMINI_API_KEY else 'no'}"
)
