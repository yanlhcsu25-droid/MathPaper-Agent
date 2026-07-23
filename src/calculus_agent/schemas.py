from typing import Literal

from pydantic import BaseModel, Field, model_validator


class CurriculumImportRequest(BaseModel):
    directory_text: str = Field(min_length=1, max_length=20000)


class CurriculumNodeRead(BaseModel):
    id: str
    parent_id: str | None
    node_type: str
    code: str | None
    title: str
    sort_order: int


class KnowledgeNodeCreate(BaseModel):
    node_type: Literal["concept", "problem_type", "method"]
    name: str = Field(min_length=1, max_length=255)
    curriculum_node_id: str | None = None
    description: str | None = None
    aliases: list[str] = Field(default_factory=list)
    review_status: Literal["proposed", "approved"] = "approved"


class KnowledgeNodeRead(BaseModel):
    id: str
    node_type: str
    name: str
    curriculum_node_id: str | None
    review_status: str
    score: float | None = None
    match_reasons: list[str] = Field(default_factory=list)


class DatasetImportRequest(BaseModel):
    path: str
    variants: list[int] = Field(default_factory=lambda: [1], min_length=1)
    limit: int | None = Field(default=None, ge=1, le=10000)


class MMMathImportRequest(BaseModel):
    path: str
    image_root: str | None = None
    limit: int | None = Field(default=None, ge=1, le=10000)
    publish: bool = True


class DatasetImportSummary(BaseModel):
    created: int
    existing: int
    skipped: int


class SolverResult(BaseModel):
    solution_steps: list[str] = Field(default_factory=list)
    final_answer: str
    used_knowledge: list[str] = Field(default_factory=list)
    used_methods: list[str] = Field(default_factory=list)
    model_name: str


class VerificationResult(BaseModel):
    status: Literal["verified", "conflict", "unsupported", "error"]
    method: str
    expected: list[str]
    actual: str
    details: list[str] = Field(default_factory=list)


class ClassificationCandidate(BaseModel):
    knowledge_node_id: str
    name: str
    node_type: str
    score: float
    evidence: list[str] = Field(default_factory=list)


class DraftProcessRead(BaseModel):
    draft_id: str
    status: str
    solution: SolverResult
    verification: VerificationResult
    candidates: list[ClassificationCandidate]


class DraftApproveRequest(BaseModel):
    primary_concept_id: str
    secondary_concept_ids: list[str] = Field(default_factory=list)
    problem_type_ids: list[str] = Field(default_factory=list)
    method_ids: list[str] = Field(default_factory=list)


class QuestionRead(BaseModel):
    id: str
    draft_id: str
    question_text: str
    final_answer: str | None
    verification_status: str
    knowledge: list[KnowledgeNodeRead]


class KnowledgeQuota(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    count: int = Field(ge=1, le=100)


class PaperBlueprint(BaseModel):
    title: str = Field(default="初中数学测试卷", min_length=1, max_length=100)
    grade: str | None = None
    total_questions: int = Field(ge=1, le=100)
    total_score: int = Field(default=100, ge=1, le=300)
    difficulty_min: float = Field(default=0.0, ge=0, le=1)
    difficulty_max: float = Field(default=1.0, ge=0, le=1)
    question_type_counts: dict[str, int] = Field(default_factory=dict)
    knowledge_quotas: list[KnowledgeQuota] = Field(default_factory=list)
    seed: int = 42

    @model_validator(mode="after")
    def validate_constraints(self):
        if self.difficulty_min > self.difficulty_max:
            raise ValueError("difficulty_min cannot exceed difficulty_max")
        if sum(self.question_type_counts.values()) > self.total_questions:
            raise ValueError("题型数量之和不能超过题目总数")
        return self


class NaturalLanguagePaperRequest(BaseModel):
    requirement: str = Field(min_length=2, max_length=2000)


class PaperItemRead(BaseModel):
    question_id: str
    question_text: str
    question_type: str
    difficulty: float | None
    score: int
    knowledge: list[str] = Field(default_factory=list)
    final_answer: str | None = None
    solution_steps: list[str] = Field(default_factory=list)


class ConstraintCheck(BaseModel):
    name: str
    required: int | str
    actual: int | str
    satisfied: bool


class PaperPreviewRead(BaseModel):
    title: str
    total_score: int
    items: list[PaperItemRead]
    constraints: list[ConstraintCheck]
    warnings: list[str] = Field(default_factory=list)
    feasible: bool


class AgentRunRequest(BaseModel):
    request: str = Field(min_length=2, max_length=4000)
    max_steps: int = Field(default=12, ge=1, le=30)
    mode: Literal["single_agent", "multi_agent"] = "multi_agent"


class ToolCallTraceRead(BaseModel):
    step: int
    actor: str
    tool_name: str
    arguments: dict
    result: dict
    status: str
    duration_ms: int


class AgentRunRead(BaseModel):
    run_id: str
    status: str
    mode: str
    final_response: str | None
    steps_used: int
    error_message: str | None = None
    current_paper: PaperPreviewRead | None = None
    traces: list[ToolCallTraceRead] = Field(default_factory=list)
