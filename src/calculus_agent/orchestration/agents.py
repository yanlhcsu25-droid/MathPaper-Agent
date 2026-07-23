from calculus_agent.orchestration.loop import ToolAgent
from calculus_agent.orchestration.tools import knowledge_tools, paper_tools, review_tools
from calculus_agent.orchestration.types import (
    AgentResult,
    AgentRunContext,
    AgentTool,
    ChatBackend,
)


KNOWLEDGE_PROMPT = """你是 KnowledgeStewardAgent，是知识库和题库的只读管理员。
你只能使用提供的检索和供给统计工具。先调用工具取得证据，再返回简洁的结构化结论。
不要组卷、不要导出文件、不要创建知识点，也不要猜测题库中不存在的数据。"""

REVIEW_PROMPT = """你是 PaperReviewerAgent，是只读试卷审核员。
必须调用 validate_current_paper 取得审核证据。不得直接修改试卷，不得放宽教师硬约束。
返回审核状态、具体问题和建议的下一步动作。"""

ORCHESTRATOR_PROMPT = """你是 PaperOrchestratorAgent，负责中文初中数学组卷调度。
多Agent模式下，涉及知识点检索或题库供给必须委托 knowledge_steward；试卷生成后必须委托
paper_reviewer 审核。确定性组卷必须调用 compose_paper，不能自己编造题目。
教师明确给出的题量、总分、题型数量和知识点配额是硬约束，禁止擅自放宽。
当题库不足时，清楚说明缺口并停止；不要循环调用同一工具。完成后汇总结果和审核状态。"""

SINGLE_AGENT_PROMPT = """你是单Agent组卷基线。你可以直接使用知识检索、题库供给、确定性组卷
和审核工具。教师明确给出的题量、总分、题型数量和知识点配额是硬约束，禁止擅自放宽。
必须基于工具结果回答，不得编造题目或题库供给。"""


class PaperAgentOrchestrator:
    def __init__(self, backend: ChatBackend) -> None:
        self.backend = backend

    def run(
        self,
        request: str,
        context: AgentRunContext,
        *,
        mode: str = "multi_agent",
    ) -> AgentResult:
        if mode == "single_agent":
            agent = ToolAgent(
                name="SinglePaperAgent",
                system_prompt=SINGLE_AGENT_PROMPT,
                backend=self.backend,
                tools=(knowledge_tools(context) + paper_tools(context) + review_tools(context)),
            )
            return agent.run(request, context)

        delegate = self._delegate_tool(context)
        agent = ToolAgent(
            name="PaperOrchestratorAgent",
            system_prompt=ORCHESTRATOR_PROMPT,
            backend=self.backend,
            tools=paper_tools(context) + [delegate],
        )
        return agent.run(request, context)

    def _delegate_tool(self, context: AgentRunContext) -> AgentTool:
        def delegate(arguments: dict) -> dict:
            context.budget.consume_delegation()
            agent_type = str(arguments.get("agent_type") or "")
            task = str(arguments.get("task") or "").strip()
            if not task:
                raise ValueError("task is required")
            if agent_type == "knowledge_steward":
                child = ToolAgent(
                    name="KnowledgeStewardAgent",
                    system_prompt=KNOWLEDGE_PROMPT,
                    backend=self.backend,
                    tools=knowledge_tools(context),
                )
            elif agent_type == "paper_reviewer":
                child = ToolAgent(
                    name="PaperReviewerAgent",
                    system_prompt=REVIEW_PROMPT,
                    backend=self.backend,
                    tools=review_tools(context),
                )
            else:
                raise ValueError(f"Unknown agent_type: {agent_type}")
            result = child.run(task, context)
            return {"agent_type": agent_type, "status": result.status, "response": result.text}

        return AgentTool(
            name="delegate_agent",
            description="把独立任务委托给受限工具集的专业子Agent，并接收其最终结果。",
            parameters={
                "type": "object",
                "properties": {
                    "agent_type": {
                        "type": "string",
                        "enum": ["knowledge_steward", "paper_reviewer"],
                    },
                    "task": {"type": "string"},
                },
                "required": ["agent_type", "task"],
            },
            handler=delegate,
        )
