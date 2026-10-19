# 【设计文档】健康咨询 AI Agent —— 开源技术演示项目

> 本文档改编自原始产品需求文档《AI问诊-健康咨询回复Agent》。原文档面向真实业务场景（接入医院/互联网医院系统、对接真实知识库与医生工作台）；本项目的目标是**把其中的 Agent 架构设计、安全兜底机制、质检闭环，还原成一个可以在个人电脑上独立运行的开源技术演示项目**，用于求职过程中讲清楚"这个 Agent 是怎么设计的、为什么这么设计"。
>
> 文档中标注 **【新增】** 的部分是原 PRD 没有、本项目补充设计的内容（核心是质检/自检模块）；标注 **【简化】** 的部分是原 PRD 依赖真实业务资产（知识库、医生工作台、预问诊Agent等），本项目用轻量方案替代的部分。

---

## 一、项目背景与目标

### 1.1 为什么做这个项目

医疗/健康咨询场景下，AI 不能像通用聊天机器人一样自由发挥——它必须在"有用"和"不能替代医生"之间做大量的工程化约束。这正是这个场景在 Agent 设计上最有技术含量的地方：

- 怎么让 AI 知道"这个问题我能答" vs "这个问题必须转人工"；
- 怎么防止 AI 的回答超出知识库授权范围、凭自己的知识"自由发挥"（幻觉风险）；
- 怎么在保证安全的前提下，不把用户体验做成一问一句"转人工"的机械客服。

原 PRD 把这套机制设计得比较完整（四层路由决策 + 多类异常兜底），但**遗漏了"模型最终输出内容本身的质检"这一环**——所有判断（命中知识库与否、人群状态、是否该追问）做完之后，生成出来的自然语言回复有没有真的符合这些判断的约束，原设计里没有校验手段。这是本项目在架构上重点补齐、也是最值得在 demo 里演示的部分。

### 1.2 作为开源作品要证明的技术能力

| 能力点 | 对应设计 |
|---|---|
| Agent 工程化拆解能力 | 意图识别→语义解析→检索→调度→生成→质检 的分层架构，每层职责单一、可独立测试 |
| 安全优先的系统设计思维 | L0/L1 双层前置拦截、特殊人群处理、红旗关键词兜底 |
| 对"LLM不可靠"的工程化应对 | 结构化标签 + 知识库锚定生成 + 质检闭环，而不是"相信模型会听话" |
| 全链路可观测性 | 每条消息的决策链路可视化（调试侧栏），而不是黑盒对话 |
| 产品化思维 | 看板指标设计、数据飞轮机制、安全合规声明 |

---

## 二、产品定位与安全声明

### 2.1 产品定位

**这是一个技术架构演示项目，不是医疗产品。** 对话内容基于演示用的知识库数据生成，不构成医疗建议。这一点必须在产品形态里**强制体现**，而不只是写在 README 里：

- 首次打开应用时，弹出一次性声明弹窗，用户确认"我理解这是技术演示、不作为医疗依据"后才能进入对话；
- 对话界面底部常驻一行小字声明；
- 每条 AI 回复在涉及用药/症状类内容时自然带出"建议线下就医确认"的收尾（沿用原 PRD 的话术设计原则：不生成机械模板，由固定话术池随机选取）。

### 2.2 核心安全边界（继承原 PRD，不可简化）

严禁任何形式的诊断、严禁对病情做推断判断、严禁提供任何个体化治疗方案、严禁一切替代医生诊疗职能的行为。AI 能给的只是通用医学科普信息。

### 2.3 【新增】API Key 处理声明

用户自行填入的 LLM API Key：
- 仅在当次请求中由本地后端转发给用户指定的 API 地址，**不落库、不写日志、不上传任何第三方**；
- 存储位置仅为浏览器本地（前端临时持有，用于逐次请求），关闭浏览器/清缓存即失效；
- 这一机制会在设置面板里明确向用户说明，作为"可信的个人作品"的加分项。

---

## 三、范围边界

### 3.1 本期做什么

