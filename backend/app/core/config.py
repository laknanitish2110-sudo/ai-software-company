import os
from dotenv import load_dotenv

load_dotenv()

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "").strip()
OPENROUTER_BASE_URL = os.getenv("LLM_BASE_URL", "https://openrouter.ai/api/v1").strip()
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

PROVIDER_MAP = {
    "ceo": os.getenv("PROVIDER_CEO", "openrouter"),
    "business_analyst": os.getenv("PROVIDER_BA", "openrouter"),
    "researcher": os.getenv("PROVIDER_RESEARCHER", "openrouter"),
    "architect": os.getenv("PROVIDER_ARCHITECT", "openrouter"),
    "engineer": os.getenv("PROVIDER_ENGINEER", "openai" if OPENAI_API_KEY else "openrouter"),
    "ppt": os.getenv("PROVIDER_PPT", "openrouter"),
    "cross_review": os.getenv("PROVIDER_REVIEW", "openrouter"),
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

# Fallback provider: which provider to use for the fallback model
FALLBACK_PROVIDER_MAP = {
    "ceo": "openrouter",
    "business_analyst": "openrouter",
    "researcher": "openrouter",
    "architect": "openrouter",
    "engineer": "openrouter",
    "ppt": "openrouter",
    "cross_review": "openrouter",
}
