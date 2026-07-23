import { useState } from "react";
import { Button, Card, Col, Empty, Form, Input, InputNumber, message, Row, Select, Space, Spin, Statistic, Tag, Timeline, Typography } from "antd";
import { FilePdfOutlined, RobotOutlined, SafetyCertificateOutlined } from "@ant-design/icons";

const API = import.meta.env.VITE_API_URL ?? "http://127.0.0.1:8000/api/v1";

type Blueprint = {
  title: string; grade: string | null; total_questions: number; total_score: number;
  difficulty_min: number; difficulty_max: number; question_type_counts: Record<string, number>;
  knowledge_quotas: { name: string; count: number }[]; seed: number;
};
type Preview = { title: string; total_score: number; feasible: boolean; warnings: string[]; constraints: { name: string; required: string | number; actual: string | number; satisfied: boolean }[]; items: { question_id: string; question_text: string; question_type: string; score: number; knowledge: string[] }[] };
type AgentRun = { run_id: string; status: string; mode: string; final_response: string | null; steps_used: number; error_message: string | null; current_paper: Preview | null; traces: { step: number; actor: string; tool_name: string; status: string; duration_ms: number; result: Record<string, unknown> }[] };

const initial: Blueprint = { title: "初中数学测试卷", grade: "八年级", total_questions: 10, total_score: 100, difficulty_min: .35, difficulty_max: .65, question_type_counts: { 选择题: 4, 填空题: 2, 解答题: 4 }, knowledge_quotas: [], seed: 42 };

