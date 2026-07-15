# v20 缺口改造任务文档

> 用途:基于 `06-customer-feedback-flow.md` 新架构文档对照 v20 实现梳理出的 6 个缺口。compact 后按此文档逐项改造。
> 基线:`charge_charging_v20.yml`(87 节点/115 边,已上线生产)+ `patch_v20.py`。
> 改造模式:沿用 patch 脚本(ruamel.yaml),基于 v20 生成 v21,用户手动导入测试 app 验证后发布生产。

> **进度(2026/07/06)**:✅ Gap1(v21) ✅ Gap3(v22) ✅ Gap5(v23) ✅ Gap2(v24) ✅ Gap6(v24) 已完成测试 app 验证;⬜ Gap4(超时清态,跨 wecom+dify 最复杂)未做。详见 memory `batch2-5-gap135-fixes.md` / `batch2-6-gap26-fixes.md`。当前最新版本 v24(95节点/130边)。

---

## 0. 执行环境(compact 后必读)

### 三机拓扑
- **开发机**:`/home/ranlei/china_charge_kf/Workflow-China_charge_seriver-draft-9380/workflow/`(当前目录)
- **120 后端生产**:`ssh -p 2134 root@120.55.45.59`,密码 `0eIGe#$3hVp15EPFH#3WBvW8X2`。飞书查表/写表内部 API:`http://localhost:2134/internal/bugtrack/*`,Bearer `rTlcyp8ezVWupzXmGrfPh-l_BQxEQaEqCHCtJbyxs6E`
- **124 Dify 生产**:`ssh root@124.243.178.156`,密码 `Xbjiejiaqsy@2026`。Dify chat API:`http://124.243.178.156:8501/v1`(开发机可直达)
- **wecom 后端**:`/home/ranlei/wecom-ai-customer-service/`,Celery timer `bugtrack_timeout`(countdown=1800)在 `app/tasks/bugtrack_tasks.py`

### Dify app
- 测试 app:token `app-JnlcvQvqVLRgClM42lK5OqjP`(id 3a4a5e88)
- 生产 app:token `app-i4HdI91FDEKPtOiautltOqGJ`(id ffaa8cf0)

### patch 脚本模式
- 复用 `patch_v20.py` 的 helpers:`find_node/pos/llm/code/assigner/ifelse/edge/out_str/out_num`
- `assigner 不支持 constant`,字符串/数字常量经 6901 code 节点输出引用(见 [[dify-chatflow-batch1-practice]])
- dify code 节点**不能可靠获取当前时间**,超时逻辑用 cv 标志位 + LLM 语义,不用硬时间窗(见 [[batch2-3-modify-window]])
- 生成后必校验:节点id唯一/边端点存在/if-else 每个 case 有出边/无孤立节点(除 6901 常量+6099 终点)

