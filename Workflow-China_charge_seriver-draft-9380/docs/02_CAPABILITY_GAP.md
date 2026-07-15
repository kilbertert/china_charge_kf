# 能力缺口对照 — 当前 `China_charge_seriver.yml` vs 架构图

> 用途: 量化重构工作量,作为 SPEC 拆解的输入。每行缺口对应至少一个施工任务。

---

## 1. 现状摘要

当前 `China_charge_seriver.yml` 的实际能力:
- 节点: **13 个**(start / if-else / 3 路 KR / 3 路 LLM / http-request / code / variable-aggregator / end)
- 分流维度: 仅按 **输入模态**(image / audio / text)三路
- 数据源: 单一 `dataset_id = cJ687vaaJbsFc7MghKK/6gS+0+mJHna8xcsp3EgZpz4FTn6Z2PZ8MtU8c36SDHxB`
- LLM: 3 个 LLM 节点共用同一 system prompt(多模态细节有差异)
- End 输出: 单字符串(`output`)
- 多轮: **不支持**(无 session_id / turn_id)

实际只实现了架构图里的"输入模态三路",**完全没有场景分类和第二轮的细化路由**。

---

## 2. 缺口对照表

| # | 架构图要求 | 当前实现 | 缺口类型 | 影响范围 |
|---|------------|----------|----------|----------|
| G1 | 场景分类(scene classifier,区分路径 A/B/C) | ❌ 无 | **结构性缺口** | 工作流入口 |
| G2 | 多轮对话(turn 1 / turn 2,回流到后台) | ❌ 无 | **结构性缺口** | start + conversation_variables |
| G3 | 流程1 — 功能匹配预检(独立 dataset + 独立 KR) | ❌ 混在单库检索中 | **数据/检索缺口** | 后台三流 |
| G4 | 流程2 — 清单准确性校验(版本/时效标签) | ❌ 无 | **数据缺口** | 后台三流 |
| G5 | 流程3 — 报价查询(独立 KB + 报价节点) | ❌ 无 | **数据/节点缺口** | 后台三流 |
| G6 | 路径 A 业务流(功能查询/检查,独立 LLM) | ⚠️ 共享 LLM 节点 | **逻辑缺口** | 场景A |
| G7 | 路径 B 业务流(业务/规则诊断 + 危险信号硬判定) | ⚠️ 文字描述无硬判定 | **逻辑缺口** | 场景B |
| G8 | 路径 C 业务流(移动设备操作指导 + 步骤化) | ❌ 无 | **结构性缺口** | 场景C |
| G9 | End 节点输出统一 SceneResponse JSON | ❌ 仅单字符串 | **契约缺口** | End 节点 + 后端解析 |
| G10 | 危险信号硬闸门(code 节点,确定性) | ❌ 仅 LLM prompt 文字 | **安全缺口** | 场景B |
| G11 | 多渠道/多语言路由层 | ⚠️ `language` 仅用于 LLM 提示词 | **逻辑缺口** | 多渠道共用 |
| G12 | 跨文档检索(multi-dataset,product + spec + policy) | ❌ 单 dataset_id | **检索缺口** | 全局 |
| G13 | 知识库可插拔(新增功能不需改流程1) | ❌ 强耦合 | **扩展性缺口** | 流程1 |
| G14 | session_id / turn_id 输入与状态追踪 | ❌ 无 | **结构性缺口** | start + 全局 |
| G15 | 工单/人工分流兜底(场景B 失败时) | ❌ 仅"建议联系售后"文本 | **兜底缺口** | 场景B |

---

## 3. 缺口按重构影响面分级

### 3.1 P0 — 阻塞新架构主流程(必须先解决)
- G1 场景分类节点 → 没有它,整张架构图无法落地
- G9 End 输出契约 → 后端解析依赖它,直接决定能否对接前端
- G2 多轮 → 架构图右侧回环注释明确要求
- G10 危险信号硬闸门 → 涉及合规,不能仅靠 LLM 自由发挥

