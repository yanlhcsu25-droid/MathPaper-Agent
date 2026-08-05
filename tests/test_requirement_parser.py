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


def test_explicit_section_scores_are_preserved_in_blueprint():
    blueprint = PaperBlueprint(total_questions=1, total_score=1)
    result = apply_explicit_constraints(
        "选择题4道，每题5分；填空题2道，每题5分；解答题4道，共60分。",
        blueprint,
    )
    assert result.total_questions == 10
    assert result.total_score == 90
    assert [
        (item.question_type, item.count, item.score_per_question, item.total_score)
        for item in result.sections
    ] == [
        ("选择题", 4, 5, 20),
        ("填空题", 2, 5, 10),
        ("解答题", 4, 15, 60),
    ]
