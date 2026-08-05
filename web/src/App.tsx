import { useEffect, useState } from "react";
import { Button, Card, Col, Empty, Form, Input, InputNumber, message, Row, Select, Space, Spin, Statistic, Tag, Timeline, Typography, Upload } from "antd";
import { ArrowDownOutlined, ArrowUpOutlined, FileImageOutlined, FilePdfOutlined, HistoryOutlined, LockOutlined, PlusOutlined, ReloadOutlined, RobotOutlined, SafetyCertificateOutlined, SaveOutlined, UnlockOutlined } from "@ant-design/icons";

const API = import.meta.env.VITE_API_URL ?? `${window.location.protocol}//${window.location.hostname}:8000/api/v1`;

type Blueprint = {
  title: string; grade: string | null; total_questions: number; total_score: number;
  difficulty_min: number; difficulty_max: number; question_type_counts: Record<string, number>;
  knowledge_quotas: { name: string; count: number }[]; locked_question_ids: string[];
  manual_question_ids: string[]; excluded_question_ids: string[]; question_order: string[];
  score_overrides: Record<string, number>; seed: number;
};
type Preview = { title: string; total_score: number; feasible: boolean; warnings: string[]; constraints: { name: string; required: string | number; actual: string | number; satisfied: boolean }[]; items: { question_id: string; question_text: string; question_type: string; score: number; knowledge: string[] }[] };
type AgentRun = { run_id: string; status: string; mode: string; final_response: string | null; steps_used: number; error_message: string | null; current_paper: Preview | null; traces: { step: number; actor: string; tool_name: string; status: string; duration_ms: number; result: Record<string, unknown> }[] };
type PaperDraft = { id: string; parent_id: string | null; title: string; blueprint: Blueprint; preview: Preview; status: string; created_at: string };
type QuestionOption = { id: string; question_text: string; question_type: string; difficulty: number | null; knowledge: string[] };
type PaperChange = { question_id: string; question_text: string; before: number | null; after: number | null };
type PaperDiff = { base_draft_id: string; target_draft_id: string; added: PaperChange[]; removed: PaperChange[]; order_changes: PaperChange[]; score_changes: PaperChange[]; blueprint_changes: Record<string, { before: string | number | null; after: string | number | null }>; has_changes: boolean };
type PrepMatch = { question_id: string; question_text: string; question_type: string; difficulty: number | null; final_answer: string | null; solution_steps: string[]; knowledge: string[]; match_reasons: string[] };
type PrepResult = { id: string; error_reason: string; knowledge_names: string[]; matches: PrepMatch[] };
type VisionExtract = { question_text: string; options: string[]; question_type: string; final_answer: string; solution_text: string; knowledge_names: string[]; needs_review: boolean; warnings: string[] };

const initial: Blueprint = { title: "初中数学测试卷", grade: "八年级", total_questions: 10, total_score: 100, difficulty_min: .35, difficulty_max: .65, question_type_counts: { 选择题: 4, 填空题: 2, 解答题: 4 }, knowledge_quotas: [], locked_question_ids: [], manual_question_ids: [], excluded_question_ids: [], question_order: [], score_overrides: {}, seed: 42 };

