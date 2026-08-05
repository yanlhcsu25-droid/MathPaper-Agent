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
            "difficulty_max, sections, knowledge_quotas, seed。"
            "sections必须为{question_type,count,score_per_question,total_score}数组，"
            "且每部分total_score=count*score_per_question，所有部分题数与分值分别等于全卷题数与总分。"
            "另有image_question_count表示至少需要的带图片题数量，strict_knowledge表示是否禁止用无关知识点补题。"
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


class BailianRequirementParser:
    def __init__(
        self, *, api_key: str, base_url: str, model: str, timeout: float = 120
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout

    def parse(self, requirement: str) -> PaperBlueprint:
        prompt = (
            "你是初中数学组卷需求解析器。把教师要求转换为严格JSON，不要选择题目。"
            "字段：title, grade, total_questions, total_score, difficulty_min, "
            "difficulty_max, sections, knowledge_quotas, seed。"
            "sections必须为{question_type,count,score_per_question,total_score}数组，"
            "且每部分total_score=count*score_per_question，所有部分题数与分值分别等于全卷题数与总分。"
            "另有image_question_count表示至少需要的带图片题数量，strict_knowledge表示是否禁止用无关知识点补题。"
            "difficulty使用0到1；容易约0.2，中等约0.5，困难约0.8。"
            "knowledge_quotas是{name,count}数组。未提及年级时grade为null，未提及总分时为100，"
            "未提及seed时为42。题型统一写选择题、填空题或解答题。\n"
            f"教师要求：{requirement}"
        )
        payload = json.dumps(
            {
                "model": self.model,
                "messages": [{"role": "user", "content": prompt}],
                "enable_thinking": False,
                "temperature": 0,
            },
            ensure_ascii=False,
        ).encode()
        request = Request(
            f"{self.base_url}/chat/completions",
            data=payload,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
        )
        with urlopen(request, timeout=self.timeout) as response:
            body = json.loads(response.read().decode())
        content = body["choices"][0]["message"]["content"]
        parsed = json.loads(_strip_json_fence(content))
        grade = parsed.get("grade")
        if isinstance(grade, int):
            parsed["grade"] = {7: "七年级", 8: "八年级", 9: "九年级"}.get(
                grade, str(grade)
            )
        blueprint = PaperBlueprint.model_validate(parsed)
        return apply_explicit_constraints(requirement, blueprint)


def _strip_json_fence(value: str) -> str:
    value = value.strip()
    match = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", value, re.DOTALL)
    if match:
        return match.group(1)
    start = value.find("{")
    end = value.rfind("}")
    return value[start : end + 1] if start >= 0 and end > start else value


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
    explicit_quotas = [
        {"name": name, "count": int(count)}
        for name, count in re.findall(
            r"([\u4e00-\u9fff]{2,20}(?:函数|方程|几何|统计|概率|不等式|根式))\s*(?:至少|不少于)\s*(\d+)\s*题",
            requirement,
        )
    ]
    if explicit_quotas:
        updates["knowledge_quotas"] = explicit_quotas
        updates["strict_knowledge"] = True
    image_count = re.search(r"(?:带|含|需要)\s*图片(?:的题目)?\s*(\d+)\s*题", requirement)
    if image_count:
        updates["image_question_count"] = int(image_count.group(1))
    elif re.search(r"(?:需要|要求|必须).*图片|含图片", requirement):
        updates["image_question_count"] = 1
    sections = []
    for question_type in ("选择题", "多选题", "填空题", "解答题"):
        per_item = re.search(
            rf"{question_type}\s*(\d+)\s*(?:道|题)[^；;。]*?每(?:小)?题\s*(\d+)\s*分",
            requirement,
        )
        total = re.search(
            rf"{question_type}\s*(\d+)\s*(?:道|题)[^；;。]*?(?:共|合计)\s*(\d+)\s*分",
            requirement,
        )
        if per_item:
            count, score = map(int, per_item.groups())
        elif total:
            count, section_total = map(int, total.groups())
            if count == 0 or section_total % count:
                continue
            score = section_total // count
        else:
            continue
        sections.append(
            {
                "question_type": question_type,
                "count": count,
                "score_per_question": score,
                "total_score": count * score,
            }
        )
    if sections:
        updates["sections"] = sections
        updates["question_type_counts"] = {
            section["question_type"]: section["count"] for section in sections
        }
        updates["total_questions"] = sum(section["count"] for section in sections)
        updates["total_score"] = sum(section["total_score"] for section in sections)
    return PaperBlueprint.model_validate({**blueprint.model_dump(), **updates})
