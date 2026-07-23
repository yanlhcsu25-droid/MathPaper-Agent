import re

from calculus_agent.schemas import PaperPreviewRead


def render_paper_latex(paper: PaperPreviewRead, *, teacher_version: bool) -> str:
    title = _latex_text(paper.title)
    suffix = "（教师解析卷）" if teacher_version else ""
    sections: list[str] = []
    current_type = None
    for index, item in enumerate(paper.items, start=1):
        if item.question_type != current_type:
            current_type = item.question_type
            sections.append(f"\\section*{{{_latex_text(current_type)}}}")
        space = "4.2cm" if item.question_type == "解答题" else "1.4cm"
        sections.extend(
            [
                f"\\question{{{index}}}{{{item.score}}}{{{_mixed_latex(item.question_text)}}}",
                f"\\vspace{{{space}}}",
            ]
        )

    answers: list[str] = []
    if teacher_version:
        answers.extend(["\\clearpage", "\\section*{参考答案与解析}"])
        for index, item in enumerate(paper.items, start=1):
            answers.append(f"\\subsection*{{第 {index} 题}}")
            answers.append(
                f"\\textbf{{答案：}}{_mixed_latex(item.final_answer or '暂无独立答案')}\\par"
            )
            if item.solution_steps:
                answers.append("\\begin{enumerate}[label=\\arabic*.,leftmargin=2em]")
                answers.extend(f"\\item {_mixed_latex(step)}" for step in item.solution_steps)
                answers.append("\\end{enumerate}")
            if item.knowledge:
                knowledge = _latex_text("、".join(item.knowledge))
                answers.append(f"\\noindent\\textcolor{{slate}}{{知识点：{knowledge}}}\\par")

    body = "\n\n".join(sections + answers)
    return rf"""\documentclass[UTF8,12pt,a4paper]{{ctexart}}
\usepackage{{amsmath,amssymb,mathtools}}
\usepackage[margin=2cm,headheight=15pt]{{geometry}}
\usepackage{{enumitem,fancyhdr,xcolor,lastpage}}
\definecolor{{accent}}{{HTML}}{{1D4ED8}}
\definecolor{{slate}}{{HTML}}{{64748B}}
\pagestyle{{fancy}}
\fancyhf{{}}
\fancyfoot[C]{{\small\textcolor{{slate}}{{第 \thepage\ 页，共 \pageref{{LastPage}} 页}}}}
\renewcommand{{\headrulewidth}}{{0pt}}
\setlength{{\parindent}}{{0pt}}
\setlength{{\parskip}}{{0.45em}}
\newcommand{{\question}}[3]{{\noindent\textbf{{#1.}}\hspace{{0.35em}}#3\hfill\textcolor{{slate}}{{（#2分）}}\par}}
\ctexset{{section={{format=\large\bfseries\color{{accent}},beforeskip=1.1em,afterskip=0.6em}}}}

\begin{{document}}
\begin{{center}}
  {{\LARGE\bfseries {title}{suffix}}}\\[1em]
  姓名：\underline{{\hspace{{3.8cm}}}}\hfill
  班级：\underline{{\hspace{{3.8cm}}}}\hfill
  满分：{paper.total_score} 分
\end{{center}}
\vspace{{0.5em}}
\hrule
\vspace{{1em}}

{body}

\end{{document}}
"""


_MATH_PATTERN = re.compile(r"(\$\$.*?\$\$|\$.*?\$|\\\[.*?\\\]|\\\(.*?\\\))", re.DOTALL)


def _mixed_latex(value: str) -> str:
    """Escape prose while preserving explicit LaTeX math segments."""
    parts = _MATH_PATTERN.split(value)
    return "".join(part if _MATH_PATTERN.fullmatch(part) else _latex_text(part) for part in parts)


def _latex_text(value: str) -> str:
    replacements = {
        "\\": r"\textbackslash{}",
        "&": r"\&",
        "%": r"\%",
        "$": r"\$",
        "#": r"\#",
        "_": r"\_",
        "{": r"\{",
        "}": r"\}",
        "~": r"\textasciitilde{}",
        "^": r"\textasciicircum{}",
    }
    return "".join(replacements.get(char, char) for char in value)
