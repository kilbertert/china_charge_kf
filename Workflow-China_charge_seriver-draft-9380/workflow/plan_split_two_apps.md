# 工作流分块计划:v24 → App A(KB问答) + App B(bug追踪)

> 方案:两个独立 Dify app + wecom 标记驱动路由(用户已选)。
> 核心约束:Dify conversation_variables 按 app 隔离 → 状态机(cv_flow_state)必须整体在 B,A 无 bug 状态。

## 一、架构总览

```
用户消息 → wecom 路由器(按 active_app 标记)
            ├─ active=A → 调 App A(KB问答) → 回答
            │              └─ A 检测 bug 意图(L3 D) → 发 SWITCH_TO_BUG 标记
            │                  → wecom 改投 B(同条消息)→ B 做 bug 采集
            └─ active=B → 调 App B(bug状态机) → 回答
                         └─ B IRRELEVANT(新话题) → 发 SWITCH_TO_KB_REENTRY → wecom 改投 A
                         └─ B 结束(写表/放弃/无差异) → 发 SWITCH_TO_KB_DONE + 话术 → wecom 发话术,下条→A
```

wecom 每 (user,scope) 维护:`{active_app, conv_id_A, conv_id_B}`(两 app 各自独立 Dify 会话)。

## 二、App A(KB问答,无 bug 状态)

**节点**(从 v24 抽取,~22 节点):
6001/6002/6003/6004 + 6101(L1) + 6102/6103-if/6103-llm/6103-parse/6104/6105/6106/6107/6108/6110/6111(FAQ) + 6201(L3) + 6210/6211/6212(A菜单) + 6220/6221(B功能) + 6230/6231(C流程) + 6098/6099 + 6901

**不含**:6601(状态机)/6170x/6171x/6240-6262/6250x/6239/6162* — 全归 B。

**改动**:
- 移除 6601(A 无状态机;入口 6002→6003→6101)
- 6201 的 D 输出(bug 意图):原 →6250(B 的),改为 → 新 code 节点 `6201-switch-bug`(输出 `<!--SYS:SWITCH_TO_BUG-->`)→ 6098。A 不做 bug 采集,只发标记,wecom 改投 B。
- A 保留自己的"澄清"会话变量(FAQ 再问流程 6104/6105 用),与 bug 状态无关。
- 验证 A 无任何 `<!--SYS:TIMER` 标记(timer 只属 B)。

## 三、App B(bug追踪,有 cv_flow_state)

**节点**(从 v24 抽取,~70 节点):
6001/6002 + 6601 + 6250*(N5) + 6250b*(N5b) + 6240build/6240/6240-parse/6241 + 6242/6242b/6242c + 6243/6243b + 6244/6244-timer + 6170/6170-parse/6171 + 6170b/6171b + 6170c/6171c + 6170d/6171d + 6172 + 6173* + 6175* + 6176a/b/c/d + 6177* + 6240builddnl/6240-denial/6240-denial-parse/6241-denial/6242b-denial/6242-denial + 6239* + 6260a/b/c/6261/6262/6262b + 6162/6162-abort/6162-out + 6098/6099 + 6901

**不含**:6101/6201(L1/L3 路由)/6102-6111(FAQ)/6210-6231(A/B/C 知识库)— 全归 A。

**改动**:
1. **IDLE 入口直达 N5**:6601[IDLE/default] 原 →6003→6101→6201→D→6250,改为 6601[IDLE] →6250(B 不做 L1/L3,A 已判定是 bug)。移除 6003/6004(B 无澄清流)。
2. **IRRELEVANT 改发标记**(替换 re-entry):6171/6171b/6171c/6171d 的 default 原 →6162→6003(re-entry 进 L1),改为 →6162(reset IDLE)→ 新 code `6162-switch-kb`(输出 `<!--SYS:SWITCH_TO_KB_REENTRY-->`,无话术)→6098。wecom 改投 A 处理新话题。
3. **结束态加 SWITCH_TO_KB_DONE**(下条回 A):以下节点在现有话术+cancel 基础上追加 `<!--SYS:SWITCH_TO_KB_DONE-->`:
   - 6162-out(放弃/无差异结束话术)
   - 6262b(N16 写表汇报+cancel)
   - 6176d(N14 update 汇报+cancel)
4. 移除 6162→6003 边(re-entry 不再回 L1)。

## 四、标记协议(wecom 解析,复用现有 timer 标记架构)

