import json
from pathlib import Path

import pytest
from fastapi import HTTPException

from console.backend.main import verify


DEMO_DIR = Path(__file__).parents[1] / "console" / "frontend" / "public" / "demo"


@pytest.mark.parametrize(
    ("artifact", "boundary"),
    (("rein.json", "autonomous"), ("rein-003.json", "unsafe_failure")),
)
def test_verify_calls_existing_judge_for_demo_artifact(artifact, boundary):
    payload = json.loads((DEMO_DIR / artifact).read_text(encoding="utf-8"))

    result = verify(payload)

    assert result["source"] == "evidence"
    assert result["verdict"]["boundary"] == boundary
    assert result["scope_map"]["source"] == "judge"
    assert result["scope_map"]["boundary"] == boundary
    active_zones = [key for key, zone in result["scope_map"]["zones"].items() if zone["active"]]
    assert active_zones == (["autonomous"] if boundary == "autonomous" else ["blocked"])
    assert result["evidence"]
    assert result["events"]


def test_verify_accepts_tau2_artifact_shape():
    payload = {"simulations": [{"reward_info": {"reward": 1.0, "action_checks": []}, "messages": []}]}

    result = verify(payload)

    assert result["source"] == "tau2_artifact"
    assert result["verdict"]["boundary"] == "autonomous"


def test_verify_rejects_unknown_payload():
    with pytest.raises(HTTPException) as error:
        verify({"scenario": "REIN-RETAIL-001"})

    assert error.value.status_code == 422


def test_verify_rejects_evidence_without_type():
    with pytest.raises(HTTPException) as error:
        verify({"evidence": [{"observed": True}]})

    assert error.value.status_code == 422
