from collections import Counter
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from calculus_agent.models import (
    ConstraintViolation,
    KnowledgeNode,
    Paper,
    PaperBlueprintRecord,
    PaperItem,
    Question,
    QuestionDraft,
    QuestionKnowledgeLink,
    ValidationReport,
)
from calculus_agent.papers.selector import compose_paper
from calculus_agent.schemas import (
    BlueprintCreateRead,
    ConstraintCheck,
    ConstraintViolationRead,
    PaperBlueprint,
    PaperItemRead,
    PaperPreviewRead,
    SavedPaperRead,
    ValidationReportRead,
)


class WorkflowNotFoundError(LookupError):
    pass


class BlueprintStateError(ValueError):
    pass


class InfeasiblePaperError(ValueError):
    def __init__(self, violations: list[ConstraintViolationRead]):
        self.violations = violations
        super().__init__("题库无法满足组卷约束")


def save_blueprint(session: Session, blueprint: PaperBlueprint) -> BlueprintCreateRead:
    record = PaperBlueprintRecord(
        title=blueprint.title, blueprint_json=blueprint.model_dump(mode="json"), status="draft"
    )
    session.add(record)
    session.flush()
    return _blueprint_read(record)


def get_blueprint(session: Session, blueprint_id: str) -> BlueprintCreateRead:
    record = session.get(PaperBlueprintRecord, blueprint_id)
    if record is None:
        raise WorkflowNotFoundError("Blueprint not found")
    return _blueprint_read(record)


def update_blueprint(
    session: Session, blueprint_id: str, blueprint: PaperBlueprint
) -> BlueprintCreateRead:
    record = session.get(PaperBlueprintRecord, blueprint_id)
    if record is None:
        raise WorkflowNotFoundError("Blueprint not found")
    if record.status != "draft":
        raise BlueprintStateError("只有草稿蓝图可以修改")
    record.title = blueprint.title
    record.blueprint_json = blueprint.model_dump(mode="json")
    record.updated_at = datetime.now(UTC)
    session.flush()
    return _blueprint_read(record)


def confirm_blueprint(session: Session, blueprint_id: str) -> BlueprintCreateRead:
    record = session.get(PaperBlueprintRecord, blueprint_id)
    if record is None:
        raise WorkflowNotFoundError("Blueprint not found")
    if record.status != "draft":
        raise BlueprintStateError("蓝图已确认或已使用")
    # Revalidation ensures persisted JSON still obeys every hard rule.
    PaperBlueprint.model_validate(record.blueprint_json)
    record.status = "confirmed"
    record.updated_at = datetime.now(UTC)
    session.flush()
    return _blueprint_read(record)


def create_paper(session: Session, blueprint_id: str) -> SavedPaperRead:
    record = session.get(PaperBlueprintRecord, blueprint_id)
    if record is None:
        raise WorkflowNotFoundError("Blueprint not found")
    if record.status != "confirmed":
        raise BlueprintStateError("只有已确认的蓝图才能组卷")
    blueprint = PaperBlueprint.model_validate(record.blueprint_json)
    preview = compose_paper(session, blueprint)
    if not preview.feasible:
        raise InfeasiblePaperError(_constraint_violations(preview.constraints))
    version = (session.scalar(select(func.count(Paper.id)).where(Paper.blueprint_id == record.id)) or 0) + 1
    paper = Paper(
        blueprint_id=record.id,
        version=version,
        status="validating",
        title=blueprint.title,
        total_score=preview.total_score,
        validation_status="pending",
    )
    session.add(paper)
    session.flush()
    locked = set(blueprint.locked_question_ids)
    for position, item in enumerate(preview.items, 1):
        session.add(PaperItem(
            paper_id=paper.id,
            question_id=item.question_id,
            section=item.question_type,
            position=position,
            score=item.score,
            locked=item.question_id in locked,
        ))
    record.status = "used"
    session.flush()
    report = validate_paper(session, paper.id)
    return _paper_read(session, paper, report)


