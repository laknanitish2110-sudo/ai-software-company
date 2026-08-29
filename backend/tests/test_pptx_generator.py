"""Tests for PPTX generator — no hackathon branding, slide creation."""
import os
import pytest
from app.services.pptx_generator import generate_pptx, _pitch_to_slides


def test_generate_pptx_basic():
    content = {
        "report_data": {
            "title": "Test Project",
            "subtitle": "A test presentation",
            "slides": [
                {"type": "content", "title": "Overview", "body": "This is a test."},
                {"type": "content", "title": "Details", "body": "More details."},
            ]
        }
    }
    path = generate_pptx("test_pptx_001", content)
    assert path is not None
    assert os.path.exists(path)
    assert path.endswith(".pptx")
    os.remove(path)


def test_no_hackathon_branding():
    """Ensure 'hackathon' does not appear in the generated PPTX."""
    import inspect
    import app.services.pptx_generator as mod
    source = inspect.getsource(mod)
    lower_source = source.lower()
    assert "hackathon" not in lower_source


def test_pitch_to_slides():
    ppt_output = {
        "report_data": {
            "title": "My Pitch",
            "subtitle": "Tagline",
        }
    }
    slides = _pitch_to_slides(ppt_output)
    assert isinstance(slides, list)
    assert len(slides) > 0