### 3.2 P1 — 业务场景必备
- G3 / G4 / G5 三个流程1/2/3 独立 KR(可串行实现)
- G6 / G7 / G8 三条路径 A/B/C 业务 LLM

### 3.3 P2 — 体验/扩展性
- G11 多语言路由层
- G12 跨文档检索(可能复用现有 dataset + 新增)
- G13 知识库可插拔(架构性需求,但 MVP 可先 hardcode)
- G14 session_id / turn_id(可放到 P1 一起做)
- G15 工单/人工兜底(独立任务,涉及外部系统)

---

## 4. 与健康咨询 v2 的复用度评估

`AI_health_consultant_v2.yml` 已实现的相似能力(可借鉴/复用):

| 健康咨询 v2 的能力 | 充电桩可借鉴点 | 复用度 |
|-------------------|----------------|--------|
| scene_classifier (code 节点,确定性 if-elif) | G1 场景分类器(但充电桩场景更复杂,可能需要 LLM 辅助) | **70%**(逻辑可复用,规则需重写) |
| scene1/2/3 if-else 路由 | G6/G7/G8 三路径路由 | **85%**(基本可套) |
| scene2_code_危险信号判定 | G10 危险信号硬闸门 | **60%**(关键词完全不同,但模式可抄) |
| End 输出 SceneResponse JSON | G9 输出契约 | **95%**(可直接复用 schema 模式) |
| node ID 4001-4099 范围 | 新工作流 node ID 5001-5099 | **100%**(避让规则) |
| conversation_variables | G14 session 状态 | **待确认**(健康咨询 v2 也没用 conversation_variables,可能本身就不需要 Dify 这层,而是后端 Redis) |

### 4.1 不能直接复用的部分
- 健康咨询 v2 的 **scene_classifier 是纯 code 节点**(关键词 + JSON 字符串),充电桩场景的关键词更模糊,可能要 LLM 辅助
- 健康咨询 v2 没有 **流程1/2/3 并行预检** 的概念,这是充电桩特有的
- 健康咨询 v2 的 scene3(产品问答)是 RAG 兜底,充电桩的 **路径 A/B/C** 都需要更复杂的业务逻辑

---

## 5. 数据源缺口细化

当前唯一 dataset_id `cJ687...` 在重构后需要拆分为:

| 新 dataset_id 占位 | 用途 | 数据源 | 优先级 |
|--------------------|------|--------|--------|
| `<DATASET_PRODUCT_SPEC>` | 流程1 — 功能匹配预检 | 产品功能矩阵文档 | P1 |
| `<DATASET_PRODUCT_CHANGELOG>` | 流程2 — 清单校验(版本/时效) | 版本变更日志 | P1 |
| `<DATASET_PRICING>` | 流程3 — 报价查询 | 报价表(产品 × 区域 × 时段) | P1 |
| `<DATASET_FAULT_DIAGNOSIS>` | 路径 B — 故障诊断 | 故障码手册 + 排查流程 | P1 |
| `<DATASET_OPERATION_GUIDE>` | 路径 C — 移动设备操作步骤 | App/H5/小程序操作手册(多语言) | P1 |
| 现有 `cJ687...` | 兜底通用知识 | 现有充电桩售后文档 | P2(保留兜底) |

> 注意: 借鉴 `DEPLOY_INSTRUCTIONS.md` 的占位符替换模式,新 yml 用 `<DATASET_*>` 占位,部署时 sed 替换。

---

## 6. 后端协同缺口

`backend/health_consult/scene_router.py` 已实现健康咨询的场景路由,充电桩也需要对应的 `scene_router`,且:

- 需要新增 `CHARGING_SCENE_HANDLERS = {scene_charge: handler, scene_fault: handler, ...}`
- 需要新增 `ChargeSceneResponse` schema(对齐 SceneResponse)
- 健康咨询的 `responses_to_unified()` 可复用做 envelope 包装
- H5 前端的 `useSceneChat` hook 可复用,但 scene 枚举要扩展

