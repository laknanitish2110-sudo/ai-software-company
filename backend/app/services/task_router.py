import logging

logger = logging.getLogger(__name__)

PIPELINE_ROUTES = {
    "quick_build": {
        "name": "Quick Build",
        "description": "Fast single-feature app — skip research and analysis",
        "agents": ["ceo", "engineer"],
        "cross_reviews": False,
        "estimated_minutes": 3,
        "icon": "⚡",
    },
    "standard": {
        "name": "Standard",
        "description": "Requirements, architecture, and code",
        "agents": ["ceo", "business_analyst", "architect", "engineer"],
        "cross_reviews": True,
        "estimated_minutes": 10,
        "icon": "🔧",
    },
    "full": {
        "name": "Full Pipeline",
        "description": "Complete analysis with research, code, and presentation",
        "agents": ["ceo", "business_analyst", "researcher", "architect", "engineer", "ppt"],
        "cross_reviews": True,
        "estimated_minutes": 20,
        "icon": "🏢",
    },
    "research": {
        "name": "Research Only",
        "description": "Market analysis and feasibility study — no code",
        "agents": ["ceo", "business_analyst", "researcher"],
        "cross_reviews": True,
        "estimated_minutes": 8,
        "icon": "🔍",
    },
    "report": {
        "name": "Report / Presentation",
        "description": "Document or pitch deck — no code generation",
        "agents": ["ceo", "business_analyst", "ppt"],
        "cross_reviews": False,
        "estimated_minutes": 6,
        "icon": "📊",
    },
}

SIMPLE_KEYWORDS = [
    "calculator", "todo", "to-do", "timer", "counter", "converter",
    "stopwatch", "clock", "quiz", "flashcard", "tic-tac-toe", "tictactoe",
    "hangman", "snake game", "pong", "memory game", "dice", "coin flip",
    "bmi", "tip calculator", "unit converter", "color picker", "notepad",
    "password generator", "random quote", "weather app", "hello world",
]

RESEARCH_KEYWORDS = [
    "analyze", "analysis", "research", "compare", "comparison", "market",
    "feasibility", "study", "survey", "benchmark", "evaluate", "assessment",
    "investigate", "explore options", "landscape",
]

COMPLEX_KEYWORDS = [
    "saas", "platform", "multi-tenant", "billing", "subscription",
    "authentication", "authorization", "real-time", "microservice",
    "distributed", "scalable", "enterprise", "marketplace", "e-commerce",
    "payment", "stripe", "oauth", "sso", "api gateway",
    "kubernetes", "docker", "deployment pipeline",
]

REPORT_KEYWORDS = [
    "pitch", "presentation", "proposal", "report", "document",
    "slide", "deck", "whitepaper", "brief", "memo", "business plan",
]

QUICK_BUILD_KEYWORDS = [
    "landing page", "portfolio", "blog", "static site", "homepage",
    "coming soon", "single page", "one page", "simple app", "basic app",
    "prototype", "mockup", "demo",
]


def classify_task(problem_statement: str) -> dict:
    text = problem_statement.lower().strip()
    word_count = len(text.split())

    scores = {
        "quick_build": 0,
        "standard": 0,
        "full": 0,
        "research": 0,
        "report": 0,
    }

    for kw in SIMPLE_KEYWORDS:
        if kw in text:
            scores["quick_build"] += 3

    for kw in QUICK_BUILD_KEYWORDS:
        if kw in text:
            scores["quick_build"] += 2

    for kw in RESEARCH_KEYWORDS:
        if kw in text:
            scores["research"] += 3

    for kw in COMPLEX_KEYWORDS:
        if kw in text:
            scores["full"] += 3

    for kw in REPORT_KEYWORDS:
        if kw in text:
            scores["report"] += 3

    if word_count < 15:
        scores["quick_build"] += 2
    elif word_count < 40:
        scores["standard"] += 1
    else:
        scores["full"] += 2

    max_score = max(scores.values())
    if max_score == 0:
        suggested = "full"
    else:
        suggested = max(scores, key=lambda k: scores[k])

    if suggested in ("research", "report"):
        code_signals = ["build", "create", "develop", "implement", "code", "app", "website", "api", "software"]
        if any(kw in text for kw in code_signals) and scores[suggested] < 6:
            suggested = "standard"

    return {
        "suggested_route": suggested,
        "route_info": PIPELINE_ROUTES[suggested],
        "scores": scores,
        "word_count": word_count,
        "all_routes": PIPELINE_ROUTES,
    }


def get_route_agents(route: str) -> list[str]:
    route_def = PIPELINE_ROUTES.get(route, PIPELINE_ROUTES["full"])
    return route_def["agents"]


def get_route_config(route: str) -> dict:
    return PIPELINE_ROUTES.get(route, PIPELINE_ROUTES["full"])
