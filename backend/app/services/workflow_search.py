"""
Workflow search service — queries the indexed n8n workflow database.
Used by the RAG agent to find relevant workflows for a given problem statement.
"""

import sqlite3
import os
from pathlib import Path
from typing import Optional


DB_PATH = os.getenv("WORKFLOW_DB_PATH", str(Path(__file__).parent.parent.parent / "workflows.db"))


def get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def search_workflows(query: str, limit: int = 10, category: Optional[str] = None,
                     ai_only: bool = False) -> list[dict]:
    conn = get_db()
    results = []

    terms = query.strip().replace("'", "").replace('"', "")
    fts_query = " OR ".join(terms.split())

    sql = """
        SELECT w.id, w.name, w.domain_category, w.sih_themes, w.tags,
               w.integrations, w.node_count, w.has_ai_nodes, w.has_webhook,
               w.has_database, w.description, w.source
        FROM workflows_fts f
        JOIN workflows w ON f.rowid = w.id
        WHERE workflows_fts MATCH ?
    """
    params = [fts_query]

    if category:
        sql += " AND w.domain_category = ?"
        params.append(category)
    if ai_only:
        sql += " AND w.has_ai_nodes = 1"

    sql += " LIMIT ?"
    params.append(limit)

    try:
        rows = conn.execute(sql, params).fetchall()
        for row in rows:
            results.append(dict(row))
    except Exception:
        results = _fallback_search(conn, query, limit, category, ai_only)

    conn.close()
    return results


def _fallback_search(conn: sqlite3.Connection, query: str, limit: int,
                     category: Optional[str], ai_only: bool) -> list[dict]:
    terms = query.lower().split()
    conditions = []
    params = []
    for term in terms[:5]:
        conditions.append("(LOWER(name) LIKE ? OR LOWER(tags) LIKE ? OR LOWER(integrations) LIKE ?)")
        params.extend([f"%{term}%"] * 3)

    sql = f"SELECT * FROM workflows WHERE ({' OR '.join(conditions)})"
    if category:
        sql += " AND domain_category = ?"
        params.append(category)
    if ai_only:
        sql += " AND has_ai_nodes = 1"
    sql += f" LIMIT {limit}"

    rows = conn.execute(sql, params).fetchall()
    return [dict(r) for r in rows]


def search_by_category(category: str, limit: int = 20, ai_only: bool = False) -> list[dict]:
    conn = get_db()
    sql = "SELECT * FROM workflows WHERE domain_category = ?"
    params = [category]
    if ai_only:
        sql += " AND has_ai_nodes = 1"
    sql += " ORDER BY node_count DESC LIMIT ?"
    params.append(limit)

    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def search_by_sih_theme(theme: str, limit: int = 20) -> list[dict]:
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM workflows WHERE sih_themes LIKE ? ORDER BY has_ai_nodes DESC, node_count DESC LIMIT ?",
        [f"%{theme}%", limit]
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_category_stats() -> list[dict]:
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM category_stats ORDER BY workflow_count DESC"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_workflow_detail(workflow_id: int) -> Optional[dict]:
    conn = get_db()
    row = conn.execute("SELECT * FROM workflows WHERE id = ?", [workflow_id]).fetchone()
    conn.close()
    return dict(row) if row else None


def analyze_for_problem(problem_statement: str, limit: int = 10) -> dict:
    keywords = _extract_keywords(problem_statement)

    direct_matches = search_workflows(" ".join(keywords), limit=limit)
    ai_matches = search_workflows(" ".join(keywords), limit=5, ai_only=True)

    seen_ids = {w["id"] for w in direct_matches}
    for w in ai_matches:
        if w["id"] not in seen_ids:
            direct_matches.append(w)
            seen_ids.add(w["id"])

    reusable = []
    modifiable = []
    inspiration = []

    for w in direct_matches:
        relevance = _score_relevance(w, keywords)
        w["relevance_score"] = relevance

        if relevance >= 0.7:
            reusable.append(w)
        elif relevance >= 0.4:
            modifiable.append(w)
        else:
            inspiration.append(w)

    reusable.sort(key=lambda x: x["relevance_score"], reverse=True)
    modifiable.sort(key=lambda x: x["relevance_score"], reverse=True)

    categories_hit = list(set(w["domain_category"] for w in direct_matches))
    sih_themes_hit = set()
    for w in direct_matches:
        for t in w.get("sih_themes", "").split(","):
            if t.strip():
                sih_themes_hit.add(t.strip())

    return {
        "query": problem_statement,
        "keywords_extracted": keywords,
        "total_matches": len(direct_matches),
        "reusable": reusable[:5],
        "modifiable": modifiable[:5],
        "inspiration": inspiration[:5],
        "categories_matched": categories_hit,
        "sih_themes_matched": list(sih_themes_hit),
        "summary": _build_summary(reusable, modifiable, inspiration),
    }


