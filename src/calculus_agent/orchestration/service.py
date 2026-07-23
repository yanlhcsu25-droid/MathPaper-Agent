from datetime import UTC, datetime

from sqlalchemy.orm import Session

from calculus_agent.models import AgentRun, ToolCallTrace
from calculus_agent.orchestration.agents import PaperAgentOrchestrator
from calculus_agent.orchestration.backend import OllamaChatBackend
from calculus_agent.orchestration.types import AgentRunContext, RunBudget
from calculus_agent.schemas import AgentRunRead, AgentRunRequest, ToolCallTraceRead


def run_paper_agent(
    session: Session,
    request: AgentRunRequest,
    *,
    base_url: str,
    model: str,
    timeout: float,
) -> AgentRunRead:
    run = AgentRun(user_request=request.request, mode=request.mode, status="running")
    session.add(run)
    session.flush()
    context = AgentRunContext(session=session, budget=RunBudget(max_steps=request.max_steps))
    backend = OllamaChatBackend(base_url=base_url, model=model, timeout=timeout)
    try:
        result = PaperAgentOrchestrator(backend).run(
            request.request,
            context,
            mode=request.mode,
        )
        run.status = result.status
        run.final_response = result.text
    except Exception as error:
        run.status = "failed"
        run.error_message = str(error)
    run.steps_used = context.budget.steps_used
    run.completed_at = datetime.now(UTC)
    for trace in context.traces:
        session.add(
            ToolCallTrace(
                run_id=run.id,
                step=trace.step,
                actor=trace.actor,
                tool_name=trace.tool_name,
                arguments_json=trace.arguments,
                result_json=trace.result,
                status=trace.status,
                duration_ms=trace.duration_ms,
            )
        )
    session.flush()
    return AgentRunRead(
        run_id=run.id,
        status=run.status,
        mode=run.mode,
        final_response=run.final_response,
        steps_used=run.steps_used,
        error_message=run.error_message,
        current_paper=context.current_paper,
        traces=[
            ToolCallTraceRead(
                step=trace.step,
                actor=trace.actor,
                tool_name=trace.tool_name,
                arguments=trace.arguments,
                result=trace.result,
                status=trace.status,
                duration_ms=trace.duration_ms,
            )
            for trace in context.traces
        ],
    )