def get_paper(session: Session, paper_id: str) -> SavedPaperRead:
    paper = session.get(Paper, paper_id)
    if paper is None:
        raise WorkflowNotFoundError("Paper not found")
    report = session.scalar(
        select(ValidationReport)
        .where(ValidationReport.paper_id == paper.id)
        .order_by(ValidationReport.created_at.desc())
    )
    if report is None:
        report_read = validate_paper(session, paper.id)
    else:
        report_read = _report_read(session, report)
    return _paper_read(session, paper, report_read)


def load_paper_preview(session: Session, paper_id: str) -> PaperPreviewRead:
    paper = session.get(Paper, paper_id)
    if paper is None:
        raise WorkflowNotFoundError("Paper not found")
    items = _items(session, paper.id)
    return PaperPreviewRead(
        title=paper.title,
        total_score=sum(item.score for item in items),
        items=items,
        constraints=[],
        warnings=[],
        feasible=paper.validation_status == "passed",
    )


def validate_paper(session: Session, paper_id: str) -> ValidationReportRead:
    paper = session.get(Paper, paper_id)
    if paper is None:
        raise WorkflowNotFoundError("Paper not found")
    record = session.get(PaperBlueprintRecord, paper.blueprint_id)
    blueprint = PaperBlueprint.model_validate(record.blueprint_json)
    items = _items(session, paper.id)
    violations: list[ConstraintViolationRead] = []
    def add(code, field, required, actual, message, question_ids=None, repairable=True):
        if required != actual:
            violations.append(ConstraintViolationRead(
                code=code, field=field, required=required, actual=actual,
                question_ids=question_ids or [], repairable=repairable, message=message,
            ))
    add("QUESTION_COUNT_MISMATCH", "total_questions", blueprint.total_questions, len(items), "题目总数不符")
    add("TOTAL_SCORE_MISMATCH", "total_score", blueprint.total_score, sum(x.score for x in items), "试卷总分不符")
    counts = Counter(item.question_type for item in items)
    for question_type, required in blueprint.question_type_counts.items():
        add("QUESTION_TYPE_COUNT_MISMATCH", question_type, required, counts[question_type], f"{question_type}数量不符")
    for section in blueprint.sections:
        actual = sum(item.score for item in items if item.question_type == section.question_type)
        add("SECTION_SCORE_MISMATCH", section.question_type, section.total_score, actual, f"{section.question_type}部分分值不符")
    knowledge = Counter(name for item in items for name in item.knowledge)
    for quota in blueprint.knowledge_quotas:
        if knowledge[quota.name] < quota.count:
            violations.append(ConstraintViolationRead(code="KNOWLEDGE_SHORTAGE", field=quota.name, required=quota.count, actual=knowledge[quota.name], question_ids=[], repairable=True, message=f"{quota.name}覆盖不足"))
    ids = [item.question_id for item in items]
    duplicates = [question_id for question_id, count in Counter(ids).items() if count > 1]
    add("DUPLICATE_QUESTION", "question_id", 0, len(duplicates), "试卷包含重复题目", duplicates)
    missing_answers = [item.question_id for item in items if not item.final_answer]
    missing_solutions = [item.question_id for item in items if not item.solution_steps]
    add("ANSWER_MISSING", "final_answer", 0, len(missing_answers), "题目缺少答案", missing_answers)
    add("SOLUTION_MISSING", "solution", 0, len(missing_solutions), "题目缺少解析", missing_solutions)
    excluded = [item.question_id for item in items if item.question_id in blueprint.excluded_question_ids]
    add("EXCLUDED_QUESTION_INCLUDED", "excluded_question_ids", 0, len(excluded), "包含已排除题目", excluded)
    excluded_topics = [item.question_id for item in items if set(item.knowledge).intersection(blueprint.excluded_topics)]
    add("EXCLUDED_TOPIC_INCLUDED", "excluded_topics", 0, len(excluded_topics), "包含已排除知识点", excluded_topics)
    invalid_difficulty = [item.question_id for item in items if item.difficulty is None or not blueprint.difficulty_min <= item.difficulty <= blueprint.difficulty_max]
    add("DIFFICULTY_OUT_OF_RANGE", "difficulty", 0, len(invalid_difficulty), "题目难度不符合蓝图", invalid_difficulty)
    report = ValidationReport(paper_id=paper.id, passed=not violations)
    session.add(report)
    session.flush()
    for violation in violations:
        session.add(ConstraintViolation(
            report_id=report.id, code=violation.code, field=violation.field,
            required_json=violation.required, actual_json=violation.actual,
            question_ids_json=violation.question_ids, repairable=violation.repairable,
            message=violation.message,
        ))
    paper.status = "passed" if report.passed else "failed"
    paper.validation_status = "passed" if report.passed else "failed"
    session.flush()
    return ValidationReportRead(id=report.id, paper_id=paper.id, passed=report.passed, violations=violations, created_at=report.created_at)


