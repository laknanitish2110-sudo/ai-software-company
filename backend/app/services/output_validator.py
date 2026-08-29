"""
Output validator — validates and repairs agent outputs before saving.
Ensures each role's JSON has the expected structure and fills missing fields.
"""

import logging

logger = logging.getLogger(__name__)

ROLE_SCHEMAS: dict[str, dict[str, str]] = {
    "ceo": {
        "project_name": "str",
        "problem_analysis": "str",
        "target_users": "str",
        "key_features": "list",
        "tech_requirements": "str",
        "success_metrics": "str",
        "deliverable_type": "str",
    },
    "business_analyst": {
        "executive_summary": "str",
        "user_personas": "list",
        "user_stories": "list",
        "functional_requirements": "list",
        "non_functional_requirements": "list",
        "scope": "str",
    },
    "researcher": {
        "market_analysis": "str",
        "competitor_analysis": "list",
        "technology_recommendations": "list",
        "recommended_approach": "str",
        "risks_and_mitigations": "list",
    },
    "architect": {
        "architecture_overview": "str",
        "tech_stack": "dict",
        "system_components": "list",
        "api_design": "list",
        "database_schema": "dict",
        "deployment_architecture": "str",
    },
    "engineer": {
        "project_structure": "str",
        "files": "list",
        "setup_instructions": "str",
        "dependencies": "dict",
    },
    "ppt": {
        "title": "str",
        "slides": "list",
        "speaker_notes": "list",
    },
}

TYPE_DEFAULTS: dict[str, object] = {
    "str": "[Not provided]",
    "list": [],
    "dict": {},
}


def validate_output(role: str, content: dict) -> dict:
    if "_parse_error" in content:
        return content

    schema = ROLE_SCHEMAS.get(role)
    if not schema:
        return content

    repaired = False
    for field, field_type in schema.items():
        if field not in content:
            content[field] = TYPE_DEFAULTS.get(field_type, "")
            repaired = True
        elif field_type == "str" and not isinstance(content[field], str):
            content[field] = str(content[field]) if content[field] is not None else "[Not provided]"
            repaired = True
        elif field_type == "list" and not isinstance(content[field], list):
            if isinstance(content[field], str):
                content[field] = [content[field]]
            elif isinstance(content[field], dict):
                content[field] = [content[field]]
            else:
                content[field] = []
            repaired = True
        elif field_type == "dict" and not isinstance(content[field], dict):
            if isinstance(content[field], str):
                content[field] = {"value": content[field]}
            else:
                content[field] = {}
            repaired = True

    for key in list(content.keys()):
        val = content[key]
        if isinstance(val, str):
            content[key] = val.strip()
            if not content[key] and key in schema:
                content[key] = "[Not provided]"

    if repaired:
        logger.info(f"Repaired output for {role}: filled missing fields")
        content["_repaired"] = True

    return content


def get_output_quality_score(role: str, content) -> float:
    if not isinstance(content, dict):
        return 0.0
    if "_parse_error" in content:
        return 0.0

    schema = ROLE_SCHEMAS.get(role)
    if not schema:
        return 1.0

    total = len(schema)
    present = 0
    quality = 0.0

    for field, field_type in schema.items():
        val = content.get(field)
        if val is None or val == "[Not provided]":
            continue
        present += 1

        if field_type == "str" and isinstance(val, str) and len(val) > 20:
            quality += 1.0
        elif field_type == "list" and isinstance(val, list) and len(val) > 0:
            quality += 1.0
        elif field_type == "dict" and isinstance(val, dict) and len(val) > 0:
            quality += 1.0
        else:
            quality += 0.5

    completeness = present / max(total, 1)
    depth = quality / max(total, 1)

    return round((completeness * 0.6 + depth * 0.4), 2)