- 完整还原原 PRD 的四层路由决策架构（语义识别 / 检索 / 调度 / 生成）
- 新增质检（自检）闭环
- L0/L1 安全拦截机制
- 多轮对话状态管理（topic_turns / ask_round / closing_probe / 关单）
- AI 决策过程可视化调试侧栏
- 简化版运营看板
- Mock 知识库（生活方式科普、用药禁忌、用法说明、科室分诊、检查前注意事项等，覆盖原 PRD 全部 7 个 sub_type）

### 3.2 本期不做 / 简化处理

| 原 PRD 内容 | 本项目处理方式 | 原因 |
|---|---|---|
| 预问诊 Agent（六要素问诊完整实现） | out_of_scope 时仅展示"已为您模拟移交预问诊流程"占位提示 | 不在原 PRD 范围内，是另一个独立系统 |
| 真实医生工作台 | 转人工时展示"已转人工客服"状态 + 保留完整对话上下文 + 展示触发的结构化标签 | demo 不需要双端系统，保留上下文展示本身就是很好的演示点 |
| 语音转文字 | 不做，仅支持文本输入 | 原 PRD 是"复用现有能力"，demo 没有这个现有能力，非架构核心 |
| 真实医学知识库/药物相互作用数据库/科室知识图谱 | 自建 mock 小数据集，明确标注"演示数据，非真实医学数据库" | 真实医学数据库不可得，也不应该由非专业渠道构建后冒充权威数据 |
| 用户账号系统 | 不做，单会话、本地状态 | 非架构核心，avoid over-engineering |

---

## 四、系统整体架构

### 4.1 架构图

```
用户输入
   │
   ▼
┌─────────────────────────┐
│  intent_router 【简化】   │  判断: 健康咨询 / 其他(模拟移交预问诊)
└───────────┬─────────────┘
            │ 命中健康咨询
            ▼
┌─────────────────────────┐
│  safety_guard L0         │  红旗关键词/正则前置拦截 → 命中直接转人工模拟，不过LLM
└───────────┬─────────────┘
            │ 未命中
            ▼
┌─────────────────────────┐
│  semantic_parser          │  LLM调用: route_scope / sub_type / population_status /
│                           │  special_population_flags / extracted_entities
└───────────┬─────────────┘
            │
            ▼
┌─────────────────────────┐
│  safety_guard L1         │  route_scope=clinical_prescription_intent → 转人工
│                           │  population_status=identified_special → 转人工
│                           │  route_scope=out_of_scope_disease_consult → 移交intent_router
└───────────┬─────────────┘
            │ 通过
            ▼
┌─────────────────────────┐
│  retrieval                │  mock知识库检索 → hit_status (hit/partial/miss)
└───────────┬─────────────┘
            │
            ▼
┌─────────────────────────┐
│  dispatcher                │  route_decision判定: ANSWER / ASK_ONCE / HANDOFF
│                           │  topic_turns / ask_round 计数与封顶
└───────────┬─────────────┘
            │ ANSWER / ASK_ONCE
            ▼
┌─────────────────────────┐
│  generator                 │  LLM调用: 基于命中条目生成自然语言回复
└───────────┬─────────────┘
            │
            ▼
┌─────────────────────────┐
│  self_check  【新增】      │  合规性/溯源一致性/人群免责尾句/格式 四维校验
│                           │  不通过 → 带反馈重试生成一次 → 仍不通过 → 转人工模拟
└───────────┬─────────────┘
            │ 通过
            ▼
     返回回复 + closing_probe
            │
            ▼
      前端渲染 + 调试侧栏展示完整决策链路
```

### 4.2 一条消息的数据流转示例

```
用户: "哪些食物富含钾?"
  → intent_router: 健康咨询 ✓
  → safety_guard L0: 未命中红旗词 ✓
  → semantic_parser: {route_scope: in_scope, sub_type: lifestyle_education,
                       population_status: unknown, extracted_entities: {...}}
  → safety_guard L1: 均未命中拦截条件 ✓
  → retrieval: hit_status = hit (命中"富钾食物"条目)
  → dispatcher: route_decision = ANSWER (hit且population_status=unknown按子类型规则直接放行)
  → generator: 基于条目生成自然语言回复
  → self_check: 合规✓ 溯源一致✓ 格式✓ → 通过
  → 返回回复 + closing_probe
```

---

## 五、核心模块详细设计

### 5.1 安全拦截模块 safety_guard

