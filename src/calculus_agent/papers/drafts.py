from sqlalchemy import select
from sqlalchemy.orm import Session

from calculus_agent.models import PaperDraft
from calculus_agent.papers.selector import compose_paper
from calculus_agent.schemas import (
    PaperBlueprint,
    PaperDraftDiffRead,
    PaperDraftRead,
    PaperItemChange,
    PaperPreviewRead,
)


class PaperDraftNotFoundError(LookupError):
    pass


def save_paper_draft(
    session: Session,
    blueprint: PaperBlueprint,
    *,
    parent_id: str | None = None,
) -> PaperDraftRead:
    if parent_id is not None and session.get(PaperDraft, parent_id) is None:
        raise PaperDraftNotFoundError(parent_id)
    preview = compose_paper(session, blueprint)
    draft = PaperDraft(
        parent_id=parent_id,
        title=blueprint.title,
        blueprint_json=blueprint.model_dump(mode="json"),
        preview_json=preview.model_dump(mode="json"),
    )
    session.add(draft)
    session.flush()
    return _read(draft)


def list_paper_drafts(session: Session) -> list[PaperDraftRead]:
    drafts = session.scalars(select(PaperDraft).order_by(PaperDraft.created_at.desc())).all()
    return [_read(draft) for draft in drafts]


def get_paper_draft(session: Session, draft_id: str) -> PaperDraftRead:
    draft = session.get(PaperDraft, draft_id)
    if draft is None:
        raise PaperDraftNotFoundError(draft_id)
    return _read(draft)


def compare_paper_drafts(
    session: Session,
    target_id: str,
    *,
    base_id: str | None = None,
) -> PaperDraftDiffRead:
    target = get_paper_draft(session, target_id)
    resolved_base_id = base_id or target.parent_id
    if resolved_base_id is None:
        raise PaperDraftNotFoundError("Draft has no parent version")
    base = get_paper_draft(session, resolved_base_id)
    base_items = {item.question_id: item for item in base.preview.items}
    target_items = {item.question_id: item for item in target.preview.items}
    added = [
        PaperItemChange(question_id=item.question_id, question_text=item.question_text)
        for item in target.preview.items
        if item.question_id not in base_items
    ]
    removed = [
        PaperItemChange(question_id=item.question_id, question_text=item.question_text)
        for item in base.preview.items
        if item.question_id not in target_items
    ]
    base_order = {item.question_id: index + 1 for index, item in enumerate(base.preview.items)}
    target_order = {item.question_id: index + 1 for index, item in enumerate(target.preview.items)}
    shared_ids = set(base_items) & set(target_items)
    order_changes = [
        PaperItemChange(
            question_id=question_id,
            question_text=target_items[question_id].question_text,
            before=base_order[question_id],
            after=target_order[question_id],
        )
        for question_id in shared_ids
        if base_order[question_id] != target_order[question_id]
    ]
    score_changes = [
        PaperItemChange(
            question_id=question_id,
            question_text=target_items[question_id].question_text,
            before=base_items[question_id].score,
            after=target_items[question_id].score,
        )
        for question_id in shared_ids
        if base_items[question_id].score != target_items[question_id].score
    ]
    blueprint_changes = {}
    for field in ("title", "grade", "total_questions", "total_score"):
        before = getattr(base.blueprint, field)
        after = getattr(target.blueprint, field)
        if before != after:
            blueprint_changes[field] = {"before": before, "after": after}
    return PaperDraftDiffRead(
        base_draft_id=base.id,
        target_draft_id=target.id,
        added=added,
        removed=removed,
        order_changes=sorted(order_changes, key=lambda item: item.after or 0),
        score_changes=sorted(score_changes, key=lambda item: target_order[item.question_id]),
        blueprint_changes=blueprint_changes,
        has_changes=bool(
            added or removed or order_changes or score_changes or blueprint_changes
        ),
    )


def _read(draft: PaperDraft) -> PaperDraftRead:
    return PaperDraftRead(
        id=draft.id,
        parent_id=draft.parent_id,
        title=draft.title,
        blueprint=PaperBlueprint.model_validate(draft.blueprint_json),
        preview=PaperPreviewRead.model_validate(draft.preview_json),
        status=draft.status,
        created_at=draft.created_at,
    )
