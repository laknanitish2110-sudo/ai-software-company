"""
n8n Workflow Indexer — parses 19,556 workflow JSONs into a searchable SQLite database.

Usage:
    python -m app.services.workflow_indexer --source <path_to_workflows> [--db workflows.db]
"""

import json
import os
import sqlite3
import sys
import time
from pathlib import Path
from typing import Optional


# Maps folder names to SIH-relevant domain categories
FOLDER_TO_CATEGORY = {
    # From the categorized templates (4000 Updated2025)
    "agriculture": "Agriculture & Rural Development",
    "ai_ml": "AI & Machine Learning",
    "automotive": "Transportation & Logistics",
    "creative_content": "Creative & Content",
    "data_analytics": "Data Analytics & BI",
    "devops": "DevOps & Infrastructure",
    "education": "Education & Skill Development",
    "email_automation": "Communication & Notifications",
    "energy": "Energy & Sustainability",
    "e_commerce_retail": "E-Commerce & Retail",
    "finance_accounting": "Finance & Fintech",
    "gaming": "Gaming & Entertainment",
    "government_ngo": "Government & Public Services",
    "healthcare": "Healthcare & Wellness",
    "hr": "HR & Recruitment",
    "iot": "IoT & Smart Systems",
    "legal_tech": "Legal & Compliance",
    "manufacturing": "Manufacturing & Supply Chain",
    "media": "Media & Publishing",
    "misc": "Miscellaneous",
    "productivity": "Productivity & Workflow",
    "real_estate": "Real Estate & Property",
    "social_media": "Social Media & Marketing",
    "travel": "Travel & Hospitality",
    # From the agents folder — tool-based categories
    "openai": "AI & Machine Learning",
    "openai_and_llms": "AI & Machine Learning",
    "deep": "AI & Machine Learning",
    "telegram": "Communication & Notifications",
    "telegramtool": "Communication & Notifications",
    "whatsapp": "Communication & Notifications",
    "slack": "Communication & Notifications",
    "discord": "Communication & Notifications",
    "discordtool": "Communication & Notifications",
    "gmail": "Communication & Notifications",
    "gmailtool": "Communication & Notifications",
    "gmail_and_email_automation": "Communication & Notifications",
    "emailsend": "Communication & Notifications",
    "emailreadimap": "Communication & Notifications",
    "googlesheets": "Data Analytics & BI",
    "googlesheetstool": "Data Analytics & BI",
    "googlebigquery": "Data Analytics & BI",
    "googleanalytics": "Data Analytics & BI",
    "google_drive_and_google_sheets": "Data Analytics & BI",
    "googledrive": "Productivity & Workflow",
    "googledrivetool": "Productivity & Workflow",
    "googledocs": "Productivity & Workflow",
    "googlecalendar": "Productivity & Workflow",
    "googlecalendartool": "Productivity & Workflow",
    "googletasks": "Productivity & Workflow",
    "googletaskstool": "Productivity & Workflow",
    "notion": "Productivity & Workflow",
    "asana": "Productivity & Workflow",
    "clickup": "Productivity & Workflow",
    "todoist": "Productivity & Workflow",
    "trello": "Productivity & Workflow",
    "mondaycom": "Productivity & Workflow",
    "github": "DevOps & Infrastructure",
    "gitlab": "DevOps & Infrastructure",
    "bitbucket": "DevOps & Infrastructure",
    "devops": "DevOps & Infrastructure",
    "postgres": "DevOps & Infrastructure",
    "postgrestool": "DevOps & Infrastructure",
    "mysqltool": "DevOps & Infrastructure",
    "mongodbtool": "DevOps & Infrastructure",
    "redis": "DevOps & Infrastructure",
    "elasticsearch": "DevOps & Infrastructure",
    "supabase": "DevOps & Infrastructure",
    "database_and_storage": "DevOps & Infrastructure",
    "hubspot": "E-Commerce & Retail",
    "shopify": "E-Commerce & Retail",
    "woocommerce": "E-Commerce & Retail",
    "woocommercetool": "E-Commerce & Retail",
    "pipedrive": "E-Commerce & Retail",
    "twitter": "Social Media & Marketing",
    "twittertool": "Social Media & Marketing",
    "facebook": "Social Media & Marketing",
    "facebookleadads": "Social Media & Marketing",
    "linkedin": "Social Media & Marketing",
    "instagram_twitter_social_media": "Social Media & Marketing",
    "youtube": "Media & Publishing",
    "figma": "Creative & Content",
    "bannerbear": "Creative & Content",
    "googleslides": "Creative & Content",
    "jira": "Productivity & Workflow",
    "jiratool": "Productivity & Workflow",
    "http": "Integration & API",
    "webhook": "Integration & API",
    "graphql": "Integration & API",
    "automation": "Productivity & Workflow",
    "automate": "Productivity & Workflow",
    "forms_and_surveys": "Data Collection & Forms",
    "form": "Data Collection & Forms",
    "pdf_and_document_processing": "Document Processing",
    "hr_and_recruitment": "HR & Recruitment",
    "ai_research_rag_and_data_analysis": "AI & Machine Learning",
    "other_integrations_and_use_cases": "Integration & API",
    "airtable": "Productivity & Workflow",
    "best of n8n agents": "AI & Machine Learning",
    "code": "DevOps & Infrastructure",
    "cron": "Productivity & Workflow",
    "schedule": "Productivity & Workflow",
    "paypal": "Finance & Fintech",
    "quickbooks": "Finance & Fintech",
    "wise": "Finance & Fintech",
    "chargebee": "Finance & Fintech",
    "intercom": "Communication & Notifications",
    "zendesk": "Communication & Notifications",
    "helpscout": "Communication & Notifications",
    "zohocrm": "E-Commerce & Retail",
    "microsoftexcel": "Productivity & Workflow",
    "microsoftonedrive": "Productivity & Workflow",
    "microsoftoutlook": "Communication & Notifications",
    "microsofttodo": "Productivity & Workflow",
    "wordpress": "Media & Publishing",
    "webflow": "Media & Publishing",
    "dropbox": "Productivity & Workflow",
    "box": "Productivity & Workflow",
    "awss3": "DevOps & Infrastructure",
    "awssns": "Communication & Notifications",
    "awsrekognition": "AI & Machine Learning",
    "awstextract": "Document Processing",
    "rssfeedread": "Media & Publishing",
    "twilio": "Communication & Notifications",
    "calendly": "Productivity & Workflow",
    "typeform": "Data Collection & Forms",
    "jotform": "Data Collection & Forms",
    "surveymonkey": "Data Collection & Forms",
    "mailchimp": "Social Media & Marketing",
    "mailerlite": "Social Media & Marketing",
    "convertkit": "Social Media & Marketing",
    "getresponse": "Social Media & Marketing",
    "netlify": "DevOps & Infrastructure",
    "eventbrite": "Travel & Hospitality",
    "stripe": "Finance & Fintech",
}

