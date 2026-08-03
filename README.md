# MathPaper Agent

面向中文初中数学教师的知识约束智能组卷系统。教师可以直接描述试卷要求，系统将其转换为可检查的结构化蓝图，再由确定性算法从题库选题，最终生成学生试卷和教师答案解析 PDF。

> 当前项目由旧高数原型独立重构而来，Python 包名暂时保留为 `calculus_agent`，不影响运行；后续稳定数据库迁移后再统一改名。

## 核心闭环

```text
CMM-Math 中文题目、答案与解析
→ 可信数据批量入库与知识点归一化
→ 教师自然语言要求
→ Qwen3 JSON Schema 解析 + 明示规则兜底
→ 可编辑 Exam Blueprint
→ 确定性约束选题
→ 约束满足报告
→ 学生卷 PDF + 教师解析卷 PDF
```

LLM 只负责理解语言和整理解析，不直接决定最终选题。相同题库、蓝图和随机种子会产生可复现结果；题库不足时返回具体未满足约束，不会偷偷降低要求。

## Agent 调度架构

系统同时保留单 Agent 基线和多 Agent 路径，用于真实对比，而不是默认假设多 Agent 更好：

```text
PaperOrchestratorAgent
├── delegate_agent → KnowledgeStewardAgent
│   ├── search_knowledge
│   └── inspect_question_supply
├── compose_paper（确定性工具）
└── delegate_agent → PaperReviewerAgent
    └── validate_current_paper
```

子 Agent拥有独立消息上下文和工具白名单，不能继续创建下级 Agent。每次运行限制最大工具步数和最大委托次数，并拦截连续重复调用。调用主体、参数、结果、状态和耗时持久化为轨迹。

## 已实现

- CMM-Math JSONL 适配，可筛选初中年级、纯文本题以及带完整解析的记录；
- MM-Math 适配与字段审计保留为英文多模态数据实验入口；
- 可信公开数据集批量发布；以后 OCR/教师自有题目仍可走草稿审核流程；
- `qwen3:14b` 本地自然语言组卷需求解析；
- 年级和难度显式表达的规则兜底；
- 年级、难度、题型数量、知识点配额、总题量和总分约束；
- 约束报告和无法组卷原因；
- React + TypeScript + Ant Design 教师端；
- 支持锁定满意题目、单题换题和排除已换题目，重组后重新验证全部约束；
- 支持保存试卷草稿、浏览历史版本、载入旧版本并另存为新版本；
- 支持按题干搜索已审核题库、手动加题、调整题序和覆盖单题分值；
- 自动对比相邻试卷版本，显示增删题、题序、分值和蓝图字段变化；
- 学生卷采用标准 A4 校内试卷版式，选择项横向排列，解答题独立成节并按分值预留答题区域；
- 嵌入中文字体的学生卷和教师解析卷 PDF；
- 可二次编辑的学生卷和教师解析卷 LaTeX 源文件；
- UGMathBench 旧适配器保留为可选外部评测入口。
- 主调度 Agent、知识库 Agent和试卷审核 Agent；
- 单 Agent与多 Agent两种运行模式；
- 工具白名单、步数预算、委托预算和重复调用防护；
- Agent运行和工具调用轨迹持久化；
- 工具选择、调用顺序、专业 Agent覆盖和禁用工具评测指标。

## 朋友本地试用

要求电脑已安装 Python 工具 `uv`、Node.js 18+ 和 `pnpm`。克隆项目后，一条命令
完成依赖安装、演示题库初始化和启动：

```bash
./scripts/quickstart.sh
```

打开 `http://127.0.0.1:5173`。安装脚本会自动安装前后端依赖、创建本地
SQLite 数据库并写入15道内置演示题；重复执行不会重复导入。

以后再次启动不需要重装依赖：

```bash
./scripts/start.sh
```

如果想让同一局域网的朋友访问，在你的电脑运行：

```bash
HOST=0.0.0.0 ./scripts/start.sh
```

朋友打开 `http://你的电脑IP:5173`。你的电脑需要保持开机，且防火墙需要允许
5173和8000端口。正式公网试用仍应部署到服务器，不要直接暴露开发服务。

基础组卷、锁题换题、版本保存和PDF导出不依赖 Ollama。自然语言解析与多 Agent
调度是可选能力；需要时启动 Ollama 并安装 `qwen3:14b`：

```bash
ollama serve
ollama pull qwen3:14b
```

后端 API 文档位于 `http://127.0.0.1:8000/docs`。

Linux 环境需要提供中文字体路径：

```bash
export MATH_PAPER_FONT_PATH=/path/to/NotoSansCJK-Regular.ttc
```

## 导入中文 CMM-Math

从官方数据集下载 `all_data.jsonl`，调用
`POST /api/v1/datasets/cmm-math/import`：

```json
{
  "path": "/absolute/path/to/all_data.jsonl",
  "levels": ["七年级", "八年级", "九年级"],
  "text_only": true,
  "require_analysis": true,
  "limit": 3000,
  "publish": true
}
```

首版建议保持 `text_only=true`，因为当前 PDF 渲染链路尚未支持题目多图。
`require_analysis=true` 会排除只有答案、没有解析的记录。`publish=true`
仅适用于已经确认来源和字段质量的可信数据；教师后续上传或 OCR
识别的内容不应跳过审核。完整审计见
[数据集审计](docs/dataset-audit.md)。

## 关键接口

- `POST /api/v1/papers/parse-requirement`：自然语言转组卷蓝图；
- `POST /api/v1/papers/preview`：确定性选题与约束报告；
- `POST /api/v1/papers/export/student`：学生试卷 PDF；
- `POST /api/v1/papers/export/teacher`：教师解析卷 PDF；
- `POST /api/v1/papers/export-latex/student`：学生试卷 `.tex`；
- `POST /api/v1/papers/export-latex/teacher`：教师解析卷 `.tex`；
- `POST /api/v1/datasets/cmm-math/import`：中文 K12 题库筛选导入；
- `POST /api/v1/datasets/mm-math/import`：英文多模态 MM-Math 实验导入；
- `POST /api/v1/agents/runs`：执行单 Agent或多 Agent组卷任务；
- `GET /api/v1/agents/runs/{run_id}`：读取持久化调度轨迹。

## Agent 路由评测

评测样例位于 `evaluations/cases.jsonl`，同一批任务可以分别运行：

```bash
uv run python -m calculus_agent.evaluations.runner \
  --mode single_agent --output output/evaluations/single-agent.json

uv run python -m calculus_agent.evaluations.runner \
  --mode multi_agent --output output/evaluations/multi-agent.json
```

当前指标包括工具选择精确率、召回率、调用顺序得分、要求的专业 Agent覆盖率和禁用工具调用次数。正式结论必须在真实题库导入后运行完整评测集得到。

## 验证

```bash
uv run pytest
uv run ruff check src tests
cd web && pnpm build
```

当前自动化测试：23 项全部通过；前端 TypeScript 检查和生产构建通过。PDF
已使用 Poppler 渲染为图片并检查中文字体、分页、页码和解析布局。

## 下一阶段

- 用知识分类 Agent 将 CMM-Math 的粗粒度 `subject` 映射到教材目录知识节点；
- 对未知难度进行离线标注和抽样复核，未标注前不宣称可精确控难；
- 题目图片与 LaTeX 公式的高质量 PDF 排版；
- 增加拖拽排序、更多学校页眉模板和版本恢复操作；
- 建立组卷成功率、知识点覆盖率和难度偏差评测；
- 最后补 Docker 一键启动与公开 Demo；
- OCR 作为独立输入适配器接入，不改变组卷核心。
