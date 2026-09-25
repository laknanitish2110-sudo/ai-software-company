"""
Reusable decision question definitions for the Jev/Jeff decision layer.

Each question is a dict with:
- type: "choice" | "noul" | "score"
- instructions: what to decide
- criteria: options with descriptions
- default: fallback when using rule-based engine
"""

ROUTE_CLASSIFICATION = {
    "type": "choice",
    "instructions": "Based on the user's task description, which pipeline route is most appropriate?",
    "criteria": {
        "quick_build": "Simple single-feature app, landing page, prototype, or demo — minimal complexity, skip analysis",
        "standard": "Moderate complexity requiring requirements + architecture + code but no deep research",
        "full": "Complex product requiring full analysis, research, architecture, code, and presentation",
        "research": "Market analysis, feasibility study, or investigation — no code needed",
        "report": "Document, pitch deck, proposal, or business plan — no code generation",
    },
    "default": "full",
}

QA_GATE = {
    "type": "choice",
    "instructions": "Given the test results and QA report, should this implementation proceed?",
    "criteria": {
        "pass": "All critical functionality works, tests pass, output meets requirements",
        "repair": "There are fixable failures — implementation needs another repair cycle",
        "escalate": "Fundamental issues that require human judgment or architectural changes",
    },
    "default": "repair",
}

REPAIR_STRATEGY = {
    "type": "choice",
    "instructions": "Given the repair history and current failures, what should happen next?",
    "criteria": {
        "continue_repair": "The current approach can fix remaining issues with targeted patches",
        "change_approach": "The current strategy isn't working — try a fundamentally different implementation",
        "escalate_human": "This requires human intervention — automated repair cannot resolve it",
    },
    "default": "continue_repair",
}

TASK_DIFFICULTY = {
    "type": "score",
    "instructions": "How difficult is this task on a scale of 1-10?",
    "criteria": {
        "1-3": "Simple CRUD, static pages, basic utilities — any model can handle it",
        "4-6": "Moderate complexity — requires some architectural thinking",
        "7-9": "Complex system with multiple integrations, auth, real-time features",
        "10": "Enterprise-scale, novel architecture, cutting-edge requirements",
    },
    "default": "5",
}

EMPLOYEE_ROUTING = {
    "type": "choice",
    "instructions": "Based on the user's request, which AI employee should handle this task?",
    "criteria": {
        "arc": "System design, architecture, database schemas, API design, technical planning",
        "sage": "Requirements analysis, competitive analysis, scope definition, business logic",
        "scout": "Technology research, market analysis, finding best practices and tools",
        "atlas": "Code implementation, bug fixing, full-stack development, code review",
        "sentinel": "Testing, security audits, performance testing, vulnerability scanning",
        "scribe": "Documentation, README generation, API docs, technical reports, writing",
    },
    "default": "atlas",
}

HUMAN_REVIEW_NEEDED = {
    "type": "noul",
    "instructions": "Does this task or its output require human review before proceeding?",
    "criteria": {
        "yes": "Security-sensitive, user-facing, irreversible, or ambiguous requirements",
        "no": "Low-risk, well-defined, reversible, and within established patterns",
    },
    "default": "no",
}