具体后端任务见后续 SPEC。

---

## 7. 验收标准(用于后续 SPEC 拆解)

每条 SPEC 完工时,必须能回答:

- [ ] 对应的 P0/P1/P2 缺口是否已关闭
- [ ] 是否影响其他 SPEC 的依赖项
- [ ] 是否有对应的 dataset_id 占位替换
- [ ] 是否有冒烟测试用例(覆盖该 SPEC 对应的场景)

---

## 8. 实际知识库结构(深挖后修正,2026-06-18)

> 来源: `32-6.17(充电桩知识库)/` 目录下 7 份原始资料的解析结果。

### 8.1 资料清单与归属

| 资料文件 | 类型 | 内容定位 | 行/段数 | 对应 SPEC |
|----------|------|----------|---------|-----------|
| `趋势云-标准充电桩功能清单V2.4.1-调整家充功能清单.xlsx` | xlsx/9 sheet | **产品功能矩阵**,含版本历史 | 9 sheet × ~50-200 行 | C1, C2 |
| `常见问题解答.xlsx` | xlsx/单 sheet | **FAQ**(英文) | 49 条,21 个功能节点分组 | F1(FAQ) |
| `Standard Operating Manual for Charging Piles.docx` | docx | **三端综合操作手册**(英文原版 V1.00) | 190 段 | D3 |
| `《标准版充电桩操作手册》--英语版本_1_56_translate_20260610174131.docx` | docx | 同上手册的中译英版 | 194 段 | D3 |
| `sys_menu_整理后.xlsx` | xlsx | **后台管理菜单层级**(PC 后台) | 1077 行 / 14 列 | F1(菜单) |
| `data_processed.csv` | csv | **i18n 翻译**(sys_menu 对应) | 28995 行 | D3 |
| `架构框架.png` | png | 业务架构图 | — | 01 文档 |

### 8.2 修正点 — 功能清单的真正结构

**不是** 简单的"功能名 | 适用型号 | 是否实现 | 描述"。实际结构是 **4 级分类 + 端类型 + 版本号**:

```
[顶级菜单/版本]  → [板块] → [模块] → [功能点] → [功能说明] + [备注]
```

**功能清单 xlsx 的 9 个 sheet**:

| Sheet 名 | 内容 | 端 |
|----------|------|-----|
| 版本记录 | V2.0→V2.4.1 更新日志 | 全局 |
| 国内充电用户端 | C 端国内版功能 | 用户端 |
| 国内运营管家端 | 运营商功能 | 管家端 |
| 国内PC端后台 | 平台管理后台 | PC 后台 |
| 海外充电用户端 | C 端海外版(独有第三方登录) | 用户端 |
| 海外运营管家端 | 运营商功能 | 管家端 |
| 海外PC端后台 | 平台管理后台 | PC 后台 |
| **家充-用户端**(V2.4 新增) | 家充场景用户端 | 用户端 |
| **家充-PC管理后台**(V2.4 新增) | 家充场景管理后台 | PC 后台 |

**结论 — SPEC-C1/C2 修订**:
- 数据集不再是 1 个,而是**至少 2 个**:
  - `<DATASET_PRODUCT_SPEC>`: 8 个 sheet 的功能点全集(用户端 + 管家端 + PC 后台)
  - `<DATASET_PRODUCT_CHANGELOG>`: `版本记录` sheet 的版本变更日志
- 每条功能点记录字段:`板块 | 模块 | 功能点 | 功能说明 | 备注 | 端类型(用户/管家/PC) | 版本(V2.x)`
- **新增"家充场景"维度**: 用户在 user-input 中提到"家充 / 家用 / 私人桩",scene_classifier 要能识别并切到"家充知识子集"
- **国内/海外差异**: 海外版独有"谷歌/脸书第三方登录"(faq_node=`Sign up`),国内独有"小程序授权登录"—— FAQ 命中时也要按地域过滤

