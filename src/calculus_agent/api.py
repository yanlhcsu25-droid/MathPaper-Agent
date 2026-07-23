from collections.abc import Iterator
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from calculus_agent.config import Settings, get_settings
from calculus_agent.datasets.cmm_math import import_cmm_math
from calculus_agent.datasets.mm_math import import_mm_math
from calculus_agent.datasets.ugmathbench import import_ugmathbench
from calculus_agent.db import build_session_factory, create_schema
from calculus_agent.knowledge.curriculum import import_curriculum
from calculus_agent.knowledge.normalization import normalize_name
from calculus_agent.knowledge.retrieval import retrieve_knowledge
from calculus_agent.knowledge.steward import DraftNotFoundError, process_draft
from calculus_agent.models import (
    AgentRun,
    CurriculumNode,
    KnowledgeAlias,
    KnowledgeNode,
    QuestionDraft,
    ToolCallTrace,
)
from calculus_agent.orchestration.service import run_paper_agent
from calculus_agent.papers.selector import compose_paper
from calculus_agent.papers.renderer import render_paper_pdf
from calculus_agent.papers.latex_renderer import render_paper_latex
from calculus_agent.questions.review import DraftApprovalError, approve_draft
from calculus_agent.requirements.parser import OllamaRequirementParser
from calculus_agent.schemas import (
    AgentRunRead,
    AgentRunRequest,
    CurriculumImportRequest,
    CurriculumNodeRead,
    CMMMathImportRequest,
    DatasetImportRequest,
    DatasetImportSummary,
    DraftApproveRequest,
    DraftProcessRead,
    KnowledgeNodeCreate,
    KnowledgeNodeRead,
    MMMathImportRequest,
    NaturalLanguagePaperRequest,
    PaperBlueprint,
    PaperPreviewRead,
    QuestionRead,
    ToolCallTraceRead,
)
from calculus_agent.solver.service import OllamaSolver, ReferenceAnswerSolver


router = APIRouter(prefix="/api/v1")


def get_session(settings: Settings = Depends(get_settings)) -> Iterator[Session]:
    create_schema(settings.database_url)
    factory = build_session_factory(settings.database_url)
    with factory.begin() as session:
        yield session


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "application": "math-paper-agent"}