export default function App() {
  const [requirement, setRequirement] = useState("生成一套八年级一次函数测试卷，共10题100分，其中选择题4道、填空题2道、解答题4道，一次函数至少5题，难度中等");
  const [blueprint, setBlueprint] = useState<Blueprint>(initial);
  const [preview, setPreview] = useState<Preview | null>(null);
  const [agentRun, setAgentRun] = useState<AgentRun | null>(null);
  const [loading, setLoading] = useState(false);

  const call = async (path: string, body: unknown) => {
    const response = await fetch(`${API}${path}`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
    if (!response.ok) throw new Error((await response.json()).detail ?? "请求失败");
    return response;
  };
  const parse = async () => { setLoading(true); try { const r = await call("/papers/parse-requirement", { requirement }); setBlueprint(await r.json()); setPreview(null); message.success("已转换为可检查的组卷蓝图"); } catch (e) { message.error(String(e)); } finally { setLoading(false); } };
  const runAgent = async () => { setLoading(true); setAgentRun(null); try { const r = await call("/agents/runs", { request: requirement, mode: "multi_agent", max_steps: 12 }); const run = await r.json(); setAgentRun(run); if (run.current_paper) setPreview(run.current_paper); message.success("Agent调度完成"); } catch (e) { message.error(String(e)); } finally { setLoading(false); } };
  const compose = async () => { setLoading(true); try { const r = await call("/papers/preview", blueprint); setPreview(await r.json()); } catch (e) { message.error(String(e)); } finally { setLoading(false); } };
  const download = async (version: "student" | "teacher") => { try { const r = await call(`/papers/export/${version}`, blueprint); const url = URL.createObjectURL(await r.blob()); const a = document.createElement("a"); a.href = url; a.download = version === "student" ? "学生试卷.pdf" : "教师解析卷.pdf"; a.click(); URL.revokeObjectURL(url); } catch (e) { message.error(String(e)); } };
  const downloadLatex = async (version: "student" | "teacher") => { try { const r = await call(`/papers/export-latex/${version}`, blueprint); const url = URL.createObjectURL(await r.blob()); const a = document.createElement("a"); a.href = url; a.download = version === "student" ? "学生试卷.tex" : "教师解析卷.tex"; a.click(); URL.revokeObjectURL(url); } catch (e) { message.error(String(e)); } };
  const setType = (type: string, value: number | null) => setBlueprint({ ...blueprint, question_type_counts: { ...blueprint.question_type_counts, [type]: value ?? 0 } });

  return <div className="app-shell">
    <header><div className="brand"><RobotOutlined /> MathPaper Agent</div><Tag color="blue">中文初中数学</Tag></header>
    <main>
      <section className="hero"><Typography.Title>把组卷要求，变成可验证的试卷</Typography.Title><Typography.Paragraph>模型理解教师语言，约束算法负责选题；每一项要求都能检查、解释和复现。</Typography.Paragraph></section>
      <Row gutter={20} align="stretch">
        <Col xs={24} lg={10}><Card title="1. 描述组卷要求" className="panel"><Input.TextArea value={requirement} onChange={e => setRequirement(e.target.value)} rows={8}/><Space direction="vertical" className="action-stack"><Button type="primary" icon={<RobotOutlined />} block size="large" onClick={runAgent} loading={loading}>运行多 Agent 调度</Button><Button block onClick={parse} loading={loading}>仅解析组卷蓝图</Button></Space></Card></Col>
        <Col xs={24} lg={14}><Card title="2. 检查组卷蓝图" className="panel"><Form layout="vertical"><Row gutter={12}><Col span={16}><Form.Item label="试卷标题"><Input value={blueprint.title} onChange={e => setBlueprint({...blueprint,title:e.target.value})}/></Form.Item></Col><Col span={8}><Form.Item label="年级"><Select value={blueprint.grade} options={["七年级","八年级","九年级"].map(v=>({value:v,label:v}))} onChange={grade=>setBlueprint({...blueprint,grade})}/></Form.Item></Col></Row><Row gutter={12}><Col span={8}><Form.Item label="题目总数"><InputNumber min={1} value={blueprint.total_questions} onChange={v=>setBlueprint({...blueprint,total_questions:v??1})}/></Form.Item></Col><Col span={8}><Form.Item label="总分"><InputNumber min={1} value={blueprint.total_score} onChange={v=>setBlueprint({...blueprint,total_score:v??100})}/></Form.Item></Col><Col span={8}><Form.Item label="随机种子"><InputNumber value={blueprint.seed} onChange={v=>setBlueprint({...blueprint,seed:v??42})}/></Form.Item></Col></Row><Row gutter={12}>{["选择题","填空题","解答题"].map(t=><Col span={8} key={t}><Form.Item label={t}><InputNumber min={0} value={blueprint.question_type_counts[t]??0} onChange={v=>setType(t,v)}/></Form.Item></Col>)}</Row><Space wrap>{blueprint.knowledge_quotas.map(q=><Tag color="geekblue" key={q.name}>{q.name} ≥ {q.count}题</Tag>)}</Space><Button block size="large" onClick={compose} loading={loading}>生成并检查试卷</Button></Form></Card></Col>
      </Row>
      {agentRun && <Card title="Agent 调用轨迹" className="result" extra={<Tag color={agentRun.status === "completed" ? "success" : "error"}>{agentRun.status}</Tag>}><Timeline items={agentRun.traces.map(trace => ({ color: trace.status === "success" ? "green" : "red", children: <div><b>{trace.actor}</b> → <code>{trace.tool_name}</code><span className="trace-time">{trace.duration_ms} ms</span></div> }))}/><Typography.Paragraph className="agent-summary">{agentRun.final_response || agentRun.error_message}</Typography.Paragraph></Card>}
      <Spin spinning={loading}><Card title="3. 组卷结果" className="result">{!preview ? <Empty description="生成后显示题目和约束报告"/> : <><Row gutter={16}><Col span={8}><Statistic title="题目" value={preview.items.length}/></Col><Col span={8}><Statistic title="总分" value={preview.total_score}/></Col><Col span={8}><Statistic title="约束状态" value={preview.feasible?"全部满足":"存在缺口"} valueStyle={{color:preview.feasible?"#16a34a":"#dc2626"}}/></Col></Row><div className="checks">{preview.constraints.map(c=><Tag icon={<SafetyCertificateOutlined />} color={c.satisfied?"success":"error"} key={c.name}>{c.name} {c.actual}/{c.required}</Tag>)}</div>{preview.items.map((q,i)=><div className="question" key={q.question_id}><span>{i+1}. {q.question_text}</span><Space><Tag>{q.question_type}</Tag><b>{q.score}分</b></Space></div>)}<Space className="downloads" wrap><Button disabled={!preview.feasible} icon={<FilePdfOutlined />} onClick={()=>download("student")}>学生卷 PDF</Button><Button type="primary" disabled={!preview.feasible} icon={<FilePdfOutlined />} onClick={()=>download("teacher")}>解析卷 PDF</Button><Button disabled={!preview.feasible} onClick={()=>downloadLatex("student")}>学生卷 LaTeX</Button><Button disabled={!preview.feasible} onClick={()=>downloadLatex("teacher")}>解析卷 LaTeX</Button></Space></>}</Card></Spin>
    </main>
  </div>;
}
