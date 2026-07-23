import json
import re
from urllib.request import Request, urlopen

from calculus_agent.schemas import PaperBlueprint


class OllamaRequirementParser:
    def __init__(self, *, base_url: str, model: str, timeout: float = 120) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout

    def parse(self, requirement: str) -> PaperBlueprint:
        prompt = (
            "你是初中数学组卷需求解析器。把教师要求转换为严格JSON，不要选择题目。"
            "字段：title, grade, total_questions, total_score, difficulty_min, "
            "difficulty_max, question_type_counts, knowledge_quotas, seed。"
            "difficulty使用0到1；容易约0.2，中等约0.5，困难约0.8。"
            "knowledge_quotas是{name,count}数组。未提及年级时grade为null，未提及总分时为100，"
            "未提及seed时为42。题型统一写选择题、填空题或解答题。\n"
            f"教师要求：{requirement}"
        )
        payload = json.dumps(
            {
                "model": self.model,
                "prompt": prompt,
                "stream": False,
                "think": False,
                "format": PaperBlueprint.model_json_schema(),
                "options": {"temperature": 0},
            }
        ).encode()
        request = Request(
            f"{self.base_url}/api/generate",
            data=payload,
            headers={"Content-Type": "application/json"},
        )
        with urlopen(request, timeout=self.timeout) as response:
            body = json.loads(response.read().decode())
        blueprint = PaperBlueprint.model_validate(json.loads(body["response"]))
        return apply_explicit_constraints(requirement, blueprint)


def apply_explicit_constraints(requirement: str, blueprint: PaperBlueprint) -> PaperBlueprint:
    """Let explicit teacher wording override fields occasionally omitted by the model."""
    updates = {}
    grade = re.search(r"([七八九]|初[一二三])年级", requirement)
    if grade:
        value = grade.group(0)
        mapping = {"初一年级": "七年级", "初二年级": "八年级", "初三年级": "九年级"}
        updates["grade"] = mapping.get(value, value)
    difficulty_ranges = {
        "容易": (0.0, 0.35),
        "基础": (0.0, 0.4),
        "中等": (0.35, 0.65),
        "较难": (0.6, 0.85),
        "困难": (0.75, 1.0),
    }
    for word, (minimum, maximum) in difficulty_ranges.items():
        if word in requirement:
            updates["difficulty_min"] = minimum
            updates["difficulty_max"] = maximum
            break
    return blueprint.model_copy(update=updates)
