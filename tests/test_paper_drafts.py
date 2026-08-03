import pytest

from calculus_agent.models import KnowledgeNode
from calculus_agent.papers.drafts import (
    PaperDraftNotFoundError,
    compare_paper_drafts,
    get_paper_draft,
    list_paper_drafts,
    save_paper_draft,
)
from calculus_agent.schemas import PaperBlueprint

from test_paper_selector import _question


def test_save_and_reload_paper_draft_preserves_blueprint_and_preview(session):
    knowledge = KnowledgeNode(
        node_type="concept", name="一次函数", normalized_name="一次函数", review_status="approved"
    )
    session.add(knowledge)
    session.flush()
    question = _question(session, 1, "选择题", knowledge)
    session.flush()
    blueprint = PaperBlueprint(
        title="一次函数测试",
        grade="八年级",
        total_questions=1,
        locked_question_ids=[question.id],
        excluded_question_ids=["previous-question"],
    )

    saved = save_paper_draft(session, blueprint)
    loaded = get_paper_draft(session, saved.id)

    assert loaded.blueprint == blueprint
    assert loaded.preview.items[0].question_id == question.id
    assert list_paper_drafts(session)[0].id == saved.id


def test_save_paper_draft_version_links_to_parent(session):
    original = save_paper_draft(session, PaperBlueprint(total_questions=1))
    revision = save_paper_draft(
        session,
        PaperBlueprint(title="第二版", total_questions=1),
        parent_id=original.id,
    )
    assert revision.parent_id == original.id


def test_save_paper_draft_rejects_unknown_parent(session):
    with pytest.raises(PaperDraftNotFoundError):
        save_paper_draft(
            session,
            PaperBlueprint(total_questions=1),
            parent_id="missing",
        )


def test_compare_paper_drafts_reports_replacement_order_and_score(session):
    knowledge = KnowledgeNode(
        node_type="concept", name="一次函数", normalized_name="一次函数", review_status="approved"
    )
    session.add(knowledge)
    session.flush()
    first = _question(session, 1, "选择题", knowledge)
    second = _question(session, 2, "选择题", knowledge)
    third = _question(session, 3, "选择题", knowledge)
    session.flush()
    original = save_paper_draft(
        session,
        PaperBlueprint(
            total_questions=2,
            manual_question_ids=[first.id, second.id],
            question_order=[first.id, second.id],
        ),
    )
    revision = save_paper_draft(
        session,
        PaperBlueprint(
            total_questions=2,
            manual_question_ids=[second.id, third.id],
            question_order=[second.id, third.id],
            score_overrides={second.id: 40},
        ),
        parent_id=original.id,
    )

    diff = compare_paper_drafts(session, revision.id)

    assert [item.question_id for item in diff.added] == [third.id]
    assert [item.question_id for item in diff.removed] == [first.id]
    assert any(item.question_id == second.id for item in diff.order_changes)
    assert any(item.question_id == second.id for item in diff.score_changes)
    assert diff.has_changes is True
