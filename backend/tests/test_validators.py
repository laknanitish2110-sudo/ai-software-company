"""Tests for output_validator — schema validation and quality scoring."""
import pytest
from app.services.output_validator import validate_output, get_output_quality_score


def test_validate_ceo_output():
    content = {
        "project_name": "Test Project",
        "problem_analysis": "Analysis here",
        "deliverable_type": "code",
        "components": ["auth", "dashboard"],
    }
    result = validate_output("ceo", content)
    assert result["project_name"] == "Test Project"


def test_validate_fills_missing_keys():
    content = {"project_name": "Partial"}
    result = validate_output("ceo", content)
    assert "project_name" in result


def test_quality_score_range():
    content = {
        "project_name": "Test",
        "problem_analysis": "A " * 50,
        "deliverable_type": "code",
        "components": ["a", "b"],
        "recommended_approach": "Use microservices " * 10,
        "key_features": ["f1", "f2", "f3"],
    }
    score = get_output_quality_score("ceo", content)
    assert 0.0 <= score <= 1.0


def test_quality_score_empty_content():
    score = get_output_quality_score("ceo", {})
    assert score >= 0


def test_quality_score_string_content():
    score = get_output_quality_score("ceo", "raw string response")
    assert score >= 0