# SIH theme mapping — maps our categories to SIH's 15 official themes
SIH_THEME_MAP = {
    "Agriculture & Rural Development": ["Smart Automation", "Disaster Management", "Miscellaneous"],
    "AI & Machine Learning": ["Smart Automation", "Robotics", "MedTech / BioTech / HealthTech"],
    "Education & Skill Development": ["Smart Education", "Miscellaneous"],
    "Healthcare & Wellness": ["MedTech / BioTech / HealthTech", "Fitness & Sports"],
    "Government & Public Services": ["Smart Automation", "Blockchain & Cybersecurity"],
    "Finance & Fintech": ["FinTech", "Blockchain & Cybersecurity"],
    "IoT & Smart Systems": ["Clean & Green Technology", "Smart Automation", "Robotics"],
    "Communication & Notifications": ["Smart Automation", "Miscellaneous"],
    "Transportation & Logistics": ["Transportation & Logistics", "Smart Automation"],
    "Energy & Sustainability": ["Clean & Green Technology", "Renewable / Sustainable Energy"],
    "E-Commerce & Retail": ["FinTech", "Smart Automation"],
    "Data Analytics & BI": ["Smart Automation", "Miscellaneous"],
    "DevOps & Infrastructure": ["Smart Automation", "Blockchain & Cybersecurity"],
    "Social Media & Marketing": ["Smart Automation", "Miscellaneous"],
    "HR & Recruitment": ["Smart Automation", "Miscellaneous"],
    "Creative & Content": ["Heritage & Culture", "Miscellaneous"],
    "Legal & Compliance": ["Blockchain & Cybersecurity", "Miscellaneous"],
    "Manufacturing & Supply Chain": ["Smart Automation", "Robotics"],
    "Media & Publishing": ["Heritage & Culture", "Smart Automation"],
    "Travel & Hospitality": ["Tourism", "Heritage & Culture"],
    "Gaming & Entertainment": ["Fitness & Sports", "Miscellaneous"],
    "Real Estate & Property": ["Smart Automation", "Miscellaneous"],
    "Productivity & Workflow": ["Smart Automation", "Miscellaneous"],
    "Integration & API": ["Smart Automation", "Miscellaneous"],
    "Data Collection & Forms": ["Smart Automation", "Miscellaneous"],
    "Document Processing": ["Smart Automation", "Miscellaneous"],
    "Miscellaneous": ["Miscellaneous"],
}


