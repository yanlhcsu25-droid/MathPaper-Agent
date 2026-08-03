from calculus_agent.models import KnowledgeNode, Question, QuestionDraft, QuestionKnowledgeLink
from calculus_agent.papers.selector import compose_paper
from calculus_agent.schemas import KnowledgeQuota, PaperBlueprint


def _question(session, number: int, question_type: str, knowledge: KnowledgeNode) -> Question:
    draft = QuestionDraft(
        source_name="test",
        source_item_id=str(number),
        variant=1,
        subject="初中数学",
        grade="八年级",
        question_type=question_type,
        difficulty=0.5,
        question_text=f"第 {number} 题",
        reference_answers_json=[str(number)],
        normalized_fingerprint=str(number).zfill(64),
        status="approved",
    )
    session.add(draft)
    session.flush()
    question = Question(
        draft_id=draft.id,
        question_text=draft.question_text,
        grade=draft.grade,
        question_type=question_type,
        difficulty=0.5,
        final_answer=str(number),
        solution_json={"solution_steps": [f"解析 {number}"]},
        verification_status="verified",
        review_status="approved",
    )
    session.add(question)
    session.flush()
    session.add(
        QuestionKnowledgeLink(
            question_id=question.id, knowledge_node_id=knowledge.id, relation_type="primary_concept"
        )
    )
    return question


def test_compose_paper_satisfies_explicit_constraints(session):
    knowledge = KnowledgeNode(
        node_type="concept", name="一次函数", normalized_name="一次函数", review_status="approved"
    )
    session.add(knowledge)
    session.flush()
    _question(session, 1, "选择题", knowledge)
    _question(session, 2, "选择题", knowledge)
    _question(session, 3, "解答题", knowledge)
    session.flush()

    result = compose_paper(
        session,
        PaperBlueprint(
            title="八年级测试",
            grade="八年级",
            total_questions=3,
            total_score=100,
            question_type_counts={"选择题": 2, "解答题": 1},
            knowledge_quotas=[KnowledgeQuota(name="一次函数", count=2)],
        ),
    )

    assert result.feasible is True
    assert result.total_score == 100
    assert len(result.items) == 3
    assert not result.warnings


def test_compose_paper_reports_infeasible_requirement(session):
    result = compose_paper(
        session,
        PaperBlueprint(total_questions=2, question_type_counts={"填空题": 2}),
    )
    assert result.feasible is False
    assert "未满足约束：题目总数" in result.warnings
    assert "未满足约束：题型：填空题" in result.warnings


def test_compose_paper_keeps_locked_questions_and_excludes_replaced_questions(session):
    knowledge = KnowledgeNode(
        node_type="concept", name="一次函数", normalized_name="一次函数", review_status="approved"
    )
    session.add(knowledge)
    session.flush()
    locked = _question(session, 1, "选择题", knowledge)
    excluded = _question(session, 2, "选择题", knowledge)
    replacement = _question(session, 3, "选择题", knowledge)
    session.flush()

    result = compose_paper(
        session,
        PaperBlueprint(
            grade="八年级",
            total_questions=2,
            locked_question_ids=[locked.id],
            excluded_question_ids=[excluded.id],
        ),
    )

    ids = [item.question_id for item in result.items]
    assert ids[0] == locked.id
    assert replacement.id in ids
    assert excluded.id not in ids
    assert result.feasible is True


def test_compose_paper_reports_missing_locked_question(session):
    result = compose_paper(
        session,
        PaperBlueprint(total_questions=1, locked_question_ids=["missing-question"]),
    )

    assert result.feasible is False
    assert "未满足约束：指定题目" in result.warnings


def test_compose_paper_applies_manual_order_and_score_override(session):
    knowledge = KnowledgeNode(
        node_type="concept", name="一次函数", normalized_name="一次函数", review_status="approved"
    )
    session.add(knowledge)
    session.flush()
    first = _question(session, 1, "选择题", knowledge)
    second = _question(session, 2, "解答题", knowledge)
    third = _question(session, 3, "填空题", knowledge)
    session.flush()

    result = compose_paper(
        session,
        PaperBlueprint(
            grade="八年级",
            total_questions=3,
            total_score=100,
            manual_question_ids=[first.id],
            question_order=[third.id, first.id, second.id],
            score_overrides={first.id: 20},
        ),
    )

    assert [item.question_id for item in result.items] == [third.id, first.id, second.id]
    assert [item.score for item in result.items] == [40, 20, 40]
    assert result.feasible is True