def _items(session: Session, paper_id: str) -> list[PaperItemRead]:
    records = session.scalars(select(PaperItem).where(PaperItem.paper_id == paper_id).order_by(PaperItem.position)).all()
    result = []
    for item in records:
        question = session.get(Question, item.question_id)
        knowledge = list(session.scalars(select(KnowledgeNode.name).join(QuestionKnowledgeLink, QuestionKnowledgeLink.knowledge_node_id == KnowledgeNode.id).where(QuestionKnowledgeLink.question_id == question.id)).all())
        draft = session.get(QuestionDraft, question.draft_id)
        result.append(PaperItemRead(
            question_id=question.id, question_text=question.question_text,
            question_type=item.section, difficulty=question.difficulty, score=item.score,
            knowledge=knowledge, final_answer=question.final_answer,
            solution_steps=(question.solution_json or {}).get("solution_steps", []),
            has_image=bool(draft and draft.image_path),
        ))
    return result


def _constraint_violations(checks: list[ConstraintCheck]) -> list[ConstraintViolationRead]:
    codes = {"题目总数": "QUESTION_COUNT_SHORTAGE", "试卷总分": "TOTAL_SCORE_MISMATCH", "指定题目": "REQUIRED_QUESTION_MISSING", "图片题数量": "IMAGE_QUESTION_SHORTAGE"}
    result = []
    for check in checks:
        if check.satisfied:
            continue
        field = check.name.split("：", 1)[-1]
        code = "QUESTION_TYPE_SHORTAGE" if check.name.startswith("题型：") else "KNOWLEDGE_SHORTAGE" if check.name.startswith("知识点：") else codes.get(check.name, "CONSTRAINT_UNSATISFIED")
        result.append(ConstraintViolationRead(code=code, field=field, required=check.required, actual=check.actual, question_ids=[], repairable=True, message=f"{check.name}无法满足"))
    return result


def _blueprint_read(record: PaperBlueprintRecord) -> BlueprintCreateRead:
    return BlueprintCreateRead(blueprint_id=record.id, status=record.status, blueprint=PaperBlueprint.model_validate(record.blueprint_json))


def _report_read(session: Session, report: ValidationReport) -> ValidationReportRead:
    values = session.scalars(select(ConstraintViolation).where(ConstraintViolation.report_id == report.id)).all()
    return ValidationReportRead(id=report.id, paper_id=report.paper_id, passed=report.passed, created_at=report.created_at, violations=[ConstraintViolationRead(code=x.code, field=x.field, required=x.required_json, actual=x.actual_json, question_ids=x.question_ids_json, repairable=x.repairable, message=x.message) for x in values])


def _paper_read(session: Session, paper: Paper, report: ValidationReportRead) -> SavedPaperRead:
    return SavedPaperRead(paper_id=paper.id, blueprint_id=paper.blueprint_id, version=paper.version, status=paper.status, total_score=paper.total_score, validation_status=paper.validation_status, preview=load_paper_preview(session, paper.id), validation_report=report, created_at=paper.created_at)
