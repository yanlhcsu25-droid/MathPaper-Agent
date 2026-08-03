import random
from collections import Counter

from sqlalchemy import select
from sqlalchemy.orm import Session

from calculus_agent.models import KnowledgeNode, Question, QuestionKnowledgeLink
from calculus_agent.schemas import ConstraintCheck, PaperBlueprint, PaperItemRead, PaperPreviewRead


def compose_paper(session: Session, blueprint: PaperBlueprint) -> PaperPreviewRead:
    rows = _candidates(session, blueprint)
    random.Random(blueprint.seed).shuffle(rows)
    selected: list[tuple[Question, list[str]]] = []
    used: set[str] = set()
    rows_by_id = {row[0].id: row for row in rows}

    required_ids = list(dict.fromkeys([*blueprint.locked_question_ids, *blueprint.manual_question_ids]))
    missing_required: list[str] = []
    for question_id in required_ids:
        row = rows_by_id.get(question_id)
        if row is None:
            missing_required.append(question_id)
            continue
        selected.append(row)
        used.add(question_id)

    def take(predicate, count: int) -> None:
        for row in rows:
            if len([item for item in selected if predicate(item)]) >= count:
                return
            if row[0].id not in used and predicate(row):
                selected.append(row)
                used.add(row[0].id)

    for quota in blueprint.knowledge_quotas:
        take(lambda row, name=quota.name: name in row[1], quota.count)
    for question_type, count in blueprint.question_type_counts.items():
        take(lambda row, value=question_type: row[0].question_type == value, count)
    take(lambda _: True, blueprint.total_questions)

    selected = selected[: blueprint.total_questions]
    if blueprint.question_order:
        order = {question_id: index for index, question_id in enumerate(blueprint.question_order)}
        original = {row[0].id: index for index, row in enumerate(selected)}
        selected.sort(key=lambda row: (order.get(row[0].id, len(order)), original[row[0].id]))
    scores = _allocate_scores(
        [question.id for question, _ in selected],
        blueprint.total_score,
        blueprint.score_overrides,
    )
    items = [
        _item(question, knowledge, score) for (question, knowledge), score in zip(selected, scores)
    ]
    checks = _checks(blueprint, items, missing_required)
    warnings = [f"未满足约束：{check.name}" for check in checks if not check.satisfied]
    return PaperPreviewRead(
        title=blueprint.title,
        total_score=sum(item.score for item in items),
        items=items,
        constraints=checks,
        warnings=warnings,
        feasible=all(check.satisfied for check in checks),
    )


def _candidates(session: Session, blueprint: PaperBlueprint):
    statement = select(Question).where(Question.review_status == "approved")
    if blueprint.excluded_question_ids:
        statement = statement.where(Question.id.not_in(blueprint.excluded_question_ids))
    if blueprint.grade:
        statement = statement.where(Question.grade == blueprint.grade)
    statement = statement.where(
        Question.difficulty.is_(None)
        | Question.difficulty.between(blueprint.difficulty_min, blueprint.difficulty_max)
    )
    questions = list(session.scalars(statement).all())
    result = []
    for question in questions:
        names = list(
            session.scalars(
                select(KnowledgeNode.name)
                .join(
                    QuestionKnowledgeLink,
                    QuestionKnowledgeLink.knowledge_node_id == KnowledgeNode.id,
                )
                .where(QuestionKnowledgeLink.question_id == question.id)
            ).all()
        )
        result.append((question, names))
    return result


def _allocate_scores(
    question_ids: list[str],
    total: int,
    overrides: dict[str, int],
) -> list[int]:
    if not question_ids:
        return []
    applicable = {question_id: overrides[question_id] for question_id in question_ids if question_id in overrides}
    flexible = [question_id for question_id in question_ids if question_id not in applicable]
    remaining = total - sum(applicable.values())
    if not flexible:
        return [applicable[question_id] for question_id in question_ids]
    base, remainder = divmod(remaining, len(flexible))
    allocated = {
        question_id: base + (1 if index < remainder else 0)
        for index, question_id in enumerate(flexible)
    }
    return [
        applicable[question_id] if question_id in applicable else allocated[question_id]
        for question_id in question_ids
    ]


def _item(question: Question, knowledge: list[str], score: int) -> PaperItemRead:
    steps = question.solution_json.get("solution_steps", []) if question.solution_json else []
    return PaperItemRead(
        question_id=question.id,
        question_text=question.question_text,
        question_type=question.question_type,
        difficulty=question.difficulty,
        score=score,
        knowledge=knowledge,
        final_answer=question.final_answer,
        solution_steps=steps,
    )


def _checks(
    blueprint: PaperBlueprint,
    items: list[PaperItemRead],
    missing_required: list[str],
) -> list[ConstraintCheck]:
    type_counts = Counter(item.question_type for item in items)
    knowledge_counts = Counter(name for item in items for name in item.knowledge)
    checks = [
        ConstraintCheck(
            name="题目总数",
            required=blueprint.total_questions,
            actual=len(items),
            satisfied=len(items) == blueprint.total_questions,
        ),
        ConstraintCheck(
            name="试卷总分",
            required=blueprint.total_score,
            actual=sum(item.score for item in items),
            satisfied=len(items) == blueprint.total_questions
            and sum(item.score for item in items) == blueprint.total_score,
        ),
        ConstraintCheck(
            name="指定题目",
            required=len(set(blueprint.locked_question_ids) | set(blueprint.manual_question_ids)),
            actual=len(set(blueprint.locked_question_ids) | set(blueprint.manual_question_ids))
            - len(missing_required),
            satisfied=not missing_required,
        ),
    ]
    for question_type, required in blueprint.question_type_counts.items():
        actual = type_counts[question_type]
        checks.append(
            ConstraintCheck(
                name=f"题型：{question_type}",
                required=required,
                actual=actual,
                satisfied=actual >= required,
            )
        )
    for quota in blueprint.knowledge_quotas:
        actual = knowledge_counts[quota.name]
        checks.append(
            ConstraintCheck(
                name=f"知识点：{quota.name}",
                required=quota.count,
                actual=actual,
                satisfied=actual >= quota.count,
            )
        )
    return checks