### 8.3 修正点 — FAQ 的真实字段与节点分组

`常见问题解答.xlsx` 实际只有 3 列(`功能节点 | 常见疑问 | 回答`),**49 条** 按 **21 个功能节点** 分组:

```
Role Management / Shop Level / Individual operator / Operator review for entry
/ Add sites under the operator / Site audit / Billing Template(6)
/ Charging Order / Charging coupons(2) / Create venue / Data View
/ Data sector / Equipment Failure List / Financial Management(2)
/ Operations Management / Order Management(2) / Placement equipment(3)
/ Real name authentication / Sign up(2) / Venue / Venue association template
/ equipment(5) / place an order(2) / top-up
```

**结论 — SPEC-F1 FAQ 子表修订**:
- 数据集字段:**`功能节点 | 常见疑问(中文关键词) | 常见疑问(英文原句) | 回答(英文) | 适用端 | 适用地域(国内/海外)`**
- 49 条 → 实际是英文版 FAQ,中文用户查询时需要反向命中(关键词中英都覆盖)
- `equipment` 节点下"设备离线的标准排查步骤"是**故障类**,应纳入路径B;`Billing Template` 下都是计费类,应纳入路径A
- FAQ 节点与操作手册章节是**对齐的** — 操作手册 35 个一级标题里有 19 个直接对应 FAQ 节点(`Role Management / Sign up / Site audit / Charging coupons / Billing Template / Financial Management / Order Management / Operations Management / Placement equipment / Equipment Failure List / Data View / Add sites under the operator / Create venue / Data sector / Venue association template / Venue / place an order / top-up / Real name authentication`)。意味着 FAQ 和操作手册可**双向引用**

### 8.4 修正点 — 操作手册的真实边界

英文原版 V1.00(2025-7-25,190 段)和中译英版(1.56,194 段)实际是**三端综合操作手册**,不是单一用户文档:

| 端 | 一级章节(粗体 = 出现顺序) |
|----|---------------------------|
| **PC 管理后台** | Role Management / Shop Level / Individual operator / Operator review for entry / Add sites under the operator / Site audit / Billing Template (Charging Station) / Add product model / equipment / Placement equipment / Charging coupons / Equipment Failure List / User Management / Financial Management / Order Management / Operations Management / Data View |
| **用户端(C 端)** | Sign up / top-up / place an order / Four wheel charging order / Placeholder fee order / venue / license plate / Change password / Fault Repair |
| **管家端(B 端)** | Sign up / Real name authentication / Create venue / my venue / Create template / Venue association template / Placement equipment / data sector / order / Venue details / Profit withdrawal |

**关键发现**:
- 手册含**路由链接字符串**(如 `/charge/pages/placeUseFeeList/placeUseFeeList`、`/charge/pages/malfunction/malfunction`)→ 路径C 输出步骤时**保留跳转链接**,用户体验更好
- 三端都有 `Sign up`(注册章节),但内容完全不同(用户注册 vs 运营商注册),需要在文档层面按端切片

**结论 — SPEC-D3 / SPEC-F1 操作手册子表修订**:
- 数据集字段:**`端(PC后台/用户端/管家端) | 章节(35个一级标题) | 步骤列表 | 跳转链接 | 适用语言(zh/en/vi)`**
- 手册每段是一行,**粒度到段**(190/194 行,不是按章节 35 行)
- KR 检索时 query_variable_selector 用 **input_text**,但 metadata filter 必须加 **端类型 + 语言**
- 路径C 输出步骤保留**跳转链接**字段(直接展示给小程序的 webview 跳转)

### 8.5 修正点 — sys_menu 与 i18n csv 的关系

