import json
import logging
import re
from typing import Optional

from app.core.database import (
    get_project,
    get_project_outputs,
    get_memory,
    save_domain_learning,
    query_domain_learnings,
)

logger = logging.getLogger(__name__)


def _extract_keywords(text: str) -> list[str]:
    """Extract meaningful keywords from a problem statement for domain matching."""
    stop_words = {
        "a", "an", "the", "is", "are", "was", "were", "be", "been", "being",
        "have", "has", "had", "do", "does", "did", "will", "would", "could",
        "should", "may", "might", "shall", "can", "need", "dare", "ought",
        "used", "to", "of", "in", "for", "on", "with", "at", "by", "from",
        "as", "into", "through", "during", "before", "after", "above", "below",
        "between", "out", "off", "over", "under", "again", "further", "then",
        "once", "and", "but", "or", "nor", "not", "so", "yet", "both", "either",
        "neither", "each", "every", "all", "any", "few", "more", "most", "other",
        "some", "such", "no", "only", "own", "same", "than", "too", "very",
        "just", "about", "also", "that", "this", "these", "those", "it", "its",
        "build", "create", "make", "develop", "implement", "design", "want",
        "app", "application", "system", "platform", "tool", "software", "project",
        "using", "use", "like", "based", "small", "large", "new", "good", "best",
    }
    words = re.findall(r'[a-z]+', text.lower())
    keywords = [w for w in words if len(w) > 2 and w not in stop_words]
    seen = set()
    unique = []
    for w in keywords:
        if w not in seen:
            seen.add(w)
            unique.append(w)
    return unique[:15]


def _safe_get(content, key, default=""):
    if isinstance(content, dict):
        return content.get(key, default)
    return default


async def extract_learnings(project_id: str) -> list[dict]:
    """Extract reusable domain learnings from a completed project's agent outputs."""
    project = await get_project(project_id)
    if not project:
        return []

    outputs = await get_project_outputs(project_id)
    memory = await get_memory(project_id)
    problem = project.get("problem_statement", "")
    keywords = _extract_keywords(problem)
    domain = " ".join(keywords[:8])

    learnings = []

    for output in outputs:
        if output.get("status") != "approved":
            continue
        role = output.get("role", "")
        content = output.get("content", {})
        if isinstance(content, str):
            try:
                content = json.loads(content)
            except (json.JSONDecodeError, TypeError):
                content = {}

        if role == "ceo":
            proj_name = _safe_get(content, "project_name", "")
            deliverable = _safe_get(content, "deliverable_type", "code")
            components = _safe_get(content, "components", [])
            if proj_name and components:
                comp_list = ", ".join(components) if isinstance(components, list) else str(components)
                learnings.append({
                    "category": "approach",
                    "title": f"Project structure: {proj_name}",
                    "content": f"For '{problem[:100]}', the system was decomposed into components: {comp_list}. Deliverable type: {deliverable}.",
                    "source_role": "ceo",
                })

        elif role == "business_analyst":
            risks = _safe_get(content, "risks", [])
            constraints = _safe_get(content, "constraints", [])
            if risks and isinstance(risks, list):
                risk_summary = "; ".join(
                    r if isinstance(r, str) else json.dumps(r)
                    for r in risks[:5]
                )
                learnings.append({
                    "category": "pitfall",
                    "title": "Key risks identified",
                    "content": risk_summary,
                    "source_role": "business_analyst",
                })
            if constraints and isinstance(constraints, list):
                constraint_summary = "; ".join(
                    c if isinstance(c, str) else json.dumps(c)
                    for c in constraints[:5]
                )
                learnings.append({
                    "category": "pattern",
                    "title": "Constraints and boundaries",
                    "content": constraint_summary,
                    "source_role": "business_analyst",
                })

        elif role == "researcher":
            raw = _safe_get(content, "raw_response", "")
            existing = _safe_get(content, "existing_products", [])
            approach = _safe_get(content, "recommended_approach", "")
            if existing and isinstance(existing, list):
                product_names = []
                for p in existing[:5]:
                    if isinstance(p, dict):
                        product_names.append(p.get("name", str(p)))
                    elif isinstance(p, str):
                        product_names.append(p)
                if product_names:
                    learnings.append({
                        "category": "technology",
                        "title": "Existing products analyzed",
                        "content": f"Competitors/alternatives studied: {', '.join(product_names)}",
                        "source_role": "researcher",
                    })
            if approach and isinstance(approach, str) and len(approach) > 20:
                learnings.append({
                    "category": "approach",
                    "title": "Recommended technical approach",
                    "content": approach[:500],
                    "source_role": "researcher",
                })

        elif role == "architect":
            arch_overview = _safe_get(content, "architecture_overview", "")
            tech_stack = _safe_get(content, "tech_stack", _safe_get(content, "frontend_architecture", ""))
            system_type = _safe_get(content, "system_type", "")
            raw = _safe_get(content, "raw_response", "")

            if arch_overview and isinstance(arch_overview, str) and len(arch_overview) > 20:
                learnings.append({
                    "category": "architecture",
                    "title": f"Architecture: {system_type}" if system_type else "Architecture decision",
                    "content": arch_overview[:500],
                    "source_role": "architect",
                })
            if isinstance(tech_stack, dict):
                stack_str = json.dumps(tech_stack)[:400]
                learnings.append({
                    "category": "technology",
                    "title": "Tech stack chosen",
                    "content": stack_str,
                    "source_role": "architect",
                })

        elif role == "engineer":
            files = _safe_get(content, "files", [])
            if isinstance(files, list) and files:
                file_names = [f.get("filename", "") if isinstance(f, dict) else "" for f in files[:10]]
                file_names = [f for f in file_names if f]
                if file_names:
                    learnings.append({
                        "category": "pattern",
                        "title": "Code file structure",
                        "content": f"Generated files: {', '.join(file_names)}",
                        "source_role": "engineer",
                    })

    saved = []
    for learning in learnings:
        try:
            result = await save_domain_learning(
                project_id=project_id,
                category=learning["category"],
                domain=domain,
                title=learning["title"],
                content=learning["content"],
                source_role=learning["source_role"],
            )
            saved.append(result)
        except Exception as e:
            logger.warning(f"Failed to save learning: {e}")

    logger.info(f"Extracted {len(saved)} domain learnings from project {project_id}")
    return saved


async def get_relevant_learnings(problem_statement: str, project_id: Optional[str] = None) -> str:
    """Query past learnings relevant to a new problem statement and format for injection into agent context."""
    keywords = _extract_keywords(problem_statement)
    if not keywords:
        return ""

    learnings = await query_domain_learnings(
        keywords=keywords[:6],
        exclude_project_id=project_id,
        limit=10,
    )

    if not learnings:
        return ""

    parts = ["## Learnings from Past Projects\nThe following insights were extracted from previous pipeline runs on similar problems:\n"]
    by_category: dict[str, list] = {}
    for l in learnings:
        cat = l.get("category", "general")
        by_category.setdefault(cat, []).append(l)

    category_labels = {
        "architecture": "Architecture Decisions",
        "technology": "Technology Choices",
        "approach": "Approaches & Strategies",
        "pitfall": "Risks & Pitfalls to Avoid",
        "pattern": "Patterns & Structures",
    }

    for cat, items in by_category.items():
        label = category_labels.get(cat, cat.title())
        parts.append(f"### {label}")
        for item in items:
            parts.append(f"- **{item.get('title', 'Insight')}**: {item.get('content', '')}")

    return "\n".join(parts)