@router.post("/agents/runs", response_model=AgentRunRead)
def create_agent_run(
    request: AgentRunRequest,
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> AgentRunRead:
    return run_paper_agent(
        session,
        request,
        base_url=settings.ollama_base_url,
        model=settings.solver_model,
        timeout=settings.solver_timeout_seconds,
    )


@router.get("/agents/runs/{run_id}", response_model=AgentRunRead)
def get_agent_run(run_id: str, session: Session = Depends(get_session)) -> AgentRunRead:
    run = session.get(AgentRun, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Agent run not found")
    traces = list(
        session.scalars(
            select(ToolCallTrace)
            .where(ToolCallTrace.run_id == run.id)
            .order_by(ToolCallTrace.step, ToolCallTrace.created_at)
        ).all()
    )
    return AgentRunRead(
        run_id=run.id,
        status=run.status,
        mode=run.mode,
        final_response=run.final_response,
        steps_used=run.steps_used,
        error_message=run.error_message,
        traces=[
            ToolCallTraceRead(
                step=item.step,
                actor=item.actor,
                tool_name=item.tool_name,
                arguments=item.arguments_json,
                result=item.result_json,
                status=item.status,
                duration_ms=item.duration_ms,
            )
            for item in traces
        ],
    )


@router.post("/curriculum/import", response_model=list[CurriculumNodeRead])
def add_curriculum(
    request: CurriculumImportRequest, session: Session = Depends(get_session)
) -> list[CurriculumNodeRead]:
    nodes = import_curriculum(session, request.directory_text)
    return [
        CurriculumNodeRead(
            id=node.id,
            parent_id=node.parent_id,
            node_type=node.node_type,
            code=node.code,
            title=node.title,
            sort_order=node.sort_order,
        )
        for node in nodes
    ]


@router.get("/curriculum", response_model=list[CurriculumNodeRead])
def curriculum(session: Session = Depends(get_session)) -> list[CurriculumNodeRead]:
    nodes = session.scalars(select(CurriculumNode).order_by(CurriculumNode.sort_order)).all()
    return [CurriculumNodeRead.model_validate(node, from_attributes=True) for node in nodes]


@router.post("/knowledge", response_model=KnowledgeNodeRead)
def add_knowledge_node(
    request: KnowledgeNodeCreate, session: Session = Depends(get_session)
) -> KnowledgeNodeRead:
    normalized = normalize_name(request.name)
    existing = session.scalar(
        select(KnowledgeNode).where(
            KnowledgeNode.node_type == request.node_type,
            KnowledgeNode.normalized_name == normalized,
        )
    )
    if existing:
        raise HTTPException(status_code=409, detail="Knowledge node already exists")
    node = KnowledgeNode(
        curriculum_node_id=request.curriculum_node_id,
        node_type=request.node_type,
        name=request.name.strip(),
        normalized_name=normalized,
        description=request.description,
        source_type="teacher" if request.review_status == "approved" else "agent_candidate",
        confidence=1.0 if request.review_status == "approved" else 0.7,
        review_status=request.review_status,
    )
    session.add(node)
    session.flush()
    for alias in request.aliases:
        session.add(
            KnowledgeAlias(
                node_id=node.id,
                alias=alias.strip(),
                normalized_alias=normalize_name(alias),
            )
        )
    return KnowledgeNodeRead(
        id=node.id,
        node_type=node.node_type,
        name=node.name,
        curriculum_node_id=node.curriculum_node_id,
        review_status=node.review_status,
    )


@router.get("/knowledge/search", response_model=list[KnowledgeNodeRead])
def search_knowledge(
    query: str = Query(min_length=1),
    node_type: str | None = None,
    session: Session = Depends(get_session),
) -> list[KnowledgeNodeRead]:
    return [
        KnowledgeNodeRead(
            id=item.node.id,
            node_type=item.node.node_type,
            name=item.node.name,
            curriculum_node_id=item.node.curriculum_node_id,
            review_status=item.node.review_status,
            score=item.score,
            match_reasons=item.reasons,
        )
        for item in retrieve_knowledge(session, query, node_type=node_type)
    ]


@router.post("/datasets/ugmathbench/import", response_model=DatasetImportSummary)
def import_dataset(
    request: DatasetImportRequest, session: Session = Depends(get_session)
) -> DatasetImportSummary:
    path = Path(request.path).expanduser().resolve()
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Dataset file not found")
    return import_ugmathbench(session, path, variants=request.variants, limit=request.limit)


@router.post("/datasets/mm-math/import", response_model=DatasetImportSummary)
def import_chinese_dataset(
    request: MMMathImportRequest, session: Session = Depends(get_session)
) -> DatasetImportSummary:
    path = Path(request.path).expanduser().resolve()
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Dataset file not found")
    image_root = Path(request.image_root).expanduser().resolve() if request.image_root else None
    return import_mm_math(
        session,
        path,
        image_root=image_root,
        limit=request.limit,
        publish=request.publish,
    )


@router.post("/datasets/cmm-math/import", response_model=DatasetImportSummary)
def import_chinese_k12_dataset(
    request: CMMMathImportRequest, session: Session = Depends(get_session)
) -> DatasetImportSummary:
    path = Path(request.path).expanduser().resolve()
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Dataset file not found")
    image_root = Path(request.image_root).expanduser().resolve() if request.image_root else None
    return import_cmm_math(
        session,
        path,
        levels=tuple(request.levels),
        image_root=image_root,
        text_only=request.text_only,
        require_analysis=request.require_analysis,
        limit=request.limit,
        publish=request.publish,
    )


@router.post("/papers/preview", response_model=PaperPreviewRead)
def preview_paper(
    request: PaperBlueprint, session: Session = Depends(get_session)
) -> PaperPreviewRead:
    return compose_paper(session, request)


@router.post("/papers/export/{version}")
def export_paper(
    version: str,
    request: PaperBlueprint,
    session: Session = Depends(get_session),
) -> Response:
    if version not in {"student", "teacher"}:
        raise HTTPException(status_code=404, detail="Unknown paper version")
    paper = compose_paper(session, request)
    if not paper.feasible:
        raise HTTPException(
            status_code=422, detail={"message": "题库无法满足组卷约束", "warnings": paper.warnings}
        )
    content = render_paper_pdf(paper, teacher_version=version == "teacher")
    filename = "teacher-paper.pdf" if version == "teacher" else "student-paper.pdf"
    return Response(
        content=content,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/papers/export-latex/{version}")
def export_paper_latex(
    version: str,
    request: PaperBlueprint,
    session: Session = Depends(get_session),
) -> Response:
    if version not in {"student", "teacher"}:
        raise HTTPException(status_code=404, detail="Unknown paper version")
    paper = compose_paper(session, request)
    if not paper.feasible:
        raise HTTPException(
            status_code=422,
            detail={"message": "题库无法满足组卷约束", "warnings": paper.warnings},
        )
    content = render_paper_latex(paper, teacher_version=version == "teacher")
    filename = "teacher-paper.tex" if version == "teacher" else "student-paper.tex"
    return Response(
        content=content.encode("utf-8"),
        media_type="application/x-tex; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/papers/parse-requirement", response_model=PaperBlueprint)
def parse_paper_requirement(
    request: NaturalLanguagePaperRequest,
    settings: Settings = Depends(get_settings),
) -> PaperBlueprint:
    parser = OllamaRequirementParser(
        base_url=settings.ollama_base_url,
        model=settings.solver_model,
        timeout=settings.solver_timeout_seconds,
    )
    try:
        return parser.parse(request.requirement)
    except Exception as error:
        raise HTTPException(status_code=502, detail=f"需求解析失败：{error}") from error


@router.get("/drafts")
def drafts(status: str | None = None, session: Session = Depends(get_session)) -> list[dict]:
    statement = select(QuestionDraft).order_by(QuestionDraft.created_at)
    if status:
        statement = statement.where(QuestionDraft.status == status)
    return [
        {
            "id": item.id,
            "source_item_id": item.source_item_id,
            "variant": item.variant,
            "question_text": item.question_text,
            "reference_answers": item.reference_answers_json,
            "status": item.status,
        }
        for item in session.scalars(statement).all()
    ]


@router.post("/drafts/{draft_id}/process", response_model=DraftProcessRead)
def run_draft(
    draft_id: str,
    solver_mode: str = Query(default="ollama", pattern="^(ollama|reference)$"),
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> DraftProcessRead:
    draft = session.get(QuestionDraft, draft_id)
    if draft is None:
        raise HTTPException(status_code=404, detail="Draft not found")
    solver = (
        ReferenceAnswerSolver(draft.reference_answers_json[0])
        if solver_mode == "reference"
        else OllamaSolver(
            base_url=settings.ollama_base_url,
            model=settings.solver_model,
            timeout=settings.solver_timeout_seconds,
        )
    )
    try:
        return process_draft(session, draft_id, solver)
    except DraftNotFoundError as error:
        raise HTTPException(status_code=404, detail="Draft not found") from error
    except Exception as error:
        raise HTTPException(status_code=502, detail=f"Solver failed: {error}") from error


@router.post("/drafts/{draft_id}/approve", response_model=QuestionRead)
def publish_draft(
    draft_id: str,
    request: DraftApproveRequest,
    session: Session = Depends(get_session),
) -> QuestionRead:
    try:
        return approve_draft(session, draft_id, request)
    except (DraftApprovalError, ValueError) as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
