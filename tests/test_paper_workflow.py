import pytest
from sqlalchemy import select

from calculus_agent.models import PaperItem, Question, QuestionDraft
from calculus_agent.papers.workflow import (
    BlueprintStateError,
    InfeasiblePaperError,
    confirm_blueprint,
    create_paper,
    get_paper,
    load_paper_preview,
    save_blueprint,
)
from calculus_agent.schemas import PaperBlueprint, SectionRequirement


def _question(session, number: int, question_type: str, difficulty: float | None = 0.5):
    draft = QuestionDraft(
        source_name="workflow", source_item_id=str(number), variant=1, subject="初中数学",
        grade="八年级", question_type=question_type, difficulty=difficulty,
        question_text=f"题目 {number}", reference_answers_json=[str(number)],
        solution_text=f"解析 {number}", normalized_fingerprint=str(number).zfill(64), status="approved",
    )
    session.add(draft)
    session.flush()
    question = Question(
        draft_id=draft.id, question_text=draft.question_text, grade="八年级",
        question_type=question_type, difficulty=difficulty, final_answer=str(number),
        solution_json={"solution_steps": [f"解析 {number}"]}, verification_status="verified",
        review_status="approved",
    )
    session.add(question)
    session.flush()
    return question


def _blueprint(seed=42):
    return PaperBlueprint(
        title="持久化测试卷", grade="八年级", total_questions=3, total_score=25,
        sections=[
            SectionRequirement(question_type="选择题", count=2, score_per_question=5, total_score=10),
            SectionRequirement(question_type="解答题", count=1, score_per_question=15, total_score=15),
        ], seed=seed,
    )


def test_unconfirmed_blueprint_cannot_create_paper(session):
    saved = save_blueprint(session, _blueprint())
    with pytest.raises(BlueprintStateError):
        create_paper(session, saved.blueprint_id)


def test_paper_items_persist_and_validate_exact_constraints(session):
    _question(session, 1, "选择题")
    _question(session, 2, "选择题")
    _question(session, 3, "解答题")
    saved = save_blueprint(session, _blueprint())
    confirm_blueprint(session, saved.blueprint_id)
    paper = create_paper(session, saved.blueprint_id)

    assert paper.status == "passed"
    assert paper.total_score == 25
    assert paper.validation_report.passed is True
    assert len(session.scalars(select(PaperItem).where(PaperItem.paper_id == paper.paper_id)).all()) == 3
    assert [item.score for item in paper.preview.items] == [5, 5, 15]


def test_saved_paper_is_single_source_for_preview_and_export(session):
    _question(session, 1, "选择题")
    _question(session, 2, "选择题")
    _question(session, 3, "解答题")
    saved = save_blueprint(session, _blueprint())
    confirm_blueprint(session, saved.blueprint_id)
    paper = create_paper(session, saved.blueprint_id)
    persisted = get_paper(session, paper.paper_id)
    export_source = load_paper_preview(session, paper.paper_id)
    assert [x.question_id for x in persisted.preview.items] == [x.question_id for x in export_source.items]


def test_infeasible_supply_returns_structured_shortage(session):
    _question(session, 1, "选择题")
    saved = save_blueprint(session, _blueprint())
    confirm_blueprint(session, saved.blueprint_id)
    with pytest.raises(InfeasiblePaperError) as raised:
        create_paper(session, saved.blueprint_id)
    assert any(item.code == "QUESTION_TYPE_SHORTAGE" for item in raised.value.violations)


def test_unknown_difficulty_is_not_selected(session):
    unknown = _question(session, 1, "选择题", None)
    known = _question(session, 2, "选择题", 0.5)
    blueprint = PaperBlueprint(
        grade="八年级", total_questions=1, total_score=5,
        sections=[SectionRequirement(question_type="选择题", count=1, score_per_question=5, total_score=5)],
    )
    saved = save_blueprint(session, blueprint)
    confirm_blueprint(session, saved.blueprint_id)
    paper = create_paper(session, saved.blueprint_id)
    assert paper.preview.items[0].question_id == known.id
    assert paper.preview.items[0].question_id != unknown.id


def test_same_seed_produces_same_order(session):
    for number in range(1, 7):
        _question(session, number, "选择题" if number <= 4 else "解答题")
    first = save_blueprint(session, _blueprint(seed=7))
    second = save_blueprint(session, _blueprint(seed=7))
    confirm_blueprint(session, first.blueprint_id)
    confirm_blueprint(session, second.blueprint_id)
    paper_a = create_paper(session, first.blueprint_id)
    paper_b = create_paper(session, second.blueprint_id)
    assert [x.question_id for x in paper_a.preview.items] == [x.question_id for x in paper_b.preview.items]