**L0 规则前置拦截**（在调用任何 LLM 之前执行，命中即转人工，不消耗模型调用）

- 红旗关键词库：过敏性休克、呼吸困难、意识不清、大出血、自杀/自伤、精神心理危机等高危表述（含口语化变体）
- 正则规则匹配

**L1 模型后置拦截**（语义识别模块输出后执行）

| 条件 | 处理 |
|---|---|
| route_scope = clinical_prescription_intent | 转人工，不进入检索与生成 |
| population_status = identified_special | 转人工（特殊人群清单：孕期/哺乳期/14岁以下儿童/65岁以上多药联用/肝肾功能异常） |
| route_scope = out_of_scope_disease_consult | 移交 intent_router，打标 `handoff_source=health_consult_agent`，防止循环移交 |

### 5.2 语义识别模块 semantic_parser

这一步只产出结构化标签，**不生成任何面向用户的回复内容**。

输出 schema：

```json
{
  "route_scope": "in_scope | clinical_prescription_intent | out_of_scope_disease_consult",
  "sub_type": "drug_contraindication | drug_usage_factual | drug_efficacy_evaluation | lifestyle_education | department_triage | pre_exam_instructions | health_checkup_explanation | null",
  "population_status": "identified_special | identified_general | unknown",
  "special_population_flags": ["pregnant", "lactating", "child", "renal_impairment", "hepatic_impairment", "elderly_polypharmacy"],
  "extracted_entities": {
    "drug_name_raw": null,
    "drug_name_normalized": null,
    "coreference_resolved_query": null,
    "symptom_or_condition_raw": null,
    "exam_item_raw": null
  }
}
```

sub_type 判断标准、HANDOFF 汇总表等枚举规则**直接沿用原 PRD 第 2.2 / 2.3 / 附录 7.1 节**，不做改动（这部分原设计是扎实的）。

> **【设计补强】** 原 PRD 对这一步只校验"JSON 格式是否合法"（parse_error），不校验"分类是否正确"。这正是质检模块要接住的缺口之一——质检不仅检查最终自然语言回复，也会在 5.6 节中对高风险 sub_type（尤其是 drug_efficacy_evaluation 这类"伪健康咨询"）做二次确认。

### 5.3 检索模块 retrieval 【简化】

- 原 PRD：对接真实"标准问答库/知识库"+"药物相互作用数据库"+"症状-科室知识图谱"
- 本项目：自建 mock 知识库（JSON/SQLite 存储），按 sub_type 分类存放条目，每条目包含：`问题主题`、`标准答案要点`、`慎用人群`、`风险提示`、`来源标注(演示数据)`
- 检索方式：关键词/语义相似度匹配（可选用轻量 embedding，不需要真实向量数据库），产出 `hit_status`:
  - `hit`：≥阈值且唯一最优
  - `partial`：同类但非最佳匹配
  - `miss`：未命中

### 5.4 调度模块 dispatcher

**route_decision 分层判断**（沿用原 PRD Step2 逻辑）：

| route_decision | 判定逻辑 |
|---|---|
| ANSWER | hit_status=hit AND population_status≠unknown（或按子类型规则豁免，见下） |
| ASK_ONCE | 需要事实性追问（药名/人群身份等），追问后可给出安全通用结论 |
| HANDOFF | 表面像科普实际涉及疗效评价/自行停药调药，或命中 partial/miss |

**population_status=unknown 时按子类型差异化处理**（原 PRD 2.4节核心规则，容易被忽略，本项目显式实现）：

- 生活方式科普/科室分诊/检查前注意事项/体检指导 → 按 identified_general 处理，直接 ANSWER
- 用药禁忌/用法说明 → 必须先做一次人群确认，合并进 ASK_ONCE（与药名确认写在同一条消息内）

**多轮计数与关单**：

- `topic_turns`：当前话题下患者发起的消息数，>2 转人工
- `ask_round`：AI 事实性追问轮次，≥2 禁止继续追问
- `closing_probe`：ANSWER/ASK_ONCE 完成后触发固定话术池收尾语，四类出口（明确否定→关单 / 描述新症状→模拟移交预问诊 / 提新问题→回到语义识别重新分类 / 无响应→超时自动关单）

