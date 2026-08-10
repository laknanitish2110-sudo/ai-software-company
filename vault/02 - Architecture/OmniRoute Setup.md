# OmniRoute Setup

## What is OmniRoute
Free, self-hosted AI gateway that sits between our backend and LLM providers. Routes requests to free/paid providers, handles failover, load balancing, and model aliasing. Replaces direct OpenRouter dependency.

- **GitHub**: https://github.com/diegosouzapw/OmniRoute
- **Version**: v3.8.49
- **Runs on**: `http://localhost:20128`
- **Dashboard**: `http://localhost:20128` (browser)

## API Key

| Key Name | Value | Purpose |
|----------|-------|---------|
| OmniRoute API Key | `sk-5cea04751782c7aa-47912e-efbb4d68` | Backend authentication to OmniRoute (local gateway) |
| Default Dashboard Password | `CHANGEME` | OmniRoute admin dashboard login |
| OpenRouter API Key | `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` | Paid OpenRouter access (current primary) |

## Backend .env Configuration

**Current (OpenRouter direct with Nemotron):**
```env
OPENROUTER_API_KEY=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
LLM_BASE_URL=https://openrouter.ai/api/v1
SMART_MODEL=nvidia/nemotron-3-ultra-550b-a55b:free
TAVILY_API_KEY=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
N8N_WEBHOOK_URL=
```

**Previous (OmniRoute local gateway):**
```env
OPENROUTER_API_KEY=sk-5cea04751782c7aa-47912e-efbb4d68
LLM_BASE_URL=http://localhost:20128/v1
SMART_MODEL=auto
```

## How It Works in Our Pipeline

```
Backend (FastAPI) 
    --> OpenAI SDK (AsyncOpenAI)
        --> OmniRoute (localhost:20128/v1)
            --> Free providers (OpenCode Free, Felo, DuckDuckGo AI Chat)
            --> OR paid providers (OpenRouter, Anthropic, OpenAI, etc.)
```

- `SMART_MODEL=auto` lets OmniRoute pick the best available provider
- OmniRoute handles retry, failover, and rate limiting automatically
- No API costs when using free providers (quality trade-off: JSON truncation on long outputs)

## Free Providers Configured
These came pre-configured with OmniRoute:
- **OpenCode Free** - Free Claude/GPT access
- **Felo** - Free search-augmented AI
- **DuckDuckGo AI Chat** - Free chat completions

## Installation Path
```
C:\Users\rajes\AppData\Roaming\npm\node_modules\omniroute\
```

## Start Command
```bash
npx omniroute start
```

## Known Limitations with Free Providers
1. **JSON truncation** - Long structured outputs (like Engineer's file list) get cut off, causing parse errors
2. **Slower response times** - Free providers can take 30-60s per agent call
3. **Rate limiting** - Some free providers limit requests per minute
4. **Model quality** - Free models may not follow JSON schema instructions as precisely

## Switching to Paid Models
To use paid providers (OpenRouter, direct API keys), update the OmniRoute dashboard:
1. Go to `http://localhost:20128`
2. Add connection with API key
3. Set model routing rules or change `SMART_MODEL` in `.env`

See: [[Search API Comparison]], [[Tech Stack]]