def init_db(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS workflows (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_path TEXT UNIQUE,
            name TEXT,
            source TEXT,
            folder_category TEXT,
            domain_category TEXT,
            sih_themes TEXT,
            tags TEXT,
            node_types TEXT,
            node_count INTEGER,
            integrations TEXT,
            has_ai_nodes INTEGER DEFAULT 0,
            has_webhook INTEGER DEFAULT 0,
            has_database INTEGER DEFAULT 0,
            description TEXT,
            meta_json TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS category_stats (
            domain_category TEXT PRIMARY KEY,
            workflow_count INTEGER,
            top_integrations TEXT,
            sih_themes TEXT
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_domain ON workflows(domain_category)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_name ON workflows(name)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_sih ON workflows(sih_themes)")
    conn.execute("""
        CREATE VIRTUAL TABLE IF NOT EXISTS workflows_fts
        USING fts5(name, tags, integrations, description, domain_category)
    """)
    conn.commit()
    return conn


AI_NODE_PATTERNS = {
    "openai", "langchain", "anthropic", "huggingface", "cohere",
    "pinecone", "weaviate", "qdrant", "chromadb", "vectorstore",
    "embedding", "llm", "chatmodel", "agent", "chain", "rag",
    "textclassifier", "sentimentanalysis", "summarization",
}

DB_NODE_PATTERNS = {
    "postgres", "mysql", "mongodb", "redis", "supabase", "sqlite",
    "elasticsearch", "airtable", "notion", "googlesheets", "baserow",
    "nocodb", "dynamodb", "firebase",
}

WEBHOOK_PATTERNS = {"webhook", "httpRequest", "respondtowebhook"}


def extract_node_info(nodes: list) -> dict:
    node_types = set()
    integrations = set()
    has_ai = False
    has_webhook = False
    has_db = False

    for node in nodes:
        ntype = node.get("type", "")
        node_types.add(ntype)

        short = ntype.split(".")[-1].lower() if "." in ntype else ntype.lower()
        integrations.add(short)

        if any(p in short for p in AI_NODE_PATTERNS):
            has_ai = True
        if any(p in short for p in DB_NODE_PATTERNS):
            has_db = True
        if any(p in short for p in WEBHOOK_PATTERNS):
            has_webhook = True

    return {
        "node_types": list(node_types),
        "integrations": sorted(integrations - {"stickynote", "noop", "nooperation", "set", "code", "function", "functionitem", "if", "switch", "merge", "splitinbatches", "splitout", "filter", "limit", "removeduplicates", "sort", "summarize", "aggregate", "wait", "interval"}),
        "node_count": len(nodes),
        "has_ai": has_ai,
        "has_webhook": has_webhook,
        "has_db": has_db,
    }


def infer_category(folder_path: str, meta: dict, nodes: list = None) -> tuple[str, str]:
    parts = Path(folder_path).parts
    folder_cat = ""

    for part in reversed(parts):
        clean = part.lower().strip().replace(" ", "_").replace("-", "_")
        if clean in FOLDER_TO_CATEGORY:
            folder_cat = part
            return folder_cat, FOLDER_TO_CATEGORY[clean]

    meta_cat = (meta.get("category") or "").lower().strip()
    if meta_cat and meta_cat in FOLDER_TO_CATEGORY:
        return meta_cat, FOLDER_TO_CATEGORY[meta_cat]

    if nodes:
        return _categorize_by_nodes(nodes)

    return "uncategorized", "Miscellaneous"


NODE_CATEGORY_RULES = [
    ({"openai", "lmchatopenai", "lmchatgooglegemini", "lmchatanthropic", "agent",
      "vectorstore", "embedding", "chain", "lmchatollama", "googlegemini",
      "chatmodel", "pinecone", "qdrant", "chromadb", "memorybufferwindow",
      "outputparser", "textclassifier"}, "AI & Machine Learning"),
    ({"gmail", "gmailtool", "emailsend", "emailreadimap", "telegram",
      "telegramtrigger", "whatsapp", "whatsapptrigger", "slack",
      "discord", "twilio", "intercom", "sendgrid", "mailgun",
      "microsoftoutlook", "postmark"}, "Communication & Notifications"),
    ({"googlesheets", "googlesheetstool", "googlebigquery", "googleanalytics",
      "microsoftexcel", "airtable", "airtabletool", "posthog"}, "Data Analytics & BI"),
    ({"github", "gitlab", "postgres", "postgrestool", "mysqltool", "mongodbtool",
      "redis", "elasticsearch", "supabase", "docker", "awss3", "netlify",
      "travisci"}, "DevOps & Infrastructure"),
    ({"shopify", "woocommerce", "woocommercetool", "hubspot", "pipedrive",
      "zohocrm", "stripe", "paypal"}, "E-Commerce & Retail"),
    ({"twitter", "twittertool", "facebook", "facebookleadads", "linkedin",
      "instagram", "youtube", "mailchimp", "mailerlite", "convertkit",
      "getresponse", "lemlist"}, "Social Media & Marketing"),
    ({"googledrive", "googledrivetool", "googledocs", "googlecalendar",
      "googlecalendartool", "googletasks", "notion", "asana", "clickup",
      "todoist", "trello", "mondaycom", "jira", "jiratool",
      "microsofttodo", "microsoftonedrive", "dropbox", "box"}, "Productivity & Workflow"),
    ({"formtrigger", "form", "typeform", "jotform", "surveymonkey",
      "wufoo"}, "Data Collection & Forms"),
    ({"extractfromfile", "converttofile", "readbinaryfile", "writebinaryfile",
      "pdf", "markdown", "xml", "compression"}, "Document Processing"),
    ({"wordpress", "webflow", "rssfeedread", "ghost", "strapi",
      "contentful"}, "Media & Publishing"),
    ({"figma", "bannerbear", "googleslides", "editimage",
      "apitemplateio"}, "Creative & Content"),
    ({"quickbooks", "invoiceninja", "chargebee", "wise", "coingecko",
      "crypto"}, "Finance & Fintech"),
    ({"calendly", "eventbrite", "gotowebinar"}, "Travel & Hospitality"),
]


def _categorize_by_nodes(nodes: list) -> tuple[str, str]:
    node_types = set()
    for node in nodes:
        ntype = node.get("type", "")
        short = ntype.split(".")[-1].lower() if "." in ntype else ntype.lower()
        node_types.add(short)

    best_match = None
    best_score = 0
    for rule_nodes, category in NODE_CATEGORY_RULES:
        overlap = len(node_types & rule_nodes)
        if overlap > best_score:
            best_score = overlap
            best_match = category

    if best_match and best_score >= 1:
        return "node_inferred", best_match

    return "uncategorized", "Miscellaneous"


def extract_description(workflow: dict) -> str:
    parts = []
    for node in workflow.get("nodes", []):
        if node.get("type", "").endswith("stickyNote"):
            content = node.get("parameters", {}).get("content", "")
            if content and len(content) > 10:
                parts.append(content[:200])
        notes = node.get("notes", "")
        if notes and "automated" not in notes.lower() and len(notes) > 10:
            parts.append(notes[:100])
    return " | ".join(parts[:3]) if parts else ""


def parse_workflow(file_path: str) -> Optional[dict]:
    try:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            data = json.load(f)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None

    if isinstance(data, list):
        data = data[0] if data else {}

    name = data.get("name", Path(file_path).stem)
    meta = data.get("meta") or {}
    raw_tags = data.get("tags") or []
    if isinstance(raw_tags, list):
        tags = []
        for t in raw_tags:
            if isinstance(t, dict):
                tags.append(str(t.get("name", "")))
            elif isinstance(t, str):
                tags.append(t)
            else:
                tags.append(str(t))
    else:
        tags = []
    nodes = data.get("nodes", [])

    node_info = extract_node_info(nodes)
    folder_cat, domain_cat = infer_category(file_path, meta, nodes)
    sih_themes = SIH_THEME_MAP.get(domain_cat, ["Miscellaneous"])
    description = extract_description(data)

    return {
        "file_path": file_path,
        "name": name,
        "folder_category": folder_cat,
        "domain_category": domain_cat,
        "sih_themes": ",".join(sih_themes),
        "tags": ",".join(tags),
        "node_types": ",".join(node_info["node_types"]),
        "node_count": node_info["node_count"],
        "integrations": ",".join(node_info["integrations"]),
        "has_ai_nodes": 1 if node_info["has_ai"] else 0,
        "has_webhook": 1 if node_info["has_webhook"] else 0,
        "has_database": 1 if node_info["has_db"] else 0,
        "description": description,
        "meta_json": json.dumps(meta, default=str)[:500],
    }


def index_workflows(source_dir: str, db_path: str) -> dict:
    conn = init_db(db_path)
    json_files = list(Path(source_dir).rglob("*.json"))
    json_files = [f for f in json_files if ".obsidian" not in str(f)]

    total = len(json_files)
    indexed = 0
    failed = 0
    batch = []

    print(f"Found {total} JSON files to index...")

    for i, fpath in enumerate(json_files):
        result = parse_workflow(str(fpath))
        if result:
            # Determine source based on path
            path_str = str(fpath).lower()
            if "4000+ n8n agents" in path_str or "agents" in path_str:
                result["source"] = "agents"
            elif "4000 n8n workflow automation" in path_str:
                result["source"] = "categorized_templates"
            else:
                result["source"] = "templates"

            batch.append(result)
            indexed += 1
        else:
            failed += 1

        if len(batch) >= 500:
            _insert_batch(conn, batch)
            batch = []
            pct = int((i + 1) / total * 100)
            print(f"  [{pct}%] Indexed {indexed} workflows...")

    if batch:
        _insert_batch(conn, batch)

    _build_fts(conn)
    _build_category_stats(conn)

    conn.close()

    stats = {
        "total_files": total,
        "indexed": indexed,
        "failed": failed,
        "db_path": db_path,
    }
    print(f"\nDone! Indexed {indexed}/{total} workflows ({failed} failed)")
    return stats


def _insert_batch(conn: sqlite3.Connection, batch: list):
    conn.executemany("""
        INSERT OR IGNORE INTO workflows
        (file_path, name, source, folder_category, domain_category, sih_themes,
         tags, node_types, node_count, integrations, has_ai_nodes, has_webhook,
         has_database, description, meta_json)
        VALUES (:file_path, :name, :source, :folder_category, :domain_category,
                :sih_themes, :tags, :node_types, :node_count, :integrations,
                :has_ai_nodes, :has_webhook, :has_database, :description, :meta_json)
    """, batch)
    conn.commit()


def _build_fts(conn: sqlite3.Connection):
    conn.execute("DROP TABLE IF EXISTS workflows_fts")
    conn.execute("""
        CREATE VIRTUAL TABLE workflows_fts
        USING fts5(name, tags, integrations, description, domain_category)
    """)
    conn.execute("""
        INSERT INTO workflows_fts(rowid, name, tags, integrations, description, domain_category)
        SELECT id, name, tags, integrations, description, domain_category FROM workflows
    """)
    conn.commit()


def _build_category_stats(conn: sqlite3.Connection):
    conn.execute("DELETE FROM category_stats")
    rows = conn.execute("""
        SELECT domain_category, COUNT(*) as cnt
        FROM workflows GROUP BY domain_category ORDER BY cnt DESC
    """).fetchall()

    for cat, count in rows:
        top = conn.execute("""
            SELECT integrations FROM workflows
            WHERE domain_category = ? AND integrations != ''
            LIMIT 50
        """, (cat,)).fetchall()

        integration_counts = {}
        for (ints,) in top:
            for i in ints.split(","):
                i = i.strip()
                if i:
                    integration_counts[i] = integration_counts.get(i, 0) + 1
        top_ints = sorted(integration_counts, key=integration_counts.get, reverse=True)[:10]
        sih = SIH_THEME_MAP.get(cat, ["Miscellaneous"])

        conn.execute("""
            INSERT OR REPLACE INTO category_stats
            (domain_category, workflow_count, top_integrations, sih_themes)
            VALUES (?, ?, ?, ?)
        """, (cat, count, ",".join(top_ints), ",".join(sih)))

    conn.commit()
    print(f"\nCategory breakdown:")
    for cat, count in rows:
        print(f"  {cat}: {count} workflows")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Index n8n workflows into SQLite")
    parser.add_argument("--source", required=True, help="Path to workflows directory")
    parser.add_argument("--db", default="workflows.db", help="SQLite database path")
    args = parser.parse_args()

    start = time.time()
    stats = index_workflows(args.source, args.db)
    elapsed = time.time() - start
    print(f"Completed in {elapsed:.1f}s")
    print(json.dumps(stats, indent=2))
