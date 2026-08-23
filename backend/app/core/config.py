import os
from dotenv import load_dotenv

load_dotenv()

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "").strip()
OPENROUTER_API_KEY_2 = os.getenv("OPENROUTER_API_KEY_2", "").strip()
OPENROUTER_API_KEY_3 = os.getenv("OPENROUTER_API_KEY_3", "").strip()
OPENROUTER_API_KEY_4 = os.getenv("OPENROUTER_API_KEY_4", "").strip()
OPENROUTER_BASE_URL = os.getenv("LLM_BASE_URL", "https://openrouter.ai/api/v1").strip()

OPENROUTER_KEYS = [k for k in [OPENROUTER_API_KEY, OPENROUTER_API_KEY_2, OPENROUTER_API_KEY_3, OPENROUTER_API_KEY_4] if k]
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
OPENAI_BASE_URL = "https://api.openai.com/v1"
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", "").strip()
N8N_WEBHOOK_URL = os.getenv("N8N_WEBHOOK_URL", "").strip()
DATABASE_PATH = os.getenv("DATABASE_PATH", "company.db")
SMART_MODEL = os.getenv("SMART_MODEL", "anthropic/claude-sonnet-4")
FALLBACK_MODEL = os.getenv("FALLBACK_MODEL", "google/gemini-2.5-flash")

# Per-agent provider + model routing
# Provider: "openrouter" | "openai" | "gemini"
# Route everything through OpenRouter — it proxies all models reliably.
# OpenAI direct only for engineer when key is available.

def _or(n: int) -> str:
    """Return provider name for OpenRouter key N (1-4), falling back to 'openrouter'."""
    if n == 1 or not OPENROUTER_KEYS[min(n - 1, len(OPENROUTER_KEYS) - 1)]:
        return "openrouter"
    return f"openrouter{n}" if n > 1 and len(OPENROUTER_KEYS) >= n else "openrouter"

PROVIDER_MAP = {
    "ceo": os.getenv("PROVIDER_CEO", _or(1)),
    "business_analyst": os.getenv("PROVIDER_BA", _or(2)),
    "researcher": os.getenv("PROVIDER_RESEARCHER", _or(3)),
    "architect": os.getenv("PROVIDER_ARCHITECT", _or(4)),
    "engineer": os.getenv("PROVIDER_ENGINEER", "openai" if OPENAI_API_KEY else _or(1)),
    "ppt": os.getenv("PROVIDER_PPT", _or(2)),
    "cross_review": os.getenv("PROVIDER_REVIEW", _or(3)),
}

MODEL_MAP = {
    "ceo": os.getenv("MODEL_CEO", "google/gemini-2.5-flash"),
    "business_analyst": os.getenv("MODEL_BA", SMART_MODEL),
    "researcher": os.getenv("MODEL_RESEARCHER", "google/gemini-2.5-flash"),
    "architect": os.getenv("MODEL_ARCHITECT", SMART_MODEL),
    "engineer": os.getenv("MODEL_ENGINEER", "gpt-4o" if OPENAI_API_KEY else SMART_MODEL),
    "ppt": os.getenv("MODEL_PPT", "google/gemini-2.5-flash"),
    "cross_review": os.getenv("MODEL_REVIEW", "google/gemini-2.5-flash"),
}

FALLBACK_MAP = {
    "ceo": os.getenv("FALLBACK_CEO", FALLBACK_MODEL),
    "business_analyst": os.getenv("FALLBACK_BA", FALLBACK_MODEL),
    "researcher": os.getenv("FALLBACK_RESEARCHER", FALLBACK_MODEL),
    "architect": os.getenv("FALLBACK_ARCHITECT", FALLBACK_MODEL),
    "engineer": os.getenv("FALLBACK_ENGINEER", SMART_MODEL),
    "ppt": os.getenv("FALLBACK_PPT", FALLBACK_MODEL),
    "cross_review": os.getenv("FALLBACK_REVIEW", FALLBACK_MODEL),
}

# Fallback provider: use a DIFFERENT key so if one hits quota, another takes over
FALLBACK_PROVIDER_MAP = {
    "ceo": _or(3),
    "business_analyst": _or(4),
    "researcher": _or(1),
    "architect": _or(2),
    "engineer": _or(3),
    "ppt": _or(4),
    "cross_review": _or(1),
}
