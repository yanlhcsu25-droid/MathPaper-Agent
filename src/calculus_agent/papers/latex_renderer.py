import re

from calculus_agent.schemas import PaperPreviewRead


def render_paper_latex(paper: PaperPreviewRead, *, teacher_version: bool) -> str:
    title = _latex_text(paper.title)
    suffix = "（教师解析卷）" if teacher_version else ""
    sections: list[str] = []
    current_type = None
    section_index = 0
    for item in paper.items:
        if item.question_type != current_type:
            current_type = item.question_type
            section_index = 0
            sections.append(f"\\section*{{{_section_title(paper, current_type)}}}")
        section_index += 1
        answer_space = max(3.2, min(7.2, 2 + item.score * 0.3))
        space = f"{answer_space:.1f}cm" if item.question_type == "解答题" else "1.1cm"
        if item.question_type == "解答题" and not teacher_version:
            sections.append(f"\\Needspace{{{answer_space + 2.2:.1f}cm}}")
        stem, options = _question_parts(item.question_text)
        sections.extend(
            [
                f"\\question{{{section_index}}}{{{item.score}}}{{{_mixed_latex(stem)}}}",
                _options_table(options),
            ]
        )
        if teacher_version:
            sections.extend(_teacher_answer_latex(item))
        else:
            sections.append(f"\\vspace{{{space}}}")

    body = "\n\n".join(sections)
    return rf"""\documentclass[UTF8,12pt,a4paper]{{ctexart}}
\usepackage{{amsmath,amssymb,mathtools}}
\usepackage[margin=2cm,headheight=15pt]{{geometry}}
\usepackage{{enumitem,fancyhdr,xcolor,lastpage,needspace,tabularx,array}}
\definecolor{{accent}}{{HTML}}{{111827}}
\definecolor{{slate}}{{HTML}}{{64748B}}
\pagestyle{{fancy}}
\fancyhf{{}}
\fancyfoot[C]{{\small\textcolor{{slate}}{{第 \thepage\ 页，共 \pageref{{LastPage}} 页}}}}
\renewcommand{{\headrulewidth}}{{0pt}}
\setlength{{\parindent}}{{0pt}}
\setlength{{\parskip}}{{0.45em}}
\newcommand{{\question}}[3]{{\noindent\textbf{{#1.}}\hspace{{0.35em}}#3\hfill\textcolor{{slate}}{{（#2分）}}\par}}
\newenvironment{{teacheranswer}}{{\begin{{quote}}\small\color{{accent}}}}{{\end{{quote}}}}
\ctexset{{section={{format=\normalsize\bfseries\color{{accent}},beforeskip=1.1em,afterskip=0.7em}}}}

\begin{{document}}
\begin{{center}}
  {{\LARGE\bfseries {title}{suffix}}}
\end{{center}}
\vspace{{1em}}

{body}

\end{{document}}
"""


def _teacher_answer_latex(item) -> list[str]:
    answer = _mixed_latex(item.final_answer or "暂无独立答案")
    result = ["\\begin{teacheranswer}", f"\\textbf{{答案：}}{answer}\\par"]
    if item.solution_steps:
        result.append("\\textbf{解析：}")
        result.append("\\begin{enumerate}[label=\\arabic*.,leftmargin=2em,topsep=0.2em]")
        result.extend(f"\\item {_mixed_latex(step)}" for step in item.solution_steps)
        result.append("\\end{enumerate}")
    if item.knowledge:
        knowledge = _latex_text("、".join(item.knowledge))
        result.append(f"\\noindent\\textcolor{{slate}}{{知识点：{knowledge}}}\\par")
    result.extend(["\\end{teacheranswer}", "\\vspace{0.5cm}"])
    return result


def _section_title(paper: PaperPreviewRead, question_type: str) -> str:
    items = [item for item in paper.items if item.question_type == question_type]
    score = sum(item.score for item in items)
    number = {"选择题": "一", "多选题": "二", "填空题": "三", "解答题": "四"}.get(
        question_type, "一"
    )
    descriptions = {
        "选择题": "每小题给出的选项中，只有一个选项正确。",
        "多选题": "每小题给出的选项中，有多项符合题目要求。",
        "填空题": "请将答案填写在题中横线上。",
        "解答题": "解答应写出文字说明、证明过程或演算步骤。",
    }
    average = score // len(items) if items and score % len(items) == 0 else None
    per_item = f"，每小题 {average} 分" if average is not None else ""
    return _latex_text(
        f"{number}、{question_type}（本大题共 {len(items)} 小题{per_item}，共 {score} 分。"
        f"{descriptions.get(question_type, '')}）"
    )


_MATH_PATTERN = re.compile(r"(\$\$.*?\$\$|\$.*?\$|\\\[.*?\\\]|\\\(.*?\\\))", re.DOTALL)
_OPTION_PATTERN = re.compile(r"^[A-D][.、．]\s*")


def _question_parts(value: str) -> tuple[str, list[str]]:
    lines = [line.strip() for line in value.splitlines() if line.strip()]
    options = [line for line in lines if _OPTION_PATTERN.match(line)]
    stem = " ".join(line for line in lines if not _OPTION_PATTERN.match(line))
    return stem, options


def _options_table(options: list[str]) -> str:
    if not options:
        return ""
    if len(options) == 4:
        cells = " & ".join(_mixed_latex(option) for option in options)
        return (
            "\\begin{tabularx}{\\textwidth}{@{}>{\\raggedright\\arraybackslash}X"
            ">{\\raggedright\\arraybackslash}X>{\\raggedright\\arraybackslash}X"
            ">{\\raggedright\\arraybackslash}X@{}}\n"
            f"{cells}\n\\end{{tabularx}}"
        )
    return "\\\\\n".join(_mixed_latex(option) for option in options)


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
