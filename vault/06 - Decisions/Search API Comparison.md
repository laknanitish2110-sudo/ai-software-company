# Search API Comparison

## Current Choice: Dual Search (Tavily + DuckDuckGo)

We use BOTH search engines simultaneously, merge and deduplicate results to give the Researcher agent the broadest, most reliable research data.

**File:** `backend/app/services/web_search.py`

### How Dual Search Works

1. Researcher agent receives a problem statement
2. `research_topic()` runs 3 query categories:
   - `"{topic}" competitors existing solutions`
   - `"{topic}" open source tools libraries`
   - `"{topic}" API services integrations`
3. Each query hits BOTH search engines:
   - **Tavily** — AI-optimized, structured, high-quality content
   - **DuckDuckGo** — broad coverage, different result set
4. Results are merged and deduplicated by URL
5. Source attribution is preserved (`[tavily]` / `[duckduckgo]`)
6. Combined results are injected into the Researcher's prompt

### Why Two Sources

| Benefit | Explanation |
|---------|-------------|
| **Broader coverage** | Different engines surface different results |
| **Reliability** | If one fails, the other still works |
| **Quality + breadth** | Tavily gives AI-ready content, DDG gives wider web coverage |
| **Free** | Both have free tiers — zero cost |
| **Verification** | Multiple sources catch more real products and tools |

## Engine Comparison

| Feature | Tavily | DuckDuckGo | SerpAPI | Serper.dev |
|---------|--------|------------|---------|------------|
| **Price** | Free: 1000/mo | Free | $50/mo (5000) | $50/mo (2500) |
| **API key needed** | Yes | No | Yes | Yes |
| **Built for AI** | Yes | No | No | No |
| **Result quality** | Excellent | Good | Excellent | Good |
| **Structured output** | Yes (JSON) | Basic | Yes | Yes |
| **Content extraction** | Full page text | Snippets only | Snippets | Snippets |
| **Reliability** | Official API | Unofficial | Official | Official |

## Why Not SerpAPI

SerpAPI gives Google-quality results ($50/mo), but Tavily already provides excellent AI-optimized results for free. Adding SerpAPI would mean paying $50/mo for marginal improvement over what Tavily + DDG already deliver. Saved for V3 if needed.

## Configuration

**Environment variables in `.env`:**
```
TAVILY_API_KEY=tvly-dev-...
```

If `TAVILY_API_KEY` is empty, the system falls back to DuckDuckGo only.

Related: [[Tech Stack]], [[Agent Roster]], [[Cross Review System]]