| 项 | sys_menu.xlsx | data_processed.csv |
|----|---------------|---------------------|
| 行数 | 1077 | 28995 |
| 列 | 14(层级路径/顶级ID/子菜单ID/...) | 8(菜单名/菜单id/component/字段key/CN/EN/层级路径/顶级菜单) |
| 关系 | 元数据(层级) | i18n 实例(每字段中英) |
| 顶级菜单 | 9 个:平台/系统/基础信息/设置中心/角色管理/管理员设置/操作日志... | 12 个:应用(6361)/运营(5666)/?(4732)/财务(3637)/商城(2894)/**充电桩(2310)**/系统(1477)/健康(1186)/IOT(676)/平台(52) |
| 是否 C 端 | ❌ 全是后台管理 | ❌ 全是后台管理 |

**结论**:
- sys_menu / data_processed.csv 实际是**后台管理的 i18n 词典**,**不是 C 端用户文档**
- **充电桩 顶级菜单** 只有 2310 条翻译字段,意味着后台的"充电桩"模块有 2310 个需要翻译的 UI 字符串
- 路径C 输出语言切换时,这些 i18n 字符串可作为**前端 i18n fallback**(后端 CMS 没翻译时用此 csv)
- 这两份资料不直接进 Dify 知识库,而是放在**前端 i18n 文件**和后端 CMS

### 8.6 新增设计约束(由实际资料推导)

1. **场景分类(scene_classifier)必须支持 4 维**:
   - 业务意图(4 路径):功能/业务规则/操作/报价
   - 端类型(3 端):用户端/管家端/PC 后台
   - 地域(2 域):国内/海外
   - 桩型(2 类):公共桩/家充(V2.4 新增)
2. **FAQ 与操作手册必须双向引用**: 同一个功能节点(如 `Billing Template`)在 FAQ 和手册都有,FAQ 给"是什么 + 为什么",手册给"怎么做"
3. **新增"家充"专属知识子集**: V2.4 后才有家充功能,FAQ/操作手册/功能清单都要标 `is_home_charge=true/false`
4. **海外版独有特征**: 第三方登录(谷歌/脸书)、邮箱注册、英文 FAQ —— 这些是国内版没有的,知识库要按地域切分
5. **"端"必须在 scene_classifier 输出中体现**,否则路径C 操作手册无法定位

---

## 9. 对 SPEC 的具体修订(传递到 03_REFACTOR_SPEC.md)

下表的修订项已同步到 `03_REFACTOR_SPEC.md`:

| 修订项 | 原 SPEC | 新版 |
|--------|---------|------|
| `<DATASET_PRODUCT_SPEC>` 字段 | `功能名 \| 适用型号 \| 是否实现 \| 描述` | `板块 \| 模块 \| 功能点 \| 功能说明 \| 备注 \| 端类型 \| 版本 \| 是否家充 \| 地域` |
| `<DATASET_PRODUCT_CHANGELOG>` 来源 | 未明确 | 直接用 `版本记录` sheet 解析 |
| `<DATASET_OPERATION_GUIDE>` 章节粒度 | "设备 \| 操作名 \| 语言" | "端 \| 章节(35个) \| 段落 \| 跳转链接 \| 语言" |
| `<DATASET_FAQ>` 节点对齐 | "问题 \| 关键词 \| 答案 \| 语言" | "功能节点(21个) \| 常见疑问(中英) \| 回答(英文) \| 端 \| 地域 \| 是否家充" |
| SPEC-B1 scene_classifier 维度 | 4 路径 | 4 路径 × 3 端 × 2 地域 × 2 桩型 |
| SPEC-D3 多语言 | zh/en/vi | zh/en/vi(不变),并按"端"过滤 |
| SPEC-D2 故障判定 | 关键词硬判定 | 关键词 + 端类型(用户端报障 / 管家端报障 关键词不同) |
| 新增 `<DATASET_I18N_FALLBACK>` | 无 | data_processed.csv 抽取充电桩 2310 条作为前端 i18n fallback |