### v20 关键节点速查
| 节点 | id | 作用 |
|---|---|---|
| code_准备本轮输入 | 6002 | 产出 query_text |
| 是否二阶段待确认态 | 6601 | cv_flow_state 状态机分发(IDLE/await_*) |
| code_常量 | 6901 | str_*/clarify_count_* 常量(无出边,靠引用) |
| L3 意图识别4路分发 | 6201 | →D路径 6250 |
| N5 转写+关键词 | 6250 | 首次提取(总是输出JSON+充足度标签) |
| N5充足度判定 | 6250-judge | 输出 label+四字段 |
| N5充足度分支 | 6250-if | sufficient→6243 / insufficient→6250-insuf |
| N5不足设态 | 6250-insuf | 设 await_confirm_new+存原始反馈+count=1 |
| N5引导话术直出 | 6250-insuf-out | 过滤标签+拼TIMER→6098 |
| D2组装查表body | 6240build | mokuai 来自 6250-judge |
| D2查询问题追踪表 | 6240 | HTTP 查飞书 |
| D2解析查表 | 6240-parse | 输出 hit_record_id+row_summary |
| D2是否已存在 | 6241 | bug_exist→6242 / default→6250-if |
| **D4 汇报问题进度** | **6242** | **命中汇报(LLM,差距1)** →6242b→6242c→6098 |
| var_标记bug已记录 | 6243 | 设cv四字段+await_confirm_new+count=0 |
| N6引导确认新增 | 6244 | LLM 生成确认话术 →6244-timer→6098 |
| N17相关性识别 | 6170 | await_confirm_new 态判定 CONFIRM/MODIFY_NEW/IRRELEVANT |
| N17分发 | 6171 | CONFIRM→6260a / MODIFY→6172 / default→6162 |
| 合并历史反馈+补充 | 6172 | cv_feedback_zh+query_text→merged |
| N5b转写(合并补充) | 6250b | 迭代场景提取 →6250b-judge |
| N5b充足度判定+兜底 | 6250b-judge | label+next_count,count>=2不足→FALLBACK |
| N5b充足度分支 | 6250b-if | sufficient/fallback→6250b-parse / insufficient→6250b-insuf |
| N5b解析JSON | 6250b-parse | 含 FALLBACK 返回待确认 |
| N17b身份确认分类 | 6170b | await_confirm_identity 态 CONFIRM_IDENTITY/DENY/MODIFY_EXISTING/IRRELEVANT |
| N17b分发 | 6171b | CONFIRM→6173 / DENY→6177 / default→6162 |
| **N5c否认命中转新增** | **6177** | **LLM转写→6177-parse→6177-assigner→6244(差距2)** |
| N9对比+N11询问修改 | 6173 | 命中确认后对比→await_diff_decision |
| N17c修改决策分类 | 6170c | CONFIRM_MODIFY/MODIFY_EXISTING/default(差距6无NO_DIFF) |
| N12汇报修改 | 6175 | LLM 汇报修改→await_confirm_modify |
| N17d修改完成确认分类 | 6170d | await_confirm_modify 态 |
| N14组装update fields | 6176a→6176b→6176c | update body |
| N14写主表update | 6176c | HTTP update 飞书 |
| **N14汇报+cancel** | **6176d** | code 拼 answer_text+cancel(差距3缺表链接) |
| N16写主表 | 6260a→6260b→6260c | add 飞书 |
| var_设IDLE+record_id | 6261 | 写表后设 modify_window+record_id+cv_row_summary |
| **N16汇报已记录** | **6262** | **LLM 含记录编号(差距3缺表链接)** →6262b→6098 |
| 修改窗意图判断 | 6239-llm | await_modify_window 态 MODIFY/NEW/OTHER |
| 修改窗分发 | 6239-if | MODIFY→6239-trans / NEW/OTHER→6239-new-idle |
| 修改窗转写 | 6239-trans | →6239-trans-parse→6239-modify-assigner→6173 |
| 修改窗回IDLE | 6239-new-idle | →6003 |
| var_reset(IDLE) | 6162 | IRRELEVANT 回 IDLE(差距5无结束话术) |
| 汇聚最终答案 | 6098 | variable-aggregator,汇聚各路径 answer_text |
| 输出AI回答 | 6099 | 终点 |

### cv_flow_state 六态
IDLE / await_confirm_new / await_confirm_identity / await_diff_decision / await_confirm_modify / await_modify_window

---

## 1. 缺口清单(按优先级)

### 【P0】差距1:D4 命中汇报模板化(去 LLM)
**现状**:6242 D4 是 LLM(prompt="汇报该记录内容,并引导用户确认"),每次命中都调 Doubao。
**文档要求**:5.1 双分支 LLM 策略——命中 bug 表"预设模板传达即可,不需要大模型"。
**改造方案**:
1. 6242 从 `type: llm` 改为 `type: code`,模板拼接:
   ```python
   def main(row_summary: str) -> dict:
       s = (row_summary or "该记录内容").strip()
       return {"answer_text": f"我们查询到已有相关追踪记录：\n{s}\n\n请问这是您反馈的问题吗？"}
   ```
   - variables: row_summary ← [6240-parse, row_summary]
   - outputs: answer_text(string)
2. 下游 6242b 当前读 `[6242, text]`,改为读 `[6242, answer_text]`(因为 code 输出 answer_text 不是 text)
3. 确认 6242→6242b→6242c→6098 链:6242b 是拼 TIMER 的 code,6242c 可能是设 await_confirm_identity 态的 assigner。改造时读 6242b/6242c 确认字段引用,把 `6242.text` 引用改 `6242.answer_text`
**验证**:命中已有记录(如"有个订单没有支付时间")→输出模板话术(无 LLM 调用延迟),含 row_summary + "这是您反馈的问题吗"

