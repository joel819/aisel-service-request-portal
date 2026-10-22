import json
from pathlib import Path

import pytest

from app.config import get_settings
from evals import run_evals


@pytest.fixture(autouse=True)
def use_mock_model(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(get_settings(), "llm_provider", "mock")


def test_shipped_testset_passes_the_gate(capsys: pytest.CaptureFixture[str]) -> None:
    assert run_evals.main([]) == 0

    summary = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert summary["cases"] == 10 and summary["pass_rate"] == 1.0
    assert summary["critical_failures"] == []


def test_gate_fails_when_a_critical_case_fails(tmp_path: Path) -> None:
    cases = [json.loads(line) for line in run_evals.TESTSET.read_text().splitlines()]
    cases[4]["expected_ids"] = [10]
    cases[4]["must_not_include"] = []
    bad = tmp_path / "bad.jsonl"
    bad.write_text("\n".join(json.dumps(c) for c in cases))

    assert run_evals.main(["--testset", str(bad)]) == 1


def test_gate_fails_below_the_pass_rate(tmp_path: Path) -> None:
    cases = [json.loads(line) for line in run_evals.TESTSET.read_text().splitlines()]
    for case in cases[:3]:
        case["expected_ids"] = [999]
        case["critical"] = False
    bad = tmp_path / "bad.jsonl"
    bad.write_text("\n".join(json.dumps(c) for c in cases))

    assert run_evals.main(["--testset", str(bad), "--min-pass", "0.9"]) == 1
    assert run_evals.main(["--testset", str(bad), "--min-pass", "0.5"]) == 0


def test_every_case_has_the_fields_the_grader_needs() -> None:
    for line in run_evals.TESTSET.read_text().splitlines():
        case = json.loads(line)
        assert {"id", "critical", "as", "kind", "question", "expected_ids"} <= case.keys()
        assert case["as"] in {"admin", "alice", "bob"}