### 5.5 生成模块 generator

**内容锚定机制**（原 PRD 核心约束）：不让 LLM 脱离知识库条目自由发挥，而是先命中条目，再由 LLM 基于条目内容生成自然语言回复。

生成 Prompt 设计要点（详见第七节）：
- 禁止跳过命中条目直接生成
- 用药类条目固定附加人群限定尾句
- 兜底话术（"具体情况因人而异，必要时线下问诊"）允许生成，但具体医学结论（如"有肾病要限钾"）必须来自条目原文，禁止编造

### 5.6 【新增】质检模块 self_check

这是本项目相对原 PRD **唯一在架构上新增的模块**，插入位置：生成回复之后、closing_probe 拼接之前。

**校验维度**：

| 维度 | 校验内容 | 典型失败案例 |
|---|---|---|
| 合规性 | 是否出现确定性诊断结论、具体剂量调整建议、"建议您停药/加量"等个体化决策用语 | "您这个情况应该是XX病" |
| 溯源一致性（核心） | 生成内容中的医学结论是否都能在命中的知识库条目范围内找到支撑 | 条目只提到"含钾高"，回复里却编了一个具体数值 |
| 人群免责尾句完整性 | 用药类回答（drug_contraindication / drug_usage_factual）是否携带了人群限定尾句 | 用药回答里漏掉了"如果是孕期/哺乳期...建议单独跟医生确认" |
| 格式 | 字数是否超限（250-300字）、是否误把 closing_probe 内容混入正文 | 回复里自己加了"还有其他问题吗" |

**失败处理策略**（已与你确认）：

1. 质检不通过 → 把具体违规点作为反馈，重新调用生成模块生成一次
2. 重试后仍不通过 → 转人工模拟，标记 `handoff_reason = self_check_failed`

**实现方式**：规则校验（格式、尾句关键词匹配）+ LLM 校验（溯源一致性、合规性语义判断）结合，避免纯规则校验不出语义层面的违规，也避免纯 LLM 校验拖慢响应、成本过高。

---

## 六、对话状态机

```
[关单] ←─────────────────────────────────────┐
  ▲                                           │
  │ 明确否定/无响应超时                          │
  │                                           │
[closing_probe] ──提新问题──→ [回到语义识别重新分类]  │
  ▲                                           │
  │ ANSWER/ASK_ONCE完成                        │
  │                                           │
[生成回复] ──质检不通过(重试1次仍失败)──────────→ [转人工模拟]
  ▲                                                ▲
  │ 质检通过                                        │
  │                                                │ HANDOFF / L0命中 / L1命中 /
[ASK_ONCE追问] ──ask_round≥2仍未解决───────────────┤ topic_turns>2 / 异议 /
  │                                                │ hit_status=partial/miss
  │ 拿到回复重新判断                                  │
  └──命中库──→ [生成回复]                            │
                                                    │
[语义识别] ──route_scope=clinical_prescription_intent┘
  │        或 population_status=identified_special
  │ 通过L0/L1
  ▼
[检索] → hit_status
```

关键状态变量：`topic_turns`（话题切换时归零）、`ask_round`（话题切换时归零）、`handoff_source`（防止 out_of_scope 循环移交）。

---

## 七、Prompt 设计

### 7.1 语义识别 Prompt

调用时机：L0 拦截通过后，检索之前。只产出结构化标签，不生成面向用户的内容。核心任务拆解（沿用原 PRD 附录"任务0-3"设计，完整枚举值与判断依据见原 PRD 第七章）：

- 任务0：route_scope 承接范围判断
- 任务1：sub_type 子类型判断（7选1或null）
- 任务2.1/2.2：特殊人群识别 + 人群状态判定
- 任务3：实体抽取与归一化（药品实体归一化、指代消解）

### 7.2 生成 Prompt

按 route_decision 分 ANSWER / ASK_ONCE 两套模板：

- ANSWER：注入 `{subtype_label}` `{answer_body}`（命中条目内容）`{caution_population}` `{risk_warning}` `{population_disclaimer}`，要求语气像医生随口解答、口语化、250-300字以内、不使用机械免责模板
- ASK_ONCE：注入 `{ask_round}` `{missing_fact_type}`，要求只问缩小范围的事实性问题、不包含任何结论判断、单条消息60字以内、一次只问一个话题（身份确认可与药名确认合并）

