import uuid
from datetime import UTC, datetime

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from calculus_agent.db import Base


def new_id() -> str:
    return str(uuid.uuid4())


class CurriculumNode(Base):
    __tablename__ = "curriculum_node"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    parent_id: Mapped[str | None] = mapped_column(
        ForeignKey("curriculum_node.id"), nullable=True, index=True
    )
    node_type: Mapped[str] = mapped_column(String(30), index=True)
    code: Mapped[str | None] = mapped_column(String(40), nullable=True)
    title: Mapped[str] = mapped_column(String(255), index=True)
    sort_order: Mapped[int] = mapped_column(Integer)
    source: Mapped[str] = mapped_column(String(80), default="teacher_directory")
    review_status: Mapped[str] = mapped_column(String(30), default="approved", index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )


class KnowledgeNode(Base):
    __tablename__ = "knowledge_node"
    __table_args__ = (UniqueConstraint("node_type", "normalized_name"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    curriculum_node_id: Mapped[str | None] = mapped_column(
        ForeignKey("curriculum_node.id"), nullable=True, index=True
    )
    node_type: Mapped[str] = mapped_column(String(30), index=True)
    name: Mapped[str] = mapped_column(String(255), index=True)
    normalized_name: Mapped[str] = mapped_column(String(255), index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_type: Mapped[str] = mapped_column(String(40), default="directory")
    confidence: Mapped[float] = mapped_column(Float, default=1.0)
    review_status: Mapped[str] = mapped_column(String(30), default="approved", index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )


class KnowledgeAlias(Base):
    __tablename__ = "knowledge_alias"
    __table_args__ = (UniqueConstraint("node_id", "normalized_alias"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    node_id: Mapped[str] = mapped_column(ForeignKey("knowledge_node.id"), index=True)
    alias: Mapped[str] = mapped_column(String(255), index=True)
    normalized_alias: Mapped[str] = mapped_column(String(255), index=True)


class QuestionDraft(Base):
    __tablename__ = "question_draft"
    __table_args__ = (UniqueConstraint("source_name", "source_item_id", "variant"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    source_name: Mapped[str] = mapped_column(String(80), index=True)
    source_item_id: Mapped[str] = mapped_column(String(120), index=True)
    variant: Mapped[int] = mapped_column(Integer, default=1)
    subject: Mapped[str] = mapped_column(String(120), index=True)
    language: Mapped[str] = mapped_column(String(20), default="zh-CN", index=True)
    grade: Mapped[str | None] = mapped_column(String(40), nullable=True, index=True)
    question_type: Mapped[str] = mapped_column(String(40), default="解答题", index=True)
    difficulty: Mapped[float | None] = mapped_column(Float, nullable=True, index=True)
    source_topic: Mapped[str | None] = mapped_column(String(255), nullable=True)
    source_subtopic: Mapped[str | None] = mapped_column(String(255), nullable=True)
    question_text: Mapped[str] = mapped_column(Text)
    reference_answers_json: Mapped[list] = mapped_column(JSON, default=list)
    answer_types_json: Mapped[list] = mapped_column(JSON, default=list)
    options_json: Mapped[list] = mapped_column(JSON, default=list)
    solution_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    image_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    level: Mapped[str | None] = mapped_column(String(20), nullable=True)
    keywords_json: Mapped[list] = mapped_column(JSON, default=list)
    normalized_fingerprint: Mapped[str] = mapped_column(String(64), index=True)
    status: Mapped[str] = mapped_column(String(30), default="pending", index=True)
    proposed_classification_json: Mapped[dict] = mapped_column(JSON, default=dict)
    solver_result_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    verification_result_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )


class Question(Base):
    __tablename__ = "question"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    draft_id: Mapped[str] = mapped_column(ForeignKey("question_draft.id"), unique=True, index=True)
    question_text: Mapped[str] = mapped_column(Text)
    grade: Mapped[str | None] = mapped_column(String(40), nullable=True, index=True)
    question_type: Mapped[str] = mapped_column(String(40), default="解答题", index=True)
    difficulty: Mapped[float | None] = mapped_column(Float, nullable=True, index=True)
    default_score: Mapped[int] = mapped_column(Integer, default=10)
    final_answer: Mapped[str | None] = mapped_column(Text, nullable=True)
    solution_json: Mapped[dict] = mapped_column(JSON, default=dict)
    verification_status: Mapped[str] = mapped_column(String(30), index=True)
    review_status: Mapped[str] = mapped_column(String(30), default="approved", index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )


class QuestionKnowledgeLink(Base):
    __tablename__ = "question_knowledge_link"
    __table_args__ = (UniqueConstraint("question_id", "knowledge_node_id", "relation_type"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    question_id: Mapped[str] = mapped_column(ForeignKey("question.id"), index=True)
    knowledge_node_id: Mapped[str] = mapped_column(ForeignKey("knowledge_node.id"), index=True)
    relation_type: Mapped[str] = mapped_column(String(40), index=True)
    confidence: Mapped[float] = mapped_column(Float, default=1.0)
    evidence_json: Mapped[list] = mapped_column(JSON, default=list)


class PaperDraft(Base):
    __tablename__ = "paper_draft"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    parent_id: Mapped[str | None] = mapped_column(
        ForeignKey("paper_draft.id"), nullable=True, index=True
    )
    title: Mapped[str] = mapped_column(String(255), index=True)
    blueprint_json: Mapped[dict] = mapped_column(JSON)
    preview_json: Mapped[dict] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(30), default="draft", index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), index=True
    )


class PaperBlueprintRecord(Base):
    __tablename__ = "paper_blueprint"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    title: Mapped[str] = mapped_column(String(255), index=True)
    blueprint_json: Mapped[dict] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(20), default="draft", index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )


class Paper(Base):
    __tablename__ = "paper"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    blueprint_id: Mapped[str] = mapped_column(ForeignKey("paper_blueprint.id"), index=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(20), default="draft", index=True)
    title: Mapped[str] = mapped_column(String(255))
    total_score: Mapped[int] = mapped_column(Integer)
    validation_status: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), index=True
    )


class PaperItem(Base):
    __tablename__ = "paper_item"
    __table_args__ = (
        UniqueConstraint("paper_id", "question_id"),
        UniqueConstraint("paper_id", "position"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    paper_id: Mapped[str] = mapped_column(ForeignKey("paper.id"), index=True)
    question_id: Mapped[str] = mapped_column(ForeignKey("question.id"), index=True)
    section: Mapped[str] = mapped_column(String(40))
    position: Mapped[int] = mapped_column(Integer)
    score: Mapped[int] = mapped_column(Integer)
    locked: Mapped[bool] = mapped_column(default=False)


class ValidationReport(Base):
    __tablename__ = "validation_report"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    paper_id: Mapped[str] = mapped_column(ForeignKey("paper.id"), index=True)
    passed: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), index=True
    )


class ConstraintViolation(Base):
    __tablename__ = "constraint_violation"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    report_id: Mapped[str] = mapped_column(ForeignKey("validation_report.id"), index=True)
    code: Mapped[str] = mapped_column(String(80), index=True)
    field: Mapped[str] = mapped_column(String(255))
    required_json: Mapped[object] = mapped_column(JSON)
    actual_json: Mapped[object] = mapped_column(JSON)
    question_ids_json: Mapped[list] = mapped_column(JSON, default=list)
    repairable: Mapped[bool] = mapped_column(default=True)
    message: Mapped[str] = mapped_column(Text)


class MistakePrepTask(Base):
    __tablename__ = "mistake_prep_task"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    grade: Mapped[str | None] = mapped_column(String(40), nullable=True, index=True)
    question_text: Mapped[str] = mapped_column(Text)
    final_answer: Mapped[str] = mapped_column(Text)
    solution_text: Mapped[str] = mapped_column(Text)
    error_reason: Mapped[str] = mapped_column(Text)
    question_type: Mapped[str | None] = mapped_column(String(40), nullable=True, index=True)
    target_difficulty: Mapped[float] = mapped_column(Float, default=0.5)
    knowledge_names_json: Mapped[list] = mapped_column(JSON, default=list)
    matched_question_ids_json: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), index=True
    )


class AgentRun(Base):
    __tablename__ = "agent_run"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_request: Mapped[str] = mapped_column(Text)
    mode: Mapped[str] = mapped_column(String(30), default="multi_agent", index=True)
    status: Mapped[str] = mapped_column(String(30), default="running", index=True)
    final_response: Mapped[str | None] = mapped_column(Text, nullable=True)
    steps_used: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ToolCallTrace(Base):
    __tablename__ = "tool_call_trace"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    run_id: Mapped[str] = mapped_column(ForeignKey("agent_run.id"), index=True)
    step: Mapped[int] = mapped_column(Integer)
    actor: Mapped[str] = mapped_column(String(80), index=True)
    tool_name: Mapped[str] = mapped_column(String(100), index=True)
    arguments_json: Mapped[dict] = mapped_column(JSON, default=dict)
    result_json: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(30), index=True)
    duration_ms: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
