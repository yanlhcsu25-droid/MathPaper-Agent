import json

from sqlalchemy import select

from calculus_agent.datasets.mm_math import import_mm_math
from calculus_agent.models import KnowledgeNode, Question, QuestionDraft


def test_import_mm_math_jsonl(session, tmp_path):
    path = tmp_path / "middle.jsonl"
    rows = [
        {
            "id": "m1",
            "question": "若 x+2=5，求 x。",
            "solution": "移项得 x=5-2=3，因此答案：3。",
            "grade": "七年级",
            "difficult": 1,
            "knowledge": ["一元一次方程"],
        },
        {"id": "invalid", "question": "缺少解析"},
    ]
    path.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False) for row in rows), encoding="utf-8"
    )

    summary = import_mm_math(session, path)

    assert summary.created == 1
    assert summary.skipped == 1
    draft = session.scalar(select(QuestionDraft))
    assert draft is not None
    assert draft.subject == "初中数学"
    assert draft.grade == "七年级"
    assert draft.difficulty == 0.25
    assert draft.keywords_json == ["一元一次方程"]
    assert session.scalar(select(Question)) is not None
    assert session.scalar(select(KnowledgeNode)).name == "一元一次方程"


def test_import_mm_math_is_idempotent(session, tmp_path):
    path = tmp_path / "middle.json"
    path.write_text(
        json.dumps(
            [{"id": "m1", "question": "计算 1+1。", "solution": "答案：2。"}], ensure_ascii=False
        ),
        encoding="utf-8",
    )
    assert import_mm_math(session, path).created == 1
    assert import_mm_math(session, path).existing == 1