### 【P0】差距4:超时清 cv_flow_state(dify 侧闭环)
**现状**:wecom Celery `bugtrack_timeout` 超时只写飞书缓存表,**不回调 dify、不清 cv_flow_state**。用户超时后再发消息仍残留 await_* 态,可能误走确认/修改分支。
**文档要求**:Timeout 半小时窗口 + Cached"超时未变更不改变数据"。
**改造方案**(跨 wecom+dify,最复杂):
- **wecom 侧**(`app/tasks/bugtrack_tasks.py`):`bugtrack_timeout` 超时后,调用 dify chat API 发一条系统消息(如 query=`【SYS:TIMEOUT_RESET】`),触发 dify 状态机清态。需带 conversation_id(wecom 侧已持有 dify conversation_id 映射)
- **dify 侧**:在 6002(code_准备本轮输入)或 6601 入口加识别——若 query_text 含 `【SYS:TIMEOUT_RESET】` 标记,则:
  - 走专用清态分支:设 cv_flow_state=IDLE + cv_clarify_count=0 + 输出"您的反馈已超时,系统已记录待跟进,如需继续请重新描述问题"
  - 不走正常状态机分发
- 实现要点:在 6601 前加一个 if-else 判定 query_text 是否含 TIMEOUT_RESET 标记,命中→清态 assigner→超时话术 code→6098;否则→6601 正常分发
**注意**:wecom 侧是否能拿到 dify conversation_id 需确认(见 [[wecom-timer-architecture]]);若拿不到,退化为"dify 侧每次入口检查 cv 时间戳"——但 dify code 取不到可靠时间,此路不通。所以必须 wecom 回调
**验证**:发起反馈→设 await_confirm_new→不回复等超时(或 wecom 侧手动触发 timer)→检查 dify cv_flow_state 是否回 IDLE + 客户收到超时话术

### 【P1】差距3:R1/R2 汇报补飞书表链接 URL
**现状**:6262 prompt 含"记录编号: {{#6260c.record_id#}}",6176d 含 cv_record_id,但**都无飞书表链接 URL**。
**文档要求**:写入后"再次发送对话提醒表链接和写入编号、内容"。
**改造方案**:
1. 从 [[feishu-bitable-practice]] 取飞书 bitable 的 app_token + table_id,构造记录链接格式:`https://{domain}.feishu.cn/base/{app_token}/table/{table_id}?record={record_id}`
2. 在 6901 code 常量加 `feishu_base_url`(完整前缀,含 app_token/table_id)
3. **6262b**(N16汇报后的 code):当前 `answer_text = llm_text + cancel标记`,改为:
   ```python
   def main(llm_text, record_id, feishu_base_url):
       url = f"{feishu_base_url}?record={record_id}" if record_id else ""
       link = f"\n📋 记录链接: {url}" if url else ""
       return {"answer_text": (llm_text or "") + link + "\n<!--SYS:TIMER|action=cancel-->"}
   ```
   - 加 variables: record_id ← [6260c, record_id] 或 [conversation, cv_record_id]; feishu_base_url ← [6901, feishu_base_url]
4. **6176d**(N14汇报+cancel):同样加 record_id 链接拼接
**验证**:新反馈确认写入后,汇报含可点击的飞书表链接 + 编号;update 修改后同样含链接

### 【P1】差距2:客户否认 → 重新查表(而非转新增)
**现状**:6170b 判 DENY_IDENTITY → 6177 N5c 转写 → 6177-parse → 6177-assigner → 6244 确认新增(直接当新反馈)。
**文档要求**:Q3 否认 → "携带新线索重新查询"(回 Q1 查表)。
**改造方案**:
1. DENY_IDENTITY 分支改为:6177 N5c 转写(提取新 mokuai)→ 6177-parse → **6240build 重新查表**(而非 6244)
2. 6240build 当前读 `[6250-judge, mokuai]`。DENY 路径要读 `[6177-parse, mokuai]`。两种来源冲突,解法:
   - 方案A:6177-parse → 一个中间 assigner 把 mokuai 写入 cv_mokuai,6240build 改读 cv_mokuai(但 6240build 现读 6250-judge.mokuai,要统一来源)
   - 方案B:新增一个 6240build-denial 节点,读 6177-parse.mokuai 组装查表 body → 6240 → 6240-parse → 6241
3. 推荐**方案B**:6177-assigner 改为不直接→6244,而是→6240build-denial(新 code,读 6177-parse.mokuai)→6240→6240-parse→6241。命中→6242 D4(再次汇报) / 未命中→6250-if(按充足度走新增/引导)
4. 6177-assigner 当前设什么 cv?需读确认。改造时设 cv_flow_state 回 IDLE 或保持查表流程
**验证**:命中记录→否认"不是这个问题,是XXX"→用新线索重新查表→命中另一条或未命中走新增

