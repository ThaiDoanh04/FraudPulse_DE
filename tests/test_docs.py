"""Structural checks for the SPEC and ADRs (Task 0.1 acceptance criteria).

These tests guard the shape of the documentation, not its wording: every ADR
follows the same template so readers (and interviewers) can scan them quickly.
"""

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
DECISIONS = ROOT / "docs" / "decisions"
SPEC = ROOT / "docs" / "SPEC.md"

ADR_SECTIONS = ["Trạng thái", "Ngày", "Bối cảnh", "Quyết định", "Các phương án đã cân nhắc", "Hệ quả"]
SPEC_SECTIONS = ["Bài toán", "Phạm vi", "Dữ liệu", "Chỉ số thành công", "Kiến trúc", "Ngoài phạm vi"]
EXPECTED_ADRS = 7


def adr_files() -> list[Path]:
    return sorted(DECISIONS.glob("ADR-[0-9][0-9][0-9]-*.md"))


def h2_headings(text: str) -> list[str]:
    return re.findall(r"^## (.+?)\s*$", text, flags=re.MULTILINE)


def test_spec_has_required_sections():
    headings = h2_headings(SPEC.read_text(encoding="utf-8"))
    missing = [s for s in SPEC_SECTIONS if s not in headings]
    assert not missing, f"SPEC.md missing sections: {missing}"


def test_spec_states_measurable_targets():
    text = SPEC.read_text(encoding="utf-8")
    for metric in ["PR-AUC", "Recall@1%FPR", "p99", "req/s"]:
        assert metric in text, f"SPEC.md does not state a target for {metric}"


def test_expected_number_of_adrs_numbered_sequentially():
    numbers = [int(p.name[4:7]) for p in adr_files()]
    assert numbers == list(range(1, EXPECTED_ADRS + 1))


@pytest.mark.parametrize("path", adr_files(), ids=lambda p: p.name)
def test_adr_follows_template(path: Path):
    text = path.read_text(encoding="utf-8")
    assert text.startswith(f"# ADR-{path.name[4:7]}: "), "title must match file number"
    headings = h2_headings(text)
    assert headings[: len(ADR_SECTIONS)] == ADR_SECTIONS, f"sections out of template order: {headings}"


@pytest.mark.parametrize("path", adr_files(), ids=lambda p: p.name)
def test_adr_is_accepted_and_considers_alternatives(path: Path):
    text = path.read_text(encoding="utf-8")
    status = text.split("## Trạng thái", 1)[1].split("##", 1)[0].strip()
    assert status == "Đã chấp nhận"
    alternatives = text.split("## Các phương án đã cân nhắc", 1)[1].split("\n## ", 1)[0]
    assert len(re.findall(r"^### ", alternatives, flags=re.MULTILINE)) >= 2, "need at least 2 alternatives"


def test_decision_index_lists_every_adr():
    index = (DECISIONS / "README.md").read_text(encoding="utf-8")
    for path in adr_files():
        assert path.name in index, f"{path.name} not linked from docs/decisions/README.md"