export default function App() {
  const [requirement, setRequirement] = useState("生成一套八年级一次函数测试卷，共10题100分，其中选择题4道、填空题2道、解答题4道，一次函数至少5题，难度中等");
  const [blueprint, setBlueprint] = useState<Blueprint>(initial);
  const [preview, setPreview] = useState<Preview | null>(null);
  const [agentRun, setAgentRun] = useState<AgentRun | null>(null);
  const [drafts, setDrafts] = useState<PaperDraft[]>([]);
  const [activeDraftId, setActiveDraftId] = useState<string | null>(null);
  const [questionOptions, setQuestionOptions] = useState<QuestionOption[]>([]);
  const [selectedQuestionId, setSelectedQuestionId] = useState<string | null>(null);
  const [versionDiff, setVersionDiff] = useState<PaperDiff | null>(null);
  const [prepInput, setPrepInput] = useState({ grade: "八年级", question_text: "", final_answer: "", solution_text: "", error_reason: "", question_type: "解答题", target_difficulty: 0.5, knowledge_names: "一次函数", match_count: 5 });
  const [prepResult, setPrepResult] = useState<PrepResult | null>(null);
  const [prepLoading, setPrepLoading] = useState(false);
  const [questionImage, setQuestionImage] = useState<string | null>(null);
  const [solutionImage, setSolutionImage] = useState<string | null>(null);
  const [questionImageName, setQuestionImageName] = useState<string | null>(null);
  const [solutionImageName, setSolutionImageName] = useState<string | null>(null);
  const [visionWarnings, setVisionWarnings] = useState<string[]>([]);
  const [visionLoading, setVisionLoading] = useState(false);
  const [loading, setLoading] = useState(false);

  const call = async (path: string, body: unknown) => {
    const response = await fetch(`${API}${path}`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
    if (!response.ok) throw new Error((await response.json()).detail ?? "请求失败");
    return response;
  };
  const refreshDrafts = async () => {
    try {
      const response = await fetch(`${API}/papers/drafts`);
      if (!response.ok) throw new Error("读取草稿失败");
      setDrafts(await response.json());
    } catch (error) {
      message.error(String(error));
    }
  };
  const loadVersionDiff = async (draftId: string, parentId: string | null) => {
    if (!parentId) {
      setVersionDiff(null);
      return;
    }
    try {
      const response = await fetch(`${API}/papers/drafts/${draftId}/diff`);
      if (!response.ok) throw new Error("读取版本差异失败");
      setVersionDiff(await response.json());
    } catch (error) {
      setVersionDiff(null);
      message.error(String(error));
    }
  };
  useEffect(() => { void refreshDrafts(); }, []);
  const parse = async () => { setLoading(true); try { const r = await call("/papers/parse-requirement", { requirement }); const parsed = await r.json(); setBlueprint({ ...parsed, locked_question_ids: [], manual_question_ids: [], excluded_question_ids: [], question_order: [], score_overrides: {} }); setPreview(null); message.success("已转换为可检查的组卷蓝图"); } catch (e) { message.error(String(e)); } finally { setLoading(false); } };
  const runAgent = async () => { setLoading(true); setAgentRun(null); try { const r = await call("/agents/runs", { request: requirement, mode: "multi_agent", max_steps: 12 }); const run: AgentRun = await r.json(); setAgentRun(run); if (run.current_paper) setPreview(run.current_paper); if (run.status === "failed") message.error(run.error_message ?? "Agent 调度失败"); else if (run.status === "needs_revision") message.warning("Agent 已完成，但试卷存在未满足的约束"); else message.success("Agent 调度完成"); } catch (e) { message.error(String(e)); } finally { setLoading(false); } };
  const compose = async (nextBlueprint: Blueprint = blueprint) => { setLoading(true); try { const r = await call("/papers/preview", nextBlueprint); setPreview(await r.json()); } catch (e) { message.error(String(e)); } finally { setLoading(false); } };
  const download = async (version: "student" | "teacher") => { try { const r = await call(`/papers/export/${version}`, blueprint); const url = URL.createObjectURL(await r.blob()); const a = document.createElement("a"); a.href = url; a.download = version === "student" ? "学生试卷.pdf" : "教师解析卷.pdf"; a.click(); URL.revokeObjectURL(url); } catch (e) { message.error(String(e)); } };
  const downloadLatex = async (version: "student" | "teacher") => { try { const r = await call(`/papers/export-latex/${version}`, blueprint); const url = URL.createObjectURL(await r.blob()); const a = document.createElement("a"); a.href = url; a.download = version === "student" ? "学生试卷.tex" : "教师解析卷.tex"; a.click(); URL.revokeObjectURL(url); } catch (e) { message.error(String(e)); } };
  const setType = (type: string, value: number | null) => setBlueprint({ ...blueprint, question_type_counts: { ...blueprint.question_type_counts, [type]: value ?? 0 } });
  const toggleLock = (questionId: string) => {
    const locked = blueprint.locked_question_ids.includes(questionId);
    setBlueprint({
      ...blueprint,
      locked_question_ids: locked
        ? blueprint.locked_question_ids.filter(id => id !== questionId)
        : [...blueprint.locked_question_ids, questionId],
    });
  };
  const replaceQuestion = async (questionId: string) => {
    const nextBlueprint = {
      ...blueprint,
      seed: blueprint.seed + 1,
      locked_question_ids: blueprint.locked_question_ids.filter(id => id !== questionId),
      manual_question_ids: blueprint.manual_question_ids.filter(id => id !== questionId),
      excluded_question_ids: Array.from(new Set([...blueprint.excluded_question_ids, questionId])),
      question_order: blueprint.question_order.filter(id => id !== questionId),
      score_overrides: Object.fromEntries(Object.entries(blueprint.score_overrides).filter(([id]) => id !== questionId)),
    };
    setBlueprint(nextBlueprint);
    await compose(nextBlueprint);
  };
  const saveDraft = async () => {
    setLoading(true);
    try {
      const response = await call("/papers/drafts", {
        blueprint,
        parent_id: activeDraftId,
      });
      const saved: PaperDraft = await response.json();
      setActiveDraftId(saved.id);
      setPreview(saved.preview);
      await refreshDrafts();
      await loadVersionDiff(saved.id, saved.parent_id);
      message.success(activeDraftId ? "已保存为新版本" : "试卷草稿已保存");
    } catch (error) {
      message.error(String(error));
    } finally {
      setLoading(false);
    }
  };
  const loadDraft = (draftId: string) => {
    const draft = drafts.find(item => item.id === draftId);
    if (!draft) return;
    setActiveDraftId(draft.id);
    setBlueprint(draft.blueprint);
    setPreview(draft.preview);
    setAgentRun(null);
    void loadVersionDiff(draft.id, draft.parent_id);
    message.success("已载入历史试卷，可继续修改并保存新版本");
  };
  const searchQuestionBank = async (query: string) => {
    const params = new URLSearchParams({ query, limit: "20" });
    if (blueprint.grade) params.set("grade", blueprint.grade);
    try {
      const response = await fetch(`${API}/questions/search?${params}`);
      if (!response.ok) throw new Error("搜索题库失败");
      setQuestionOptions(await response.json());
    } catch (error) {
      message.error(String(error));
    }
  };
  const addManualQuestion = async () => {
    if (!selectedQuestionId) return;
    const nextBlueprint = {
      ...blueprint,
      manual_question_ids: Array.from(new Set([...blueprint.manual_question_ids, selectedQuestionId])),
      excluded_question_ids: blueprint.excluded_question_ids.filter(id => id !== selectedQuestionId),
      question_order: [...(preview?.items.map(item => item.question_id) ?? []), selectedQuestionId],
    };
    setBlueprint(nextBlueprint);
    setSelectedQuestionId(null);
    await compose(nextBlueprint);
  };
  const moveQuestion = async (questionId: string, offset: -1 | 1) => {
    if (!preview) return;
    const order = preview.items.map(item => item.question_id);
    const index = order.indexOf(questionId);
    const target = index + offset;
    if (target < 0 || target >= order.length) return;
    [order[index], order[target]] = [order[target], order[index]];
    const nextBlueprint = { ...blueprint, question_order: order };
    setBlueprint(nextBlueprint);
    await compose(nextBlueprint);
  };
  const setQuestionScore = (questionId: string, score: number | null) => {
    if (score === null) return;
    setBlueprint({
      ...blueprint,
      score_overrides: { ...blueprint.score_overrides, [questionId]: score },
    });
  };
  const createPrepTask = async () => {
    setPrepLoading(true);
    try {
      const response = await call("/prep/mistakes", {
        ...prepInput,
        knowledge_names: prepInput.knowledge_names.split(/[，,、]/).map(value => value.trim()).filter(Boolean),
      });
      const result: PrepResult = await response.json();
      setPrepResult(result);
      message.success(`已保存错题任务并匹配 ${result.matches.length} 道巩固题`);
    } catch (error) {
      message.error(String(error));
    } finally {
      setPrepLoading(false);
    }
  };
  const selectImage = async (file: File, kind: "question" | "solution") => {
    if (!(["image/jpeg", "image/png", "image/webp"].includes(file.type))) {
      message.error("仅支持 JPG、PNG 或 WebP 图片");
      return;
    }
    if (file.size > 10 * 1024 * 1024) {
      message.error("单张图片不能超过 10 MB");
      return;
    }
    const dataUrl = await new Promise<string>((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => resolve(String(reader.result));
      reader.onerror = () => reject(new Error("读取图片失败"));
      reader.readAsDataURL(file);
    });
    if (kind === "question") {
      setQuestionImage(dataUrl);
      setQuestionImageName(file.name);
    } else {
      setSolutionImage(dataUrl);
      setSolutionImageName(file.name);
    }
  };
  const recognizeImages = async () => {
    if (!questionImage) return;
    setVisionLoading(true);
    try {
      const response = await call("/prep/vision/extract", { question_image: questionImage, solution_image: solutionImage });
      const result: VisionExtract = await response.json();
      const questionText = [result.question_text, ...result.options].filter(Boolean).join("\n");
      setPrepInput({
        ...prepInput,
        question_text: questionText,
        final_answer: result.final_answer,
        solution_text: result.solution_text,
        question_type: result.question_type,
        knowledge_names: result.knowledge_names.join("，"),
      });
      setVisionWarnings(result.warnings);
      message.success("图片识别完成，请检查并修改识别结果后再保存");
    } catch (error) {
      message.error(String(error));
    } finally {
      setVisionLoading(false);
    }
  };

  return <div className="app-shell">
    <header><div className="brand"><RobotOutlined /> MathPaper Agent</div><Tag color="blue">中文初中数学</Tag></header>
    <main>
      <section className="hero"><Typography.Title>教师备课 Agent</Typography.Title><Typography.Paragraph>从错题诊断到针对性练习，再到可验证组卷与教学材料生成。</Typography.Paragraph></section>
      <Card title="错题备课任务" className="prep-card" extra={<Tag color="purple">第一版：教师提供错误原因</Tag>}>
        <Typography.Paragraph type="secondary">填写错题、标准答案、解析以及你从 ChatGPT 得到的错误原因；系统从已审核题库匹配同知识点、相近难度的巩固题。</Typography.Paragraph>
        <div className="vision-upload">
          <Space wrap>
            <Upload accept=".jpg,.jpeg,.png,.webp" showUploadList={false} beforeUpload={file=>{void selectImage(file,"question");return false;}}><Button icon={<FileImageOutlined/>}>选择题目图片</Button></Upload>
            <Typography.Text type={questionImageName?undefined:"secondary"}>{questionImageName??"必选：标准印刷题图片"}</Typography.Text>
            <Upload accept=".jpg,.jpeg,.png,.webp" showUploadList={false} beforeUpload={file=>{void selectImage(file,"solution");return false;}}><Button icon={<FileImageOutlined/>}>选择答案/解析图片</Button></Upload>
            <Typography.Text type={solutionImageName?undefined:"secondary"}>{solutionImageName??"可选"}</Typography.Text>
            <Button type="primary" ghost loading={visionLoading} disabled={!questionImage} onClick={recognizeImages}>用硅基流动识别并回填</Button>
          </Space>
          {!!visionWarnings.length&&<div className="vision-warnings">{visionWarnings.map(warning=><Tag color="warning" key={warning}>{warning}</Tag>)}</div>}
        </div>
        <Row gutter={14}>
          <Col xs={24} lg={12}><Form.Item label="错题题目" required><Input.TextArea rows={4} value={prepInput.question_text} onChange={event=>setPrepInput({...prepInput,question_text:event.target.value})}/></Form.Item></Col>
          <Col xs={24} lg={12}><Form.Item label="标准解析" required><Input.TextArea rows={4} value={prepInput.solution_text} onChange={event=>setPrepInput({...prepInput,solution_text:event.target.value})}/></Form.Item></Col>
        </Row>
        <Row gutter={14}>
          <Col xs={24} lg={12}><Form.Item label="标准答案" required><Input value={prepInput.final_answer} onChange={event=>setPrepInput({...prepInput,final_answer:event.target.value})}/></Form.Item></Col>
          <Col xs={24} lg={12}><Form.Item label="学生错误原因（由教师或 ChatGPT 提供）" required><Input value={prepInput.error_reason} onChange={event=>setPrepInput({...prepInput,error_reason:event.target.value})}/></Form.Item></Col>
        </Row>
        <Row gutter={14}>
          <Col xs={12} md={5}><Form.Item label="年级"><Select value={prepInput.grade} options={["七年级","八年级","九年级"].map(value=>({value,label:value}))} onChange={grade=>setPrepInput({...prepInput,grade})}/></Form.Item></Col>
          <Col xs={12} md={5}><Form.Item label="题型"><Select value={prepInput.question_type} options={["选择题","填空题","解答题"].map(value=>({value,label:value}))} onChange={question_type=>setPrepInput({...prepInput,question_type})}/></Form.Item></Col>
          <Col xs={24} md={6}><Form.Item label="目标知识点（逗号分隔）"><Input value={prepInput.knowledge_names} onChange={event=>setPrepInput({...prepInput,knowledge_names:event.target.value})}/></Form.Item></Col>
          <Col xs={12} md={4}><Form.Item label="目标难度"><InputNumber min={0} max={1} step={0.1} value={prepInput.target_difficulty} onChange={value=>setPrepInput({...prepInput,target_difficulty:value??0.5})}/></Form.Item></Col>
          <Col xs={12} md={4}><Form.Item label="匹配数量"><InputNumber min={1} max={20} value={prepInput.match_count} onChange={value=>setPrepInput({...prepInput,match_count:value??5})}/></Form.Item></Col>
        </Row>
        <Button type="primary" icon={<RobotOutlined/>} loading={prepLoading} disabled={!prepInput.question_text.trim()||!prepInput.final_answer.trim()||!prepInput.solution_text.trim()||!prepInput.error_reason.trim()||!prepInput.knowledge_names.trim()} onClick={createPrepTask}>保存并匹配巩固题</Button>
        {prepResult && <div className="prep-results"><Typography.Title level={4}>匹配结果</Typography.Title>{!prepResult.matches.length?<Empty description="当前题库没有匹配题，请调整知识点或先扩充题库"/>:prepResult.matches.map((item,index)=><div className="prep-match" key={item.question_id}><div><Typography.Text strong>{index+1}. {item.question_text}</Typography.Text><div className="prep-tags"><Tag>{item.question_type}</Tag>{item.knowledge.map(name=><Tag color="geekblue" key={name}>{name}</Tag>)}{item.match_reasons.map(reason=><Tag color="green" key={reason}>{reason}</Tag>)}</div></div><Typography.Paragraph><b>答案：</b>{item.final_answer??"暂无"}</Typography.Paragraph><Typography.Paragraph><b>解析：</b>{item.solution_steps.join(" ")||"暂无"}</Typography.Paragraph></div>)}</div>}
      </Card>
      <Row gutter={20} align="stretch">
        <Col xs={24} lg={10}><Card title="1. 描述组卷要求" className="panel"><Input.TextArea value={requirement} onChange={e => setRequirement(e.target.value)} rows={8}/><Space direction="vertical" className="action-stack"><Button type="primary" icon={<RobotOutlined />} block size="large" onClick={runAgent} loading={loading}>运行多 Agent 调度</Button><Button block onClick={parse} loading={loading}>仅解析组卷蓝图</Button></Space></Card></Col>
        <Col xs={24} lg={14}><Card title="2. 检查组卷蓝图" className="panel"><Form layout="vertical"><Row gutter={12}><Col span={16}><Form.Item label="试卷标题"><Input value={blueprint.title} onChange={e => setBlueprint({...blueprint,title:e.target.value})}/></Form.Item></Col><Col span={8}><Form.Item label="年级"><Select value={blueprint.grade} options={["七年级","八年级","九年级"].map(v=>({value:v,label:v}))} onChange={grade=>setBlueprint({...blueprint,grade})}/></Form.Item></Col></Row><Row gutter={12}><Col span={8}><Form.Item label="题目总数"><InputNumber min={1} value={blueprint.total_questions} onChange={v=>setBlueprint({...blueprint,total_questions:v??1})}/></Form.Item></Col><Col span={8}><Form.Item label="总分"><InputNumber min={1} value={blueprint.total_score} onChange={v=>setBlueprint({...blueprint,total_score:v??100})}/></Form.Item></Col><Col span={8}><Form.Item label="随机种子"><InputNumber value={blueprint.seed} onChange={v=>setBlueprint({...blueprint,seed:v??42})}/></Form.Item></Col></Row><Row gutter={12}>{["选择题","填空题","解答题"].map(t=><Col span={8} key={t}><Form.Item label={t}><InputNumber min={0} value={blueprint.question_type_counts[t]??0} onChange={v=>setType(t,v)}/></Form.Item></Col>)}</Row><Space wrap>{blueprint.knowledge_quotas.map(q=><Tag color="geekblue" key={q.name}>{q.name} ≥ {q.count}题</Tag>)}</Space><Button block size="large" onClick={()=>compose()} loading={loading}>生成并检查试卷</Button></Form></Card></Col>
      </Row>
      {agentRun && <Card title="Agent 调用轨迹" className="result" extra={<Tag color={agentRun.status === "completed" ? "success" : "error"}>{agentRun.status}</Tag>}><Timeline items={agentRun.traces.map(trace => ({ color: trace.status === "success" ? "green" : "red", children: <div><b>{trace.actor}</b> → <code>{trace.tool_name}</code><span className="trace-time">{trace.duration_ms} ms</span></div> }))}/><Typography.Paragraph className="agent-summary">{agentRun.final_response || agentRun.error_message}</Typography.Paragraph></Card>}
      <Card title="试卷草稿与版本" className="result" extra={<HistoryOutlined />}>
        <Row gutter={12} align="middle">
          <Col xs={24} md={16}>
            <Select
              allowClear
              showSearch
              value={activeDraftId}
              placeholder={drafts.length ? "选择历史试卷" : "还没有保存的试卷"}
              optionFilterProp="label"
              options={drafts.map(draft => ({
                value: draft.id,
                label: `${draft.title} · ${new Date(draft.created_at).toLocaleString()}`,
              }))}
              onChange={value => value ? loadDraft(value) : (setActiveDraftId(null), setVersionDiff(null))}
              className="draft-select"
            />
          </Col>
          <Col xs={24} md={8}>
            <Button type="primary" block icon={<SaveOutlined />} disabled={!preview} loading={loading} onClick={saveDraft}>
              {activeDraftId ? "保存为新版本" : "保存当前试卷"}
            </Button>
          </Col>
        </Row>
        {activeDraftId && <Typography.Paragraph type="secondary" className="draft-hint">当前载入的是历史版本；再次保存会创建新版本，不覆盖原记录。</Typography.Paragraph>}
        {versionDiff && <div className="version-diff">
          <Typography.Text strong>与上一版本相比</Typography.Text>
          {!versionDiff.has_changes ? <Tag color="default">没有内容变化</Tag> : <Space direction="vertical" size={6}>
            {!!versionDiff.added.length && <div><Tag color="success">新增 {versionDiff.added.length} 题</Tag>{versionDiff.added.map(item=><span className="diff-item" key={`add-${item.question_id}`}>{item.question_text}</span>)}</div>}
            {!!versionDiff.removed.length && <div><Tag color="error">删除 {versionDiff.removed.length} 题</Tag>{versionDiff.removed.map(item=><span className="diff-item" key={`remove-${item.question_id}`}>{item.question_text}</span>)}</div>}
            {!!versionDiff.order_changes.length && <div><Tag color="blue">题序变化 {versionDiff.order_changes.length} 题</Tag>{versionDiff.order_changes.map(item=><span className="diff-item" key={`order-${item.question_id}`}>第 {item.before} → 第 {item.after} 题</span>)}</div>}
            {!!versionDiff.score_changes.length && <div><Tag color="gold">分值变化 {versionDiff.score_changes.length} 题</Tag>{versionDiff.score_changes.map(item=><span className="diff-item" key={`score-${item.question_id}`}>{item.before} → {item.after} 分</span>)}</div>}
            {Object.entries(versionDiff.blueprint_changes).map(([field, change])=><div key={field}><Tag color="purple">{field}</Tag><span className="diff-item">{String(change.before)} → {String(change.after)}</span></div>)}
          </Space>}
        </div>}
      </Card>
      <Spin spinning={loading}><Card title="3. 组卷结果" className="result">{!preview ? <Empty description="生成后显示题目和约束报告"/> : <><Row gutter={16}><Col span={8}><Statistic title="题目" value={preview.items.length}/></Col><Col span={8}><Statistic title="总分" value={preview.total_score}/></Col><Col span={8}><Statistic title="约束状态" value={preview.feasible?"全部满足":"存在缺口"} valueStyle={{color:preview.feasible?"#16a34a":"#dc2626"}}/></Col></Row><div className="checks">{preview.constraints.map(c=><Tag icon={<SafetyCertificateOutlined />} color={c.satisfied?"success":"error"} key={c.name}>{c.name} {c.actual}/{c.required}</Tag>)}</div><Typography.Paragraph type="secondary">锁定满意题目后，可单独更换其他题；也可以调整题序、指定单题分值或从题库手动加题。</Typography.Paragraph><div className="manual-add"><Input.Search placeholder="输入题干关键词搜索当前年级题库" enterButton="搜索" onSearch={searchQuestionBank}/><Select showSearch optionFilterProp="label" placeholder="选择要加入的题目" value={selectedQuestionId} onChange={setSelectedQuestionId} options={questionOptions.map(item=>({value:item.id,label:`[${item.question_type}] ${item.question_text}`}))}/><Button icon={<PlusOutlined/>} disabled={!selectedQuestionId} onClick={addManualQuestion}>加入试卷</Button></div>{preview.items.map((q,i)=>{const locked=blueprint.locked_question_ids.includes(q.question_id);return <div className={`question ${locked?"question-locked":""}`} key={q.question_id}><span>{i+1}. {q.question_text}</span><Space wrap><Tag>{q.question_type}</Tag><InputNumber size="small" min={1} max={blueprint.total_score} value={blueprint.score_overrides[q.question_id]??q.score} onChange={value=>setQuestionScore(q.question_id,value)} addonAfter="分"/><Button size="small" icon={<ArrowUpOutlined/>} disabled={i===0||loading} onClick={()=>moveQuestion(q.question_id,-1)}/><Button size="small" icon={<ArrowDownOutlined/>} disabled={i===preview.items.length-1||loading} onClick={()=>moveQuestion(q.question_id,1)}/><Button size="small" type={locked?"primary":"default"} icon={locked?<UnlockOutlined/>:<LockOutlined/>} onClick={()=>toggleLock(q.question_id)}>{locked?"取消锁定":"锁定"}</Button><Button size="small" icon={<ReloadOutlined/>} disabled={locked||loading} onClick={()=>replaceQuestion(q.question_id)}>换一题</Button></Space></div>})}<Space className="downloads" wrap><Button onClick={()=>compose()}>应用分值并重新检查</Button><Button disabled={!preview.feasible} icon={<FilePdfOutlined />} onClick={()=>download("student")}>学生卷 PDF</Button><Button type="primary" disabled={!preview.feasible} icon={<FilePdfOutlined />} onClick={()=>download("teacher")}>解析卷 PDF</Button><Button disabled={!preview.feasible} onClick={()=>downloadLatex("student")}>学生卷 LaTeX</Button><Button disabled={!preview.feasible} onClick={()=>downloadLatex("teacher")}>解析卷 LaTeX</Button></Space></>}</Card></Spin>
    </main>
  </div>;
}