### 【P2】差距5:Q3 静默/无关 → 结束话术
**现状**:6170b IRRELEVANT → 6162 reset IDLE,无话术。6162 是纯 assigner,不输出话术。
**文档要求**:Q3 静默 → "回复会继续跟进、结束对话"。
**改造方案**:
1. 6171b 的 default(IRRELEVANT)分支当前 → 6162。改为 → 新增 code 节点 `6162-out`(输出结束话术)→ 6162 → 6098
2. 6162-out code:
   ```python
   def main() -> dict:
       return {"answer_text": "好的,您反馈的问题我们会继续跟进处理,有进展会第一时间通知您。若还有其他问题随时联系我~"}
   ```
3. 6162-out → 6162(reset IDLE)→ 6098?但 6162 是 assigner 无 text 输出。改为:6171b default → 6162-out → 6098,6162-out 同时在 answer_text 里不含清态。需 6162-out 后接 6162 清态再... 但 6162 无输出。
   - 解法:6171b default → 6162(reset)→ 6162-out(话术)→ 6098。6162-out 读空,输出固定话术
4. 同理适用于其他 IRRELEVANT 分支(6171 default、6171c default、6171d default)——这些回 IDLE 时都缺结束话术,可统一加
**验证**:命中记录后回"算了"或开新话题 → 收到友好结束话术 + 状态回 IDLE

### 【P2】差距6:Q4 无差异 → 结束话术
**现状**:6170c N17c cases 为 confirm_modify/MODIFY_EXISTING/default,无"无差异(NO_DIFF)"判定;default → 6162 reset 无话术。
**文档要求**:Q4 无差异 → "回复会继续跟进、结束对话"。
**改造方案**:
1. 6170c N17c prompt 加 `NO_DIFF` 标签:用户确认无需修改/内容一致时输出 NO_DIFF
2. 6170c-parse 解析加 NO_DIFF
3. 6171c 加 case `no_diff` → 结束话术分支(复用差距5 的 6162-out)
4. 6170c prompt 当前判定什么?需读确认(CONFIRM_MODIFY/MODIFY_EXISTING 语义)。改造时加 NO_DIFF 第三类
**验证**:命中→确认→对比无差异→回"不用改"→输出结束话术 + 回 IDLE

---

## 2. 改造执行顺序建议

1. **差距1(D4模板化)** —— 独立、低风险,先做。改 6242 llm→code + 下游字段引用
2. **差距3(表链接)** —— 独立、低风险。6901 加常量 + 6262b/6176d 拼接
3. **差距5/6(结束话术)** —— 可合并,新增 1 个话术 code 节点 + 改若干 default 分支
4. **差距2(否认重查)** —— 中等,新增 6240build-denial + 改 6177-assigner 出边
5. **差距4(超时清态)** —— 最复杂,跨 wecom+dify,最后做。需先确认 wecom 能否拿 dify conversation_id

每项改完生成 v21(或分版本 v21a/v21b...),用户导入测试 app 验证通过再合入下一项,避免一次改太多难定位问题。

---

## 3. 验证通用方法

- 测试 app curl:`curl -X POST http://124.243.178.156:8501/v1/chat-messages -H 'Authorization: Bearer app-JnlcvQvqVLRgClM42lK5OqjP' -d '{"inputs":{},"query":"...","response_mode":"blocking","conversation_id":"","user":"test"}'`
- 验证 answer 含/不含期望内容 + state 标记(`<!--SYS:TIMER|state=xxx-->`)
- 飞书表记录核查:通过 120 后端 `curl http://localhost:2134/internal/bugtrack/record/{record_id}` 或 ssh 120 查飞书
- 每项改造的验证用例见各缺口"验证"小节

---

## 4. 关键记忆引用(compact 后可读 memory 文件补充上下文)

- `batch2-4-sufficiency-judge.md` — v20 充足度判定+引导循环+先查表(当前基线)
- `batch2-3-modify-window.md` — 修改窗保活+6239-llm(dify code 取不到时间的约束来源)
- `wecom-timer-architecture.md` — wecom timer 超时机制现状(差距4 依赖)
- `feishu-bitable-practice.md` — 飞书 bitable app_token/table_id(差距3 依赖)
- `dify-chatflow-batch1-practice.md` — assigner 不支持 constant 等踩坑
- `three-env-topology.md` — 三机拓扑+.env 差异红线
