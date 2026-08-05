from calculus_agent.requirements.parser import apply_explicit_constraints
from calculus_agent.schemas import PaperBlueprint


def test_explicit_grade_and_difficulty_override_model_omissions():
    blueprint = PaperBlueprint(
        total_questions=8,
        grade=None,
        difficulty_min=0.5,
        difficulty_max=0.5,
    )
    result = apply_explicit_constraints("生成八年级中等难度测试卷", blueprint)
    assert result.grade == "八年级"
    assert result.difficulty_min == 0.35
    assert result.difficulty_max == 0.65


def test_junior_grade_alias_is_normalized():
    blueprint = PaperBlueprint(total_questions=5)
    result = apply_explicit_constraints("初二年级基础练习", blueprint)
    assert result.grade == "八年级"


def test_explicit_knowledge_and_image_constraints_override_model():
    blueprint = PaperBlueprint(
        total_questions=10,
        knowledge_quotas=[{"name": "一次函数", "count": 5}],
    )
    result = apply_explicit_constraints(
        "一次函数测试卷，二次函数至少5题，需要含图片", blueprint
    )
    assert [(item.name, item.count) for item in result.knowledge_quotas] == [
        ("二次函数", 5)
    ]
    assert result.image_question_count == 1