| 标记 | 发出方 | wecom 动作 |
|---|---|---|
| `<!--SYS:SWITCH_TO_BUG-->` | A(6201 D 意图) | active=B,同条消息改投 B |
| `<!--SYS:SWITCH_TO_KB_REENTRY-->` | B(IRRELEVANT 新话题) | active=A,同条消息改投 A(B 无话术) |
| `<!--SYS:SWITCH_TO_KB_DONE-->` | B(写表/放弃/无差异结束) | active=A,发 B 话术,不改投 |

## 五、wecom 改动(`/home/ranlei/wecom-ai-customer-service/`)

1. **config.py**:`DIFY_APP_A_TOKEN`(KB)+ `DIFY_APP_B_TOKEN`(bug)两个 token(或 A/B 两组 base+token)。保留 `DIFY_API_BASE`。
2. **dify_client.py / dify.py**:支持按 app 选 token(`run_chatflow(..., app="A"|"B")`)。两个 DifyClient 实例或参数化。
3. **conversation_store.py**:`get/save` 扩展为存结构 `{active:"A", conv_A:..., conv_B:...}`(key 仍 user+scope)。新增 `get_active`/`set_active`。
4. **message_processor.py** 路由逻辑(第 5 步调 AI 处):
   ```
   active = store.get_active(user, scope)
   resp = call_app(active, query, conv_id[active])
   markers = parse_markers(resp.answer)
   if "SWITCH_TO_BUG" in markers:
       store.set_active(user, scope, "B")
       resp = call_app("B", query, conv_id["B"])   # 改投 B
   elif "SWITCH_TO_KB_REENTRY" in markers:
       store.set_active(user, scope, "A")
       resp = call_app("A", query, conv_id["A"])   # 改投 A
   elif "SWITCH_TO_KB_DONE" in markers:
       store.set_active(user, scope, "A")           # 发 B 话术,不改投
   reply = strip_markers(resp.answer)
   save conv_id[active]
   ```
5. **marker parser**:扩展现有 timer_coordinator 的标记解析(或新模块),识别 3 个 SWITCH 标记。TIMER arm/cancel 标记仍由 B 发、wecom timer_coordinator 处理(不变)。

## 六、实施步骤(增量验证)

1. **patch_split_a.py**:从 v24.yml 生成 `charge_charging_A.yml`(抽 A 节点 + 6201 D→switch-bug + 移除 6601)。
2. **patch_split_b.py**:从 v24.yml 生成 `charge_charging_B.yml`(抽 B 节点 + 6601 IDLE→6250 + default→6162-switch-kb + 6162-out/6262b/6176d 加 SWITCH_TO_KB_DONE + 移除 6003/6101/6201)。
3. 两个 yml 本地校验(节点id唯一/边端点存在/无悬空引用/6098 聚合器含各分支末尾)。
4. Dify 建两个新 app(导入 A.yml、B.yml),取 token。先**不**动生产 app(v24 仍在)。
5. wecom 改 config/store/processor/parser。开发机自测。
6. 端到端测(测试环境):
   - KB 问答(A):FAQ/菜单/功能/流程 → A 直接答
   - A→B:KB 问题触发 bug 意图 → 改投 B → bug 采集(D4/N6)
   - B 多轮状态机:确认/修改/否认/放弃/无差异 全闭环
   - B→A reentry:bug 流中发 KB 问题 → 改投 A → A 答
   - B→A done:写表后 → 发汇报话术 → 下条 KB 问题进 A
7. 验证通过后:wecom .env 切到 A/B 双 app token,生产部署。旧 v24 app 保留作回滚。

## 七、风险与回滚

- **风险1**:A/B 节点抽取遗漏(共享节点 6002/6098/6901/6162 等)。→ patch 脚本生成后用脚本全量校验边端点+变量引用,无悬空才导入。
- **风险2**:wecom 双 conv_id 路由状态不一致(active 与实际错位)。→ 标记驱动同步,每条消息根据上次响应标记更新 active;done/reentry 都切 A,bug 意图切 B,无第三态。
- **风险3**:handoff 双调用延迟(A→B 或 B→A 同条消息调两次)。→ handoff 罕见(仅意图切换),可接受;blocking 模式总耗时≈两次 Dify 调用。
- **回滚**:wecom .env 切回单 v24 app token 即恢复;A/B app 可停用。v24.yml 保留。

## 八、待确认/注意

- 6201(L3)的 D 类是"bug反馈"意图——确认 6201 的 4 路分类与 A/B/C/D 语义(实施前看 6201 配置)。
- A 是否有 TIMER 标记(应无)——实施前 grep 确认。
- 6261 设的是 IDLE 还是 modify_window(影响 SWITCH_TO_KB_DONE 加在哪)——实施前读 6261 items。
- wecom conversation_store 现有 InMemory/Redis 实现——扩展时保持接口兼容。