### 7.3 【新增】质检 Prompt

```
你是健康咨询回复的质检员，负责在回复发送给患者之前做最后一道把关。

【输入】
- 命中的知识库条目原文：{retrieved_entry}
- 待审核的AI生成回复：{generated_reply}
- 本轮 sub_type：{sub_type}

【审核维度，逐项给出 true/false 和理由】
1. compliance_pass：回复中是否存在确定性诊断结论、具体剂量调整、"建议停药/加量"等个体化诊疗决策表述？(不存在=true)
2. grounding_pass：回复中的每一条医学结论，是否都能在"命中的知识库条目原文"中找到依据？(全部可溯源=true)
3. disclaimer_pass：若 sub_type 属于用药类(drug_contraindication/drug_usage_factual)，回复是否携带了人群限定尾句？(非用药类此项默认true)
4. format_pass：回复字数是否在300字以内，且没有混入"还有其他问题吗"一类的收尾话术？(符合=true)

【输出】严格JSON:
{
  "compliance_pass": bool, "grounding_pass": bool,
  "disclaimer_pass": bool, "format_pass": bool,
  "overall_pass": bool,   // 四项全部true才为true
  "violations": ["具体违规点描述，用于反馈给生成模块重试"]
}
```

---

## 八、前端设计

### 8.1 对话主界面
类聊天应用的消息流，AI 消息下方附带状态标签（ANSWER / ASK_ONCE / 已转人工）。

### 8.2 【新增】AI 决策过程调试侧栏
每条 AI 消息可展开查看完整决策链路，这是把"黑盒对话"变成"可讲解的架构"的关键演示点：

```
route_scope: in_scope
sub_type: lifestyle_education
population_status: unknown
hit_status: hit
route_decision: ANSWER
self_check: compliance✓ grounding✓ disclaimer✓ format✓ → 通过
```

### 8.3 设置面板
API Key / Base URL / Model 配置，本地存储说明，首次使用免责声明弹窗。

### 8.4 【新增】简化版运营看板

独立页面，基于本地会话日志统计（沿用原 PRD 第六节指标设计，缩减到核心几项）：

- 健康咨询问诊单量
- ANSWER / ASK_ONCE / HANDOFF 占比
- hit_status 分布
- topic_turns > 2 占比（反映知识库覆盖深度不足的信号）
- **质检拦截率**（self_check 不通过后重试/转人工的比例）—— 这是原 PRD 没有、本项目新增指标，用于体现质检模块本身的工作量

---

## 九、技术栈与工程结构

- 后端：Python + FastAPI，模块目录与第四节架构图一一对应
- 前端：React + Vite，构建产物由 FastAPI 直接 serve
- 启动方式：本地一条命令启动（`uvicorn main:app` 或打包脚本），浏览器打开 `localhost` 即可使用

```
health-consult-agent/
├── backend/
│   ├── intent_router/
│   ├── safety_guard/
│   ├── semantic_parser/
│   ├── retrieval/
│   ├── dispatcher/
│   ├── generator/
│   ├── self_check/
│   ├── session_state/
│   ├── knowledge_base/        # mock数据
│   └── main.py                 # FastAPI入口 + 静态文件托管
├── frontend/
│   ├── src/
│   │   ├── components/ChatPanel/
│   │   ├── components/DebugSidebar/
│   │   ├── components/SettingsPanel/
│   │   └── pages/Dashboard/
└── docs/
```

---

## 十、知识库内容来源说明

Mock 知识库覆盖原 PRD 全部 7 个 sub_type，每类预计构造 8-15 条示例问答，内容来自公开医学科普资料整理改写，**仅用于架构演示，不作为医疗依据**，每条数据附来源标注。知识库 schema 设计见 5.3 节。

---

## 十一、后续可迭代方向（Not in scope，体现设计完整性）

- 对接真实预问诊 Agent，实现 out_of_scope 的完整移交闭环
- 语音输入（复用成熟 ASR 能力）
- 知识库内容的人工复核与数据飞轮闭环（原 PRD 6.2 节设计，demo 阶段数据量不足以支撑）
- 多语言支持
