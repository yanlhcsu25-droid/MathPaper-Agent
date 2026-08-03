from calculus_agent.papers.latex_renderer import render_paper_latex
from calculus_agent.schemas import PaperItemRead, PaperPreviewRead


def _paper() -> PaperPreviewRead:
    return PaperPreviewRead(
        title="八年级函数测试_卷",
        total_score=20,
        feasible=True,
        constraints=[],
        items=[
            PaperItemRead(
                question_id="q1",
                question_text=r"已知 $y=\frac{1}{2}x+3$，求增长率（占比 50%）。",
                question_type="解答题",
                difficulty=0.5,
                score=20,
                knowledge=["一次函数"],
                final_answer=r"$\frac{1}{2}$",
                solution_steps=[r"由 $y=kx+b$ 可知 $k=\frac{1}{2}$。"],
            )
        ],
    )


def test_student_latex_escapes_prose_and_preserves_math():
    result = render_paper_latex(_paper(), teacher_version=False)
    assert result.startswith(r"\documentclass")
    assert r"测试\_卷" in result
    assert r"$y=\frac{1}{2}x+3$" in result
    assert r"50\%" in result
    assert "参考答案与解析" not in result
    assert "解答应写出文字说明、证明过程或演算步骤" in result
    assert r"\Needspace{9.4cm}" in result


def test_teacher_latex_contains_solution():
    result = render_paper_latex(_paper(), teacher_version=True)
    assert "参考答案与解析" in result
    assert r"$\frac{1}{2}$" in result
    assert "知识点：一次函数" in result