def analyze_by_components(components: list[str], limit_per_component: int = 5) -> dict:
    """
    Component-by-component RAG search — takes the CEO's structured breakdown
    and searches for each component separately, combining results.
    """
    all_matches = []
    seen_ids = set()
    component_results = {}

    for component in components:
        keywords = _extract_keywords(component)
        if not keywords:
            continue

        matches = search_workflows(" ".join(keywords), limit=limit_per_component)
        ai_matches = search_workflows(" ".join(keywords), limit=3, ai_only=True)

        for w in ai_matches:
            if w["id"] not in {m["id"] for m in matches}:
                matches.append(w)

        scored = []
        for w in matches:
            if w["id"] in seen_ids:
                continue
            w["relevance_score"] = _score_relevance(w, keywords)
            w["matched_component"] = component
            scored.append(w)
            seen_ids.add(w["id"])
            all_matches.append(w)

        scored.sort(key=lambda x: x["relevance_score"], reverse=True)
        component_results[component] = scored[:3]

    reusable = [w for w in all_matches if w["relevance_score"] >= 0.7]
    modifiable = [w for w in all_matches if 0.4 <= w["relevance_score"] < 0.7]
    inspiration = [w for w in all_matches if w["relevance_score"] < 0.4]

    reusable.sort(key=lambda x: x["relevance_score"], reverse=True)
    modifiable.sort(key=lambda x: x["relevance_score"], reverse=True)

    categories_hit = list(set(w["domain_category"] for w in all_matches))
    sih_themes_hit = set()
    for w in all_matches:
        for t in w.get("sih_themes", "").split(","):
            if t.strip():
                sih_themes_hit.add(t.strip())

    return {
        "query": " | ".join(components),
        "components_searched": components,
        "component_results": {
            comp: [{"name": w["name"], "category": w["domain_category"],
                    "score": w["relevance_score"]}
                   for w in results]
            for comp, results in component_results.items()
        },
        "keywords_extracted": list(set(
            kw for comp in components for kw in _extract_keywords(comp)
        ))[:20],
        "total_matches": len(all_matches),
        "reusable": reusable[:5],
        "modifiable": modifiable[:5],
        "inspiration": inspiration[:5],
        "categories_matched": categories_hit,
        "sih_themes_matched": list(sih_themes_hit),
        "summary": _build_summary(reusable, modifiable, inspiration),
    }


def _extract_keywords(text: str) -> list[str]:
    stop_words = {
        "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
        "have", "has", "had", "do", "does", "did", "will", "would", "could",
        "should", "may", "might", "shall", "can", "need", "dare", "ought",
        "used", "to", "of", "in", "for", "on", "with", "at", "by", "from",
        "as", "into", "through", "during", "before", "after", "above",
        "below", "between", "and", "but", "or", "nor", "not", "so", "yet",
        "both", "either", "neither", "each", "every", "all", "any", "few",
        "more", "most", "other", "some", "such", "no", "only", "own", "same",
        "than", "too", "very", "just", "because", "that", "this", "these",
        "those", "it", "its", "they", "them", "their", "we", "us", "our",
        "you", "your", "he", "him", "his", "she", "her", "i", "me", "my",
        "what", "which", "who", "whom", "how", "when", "where", "why",
        "about", "up", "out", "if", "then", "also", "over",
    }
    words = text.lower().split()
    words = [w.strip(".,!?;:()[]{}\"'") for w in words]
    keywords = [w for w in words if w and w not in stop_words and len(w) > 2]
    return keywords[:15]


def _score_relevance(workflow: dict, keywords: list[str]) -> float:
    name = workflow.get("name", "").lower()
    tags = workflow.get("tags", "").lower()
    integrations = workflow.get("integrations", "").lower()
    desc = workflow.get("description", "").lower()

    matched_name = sum(1 for k in keywords if k in name)
    matched_tags = sum(1 for k in keywords if k in tags)
    matched_ints = sum(1 for k in keywords if k in integrations)
    matched_desc = sum(1 for k in keywords if k in desc)

    total_kw = max(len(keywords), 1)
    name_score = matched_name / total_kw * 0.5
    other_score = (matched_tags + matched_ints + matched_desc) / (total_kw * 3) * 0.3

    base_score = 0.3 + name_score + other_score

    if workflow.get("has_ai_nodes"):
        base_score += 0.1
    if workflow.get("node_count", 0) > 5:
        base_score += 0.05
    if workflow.get("has_webhook"):
        base_score += 0.05

    return min(base_score, 1.0)


def _build_summary(reusable: list, modifiable: list, inspiration: list) -> str:
    parts = []
    if reusable:
        parts.append(f"{len(reusable)} workflows can be reused directly")
    if modifiable:
        parts.append(f"{len(modifiable)} need modifications")
    if inspiration:
        parts.append(f"{len(inspiration)} provide pattern inspiration")
    if not parts:
        return "No matching workflows found — build from scratch recommended."
    return f"Found {len(reusable) + len(modifiable) + len(inspiration)} relevant workflows: " + ", ".join(parts) + "."
