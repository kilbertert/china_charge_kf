# v20 改造方案：补齐「信息充足度判定 + 引导补充循环」

## 一、目标
按 `新反馈增加.txt` 提示词，让新反馈路径在 **N5 提取前** 先判定信息充足度：
- 信息**充足** → 正常提取四字段 → 查表 → 确认（现状不变）
- 信息**不足** → **不生成结构化数据**，只输出引导话术，设态等用户补充 → 补充后整合转写 → 再次判定
- 最多引导 2 次，第 3 次仍不足则兜底生成带「待确认」的结构化数据

## 二、现状架构（已摸清）

### 新反馈首次路径（IDLE → 新 bug 确认）
```
6601[default] → 6003 → 6101[L1] → ... → 6201[L3分发]
  → class_d → 6250[N5转写+关键词]            ← 首次提取（无脑提取，缺失填"待确认"）
    → 6250-parse → 6240build → 6240[查表] → 6240-parse → 6241[是否已存在]
      → 未命中 → 6243[var_标记bug已记录, 设await_confirm_new] → 6244[N6确认话术] → 6244-timer → 6098
      → 命中   → 6242[D4汇报] → ...
```
**缺口**：6250 之前无任何充足度判定；信息再模糊也直接提取。

### 现成补充循环（await_confirm_new 态，可复用）
```
6601[await_confirm_new] → 6170[N17相关性识别] → 6170-parse → 6171[N17分发]
  → CONFIRM_NEW  → 6260a/b/c → 6261[写表+设IDLE] → 6262 → 6098
  → MODIFY_NEW   → 6172[合并 cv_feedback_zh + query_text] → 6250b[N5b转写] → 6250b-parse → 6243b[更新cv] → 6244[重新确认] → 6098
  → IRRELEVANT   → 6162[reset IDLE] → 6003
```
**关键**：6172 合并的是 `cv_feedback_zh`（旧）+ `query_text`（新补充），正好对齐提示词的「整合 input + xinfankui」。

## 三、改造方案

### 核心思路
1. **N5(6250) / N5b(6250b) prompt 升级**为 `新反馈增加.txt` 完整版，输出统一加 `【充足度】SUFFICIENT/INSUFFICIENT` 标签 + 条件性 JSON + 话术
2. N5 / N5b 之后各插一个 **judge code 节点**解析标签，分支：充足→现有提取链；不足→引导话术直出 + 设态
3. **复用** 现有 `await_confirm_new + 6170 + 6172 + 6250b` 循环处理「补充后重新转写」
4. 新增 `cv_clarify_count` 计数，实现 2 次兜底

### 输出格式约定（N5/N5b prompt 强约束）
```
【充足度】SUFFICIENT
【内部结构化数据】
{"mokuai":"...","caozuomiaoshu":"...","huanjing":"...","leixing":"..."}
【客户侧回复话术】
...
```
或
```
【充足度】INSUFFICIENT
【客户侧引导话术】
...（5 种场景引导话术之一，末尾追加 ID 提示）
```

### 新增节点（6 个）
| 新节点 id | 类型 | 作用 |
|---|---|---|
| `6250-judge` | code | 解析 6250 输出：提取充足度标签 + JSON；输出 `label` + 四字段（不足时空） |
| `6250-insuf` | assigner | 不足时设：`cv_flow_state=await_confirm_new` + `cv_feedback_zh=query_text`（存原始反馈供下轮合并）+ `cv_clarify_count=1` |
| `6250-insuf-out` | code | 把 6250 的引导话术包成 `answer_text`（拼 TIMER|state=await_confirm_new 标记）→ 6098 |
| `6250b-judge` | code | 解析 6250b 输出：标签 + JSON + 计数判定（count≥2 且不足→强制兜底） |
| `6250b-insuf` | assigner | 不足且 count<2 时：`cv_clarify_count+1` + `cv_feedback_zh=6172.merged`（累积补充）+ 保持 await_confirm_new |
| `6250b-insuf-out` | code | 把 6250b 引导话术包成 `answer_text` → 6098 |

### 改动节点
- **6250 (N5)** prompt → `新反馈增加.txt` 完整版（输入 `6002.query_text`，首次场景）
- **6250b (N5b)** prompt → `新反馈增加.txt` 完整版（输入 `6172.merged`，迭代场景，强调"整合旧数据+补充"）
- **6901 (code_常量)** 加常量 `str_await_confirm_new`（若未暴露，供 insuf assigner 引用）—— 已有则跳过
- **conversation_variables** 新增 `cv_clarify_count`（int，默认 0）

### 改动边
**N5 分支（替换 `6250 → 6250-parse`）**：
- `6250 → 6250-judge`
- `6250-judge`(SUFFICIENT) `→ 6250-parse`（不变后续）
- `6250-judge`(INSUFFICIENT) `→ 6250-insuf → 6250-insuf-out → 6098`

**N5b 分支（替换 `6250b → 6250b-parse`）**：
- `6250b → 6250b-judge`
- `6250b-judge`(SUFFICIENT 或 count≥2兜底) `→ 6250b-parse → 6243b`（不变后续）
- `6250b-judge`(INSUFFICIENT 且 count<2) `→ 6250b-insuf → 6250b-insuf-out → 6098`

### 兜底逻辑（6250b-judge code 内）
```
若 label==INSUFFICIENT 且 cv_clarify_count>=2:
    强制输出 label=SUFFICIENT + 四字段全填"待确认"  → 走 6243b → 6244 确认
否则按真实 label 分支
```

## 四、数据流（改造后）

### 首次信息充足（主流，不变）
`6250 → 6250-judge[SUFFICIENT] → 6250-parse → 6240 → 6241 → 6243 → 6244 → 6098`

### 首次信息不足（新增）
`6250 → 6250-judge[INSUFFICIENT] → 6250-insuf(设态+存原始反馈+count=1) → 6250-insuf-out(引导话术) → 6098`
↓ 用户补充
`6601[await_confirm_new] → 6170 → MODIFY_NEW → 6172(合并原始+补充) → 6250b → 6250b-judge`
- 充足 → `6250b-parse → 6243b → 6244 → 6098`
- 仍不足(count<2) → `6250b-insuf(count=2, 累积merged) → 6250b-insuf-out → 6098`（第二次引导）
- 仍不足(count≥2) → 兜底四字段"待确认" → `6243b → 6244 → 6098`

## 五、风险与权衡
1. **LLM 格式稳定性**：Doubao-Seed-2.0-lite 是轻量模型，`【充足度】` 标签可能偶发缺失。judge code 需容错：无标签时 fallback 按"是否含 JSON"判定（有 JSON→SUFFICIENT，无→INSUFFICIENT）。
2. **N6 话术冗余**：充足时 N5 prompt 输出的话术仍被丢弃（N6 重新生成），与现状一致。本次不动 N6，聚焦充足度闭环。
3. **cv_feedback_zh 语义双重用途**：既作"结构化操作描述"又作"原始反馈锚点"。不足时写入 query_text（原始），充足时被 6250-parse 的 caozuomiaoshu 覆盖。语义自洽但需留意。
4. **计次边界**：count 从 1 起（首次不足设 1），6250b 不足时 +1，≥2 触发兜底。即首次引导 + 至多 1 次再引导 + 兜底，共 2 次引导，符合提示词"最多引导 2 次"。

## 六、实现方式
沿用批次二.3 的 patch 脚本模式：写 `patch_v20.py`（ruamel.yaml，复用 patch_v19.py 的 helpers），基于 `charge_charging_v19.yml` 生成 `charge_charging_v20.yml`。用户手动导入测试 app → 验证 → 发布生产。

## 七、验证计划（测试 app 3a4a5e88）
| 用例 | 输入 | 期望 |
|---|---|---|
| V1 首次充足 | "app扫码充电提示设备不存在，桩号CDZ001" | 直接提取+确认，无引导 |
| V2 首次不足 | "充电桩用不了，赶紧处理" | 输出引导话术，不写表，设 await_confirm_new |
| V3 补充后充足 | V2 后回"用户扫码启动不了，提示设备不存在，U89076" | 整合转写+确认 |
| V4 二次仍不足 | V2 后回"还是不行" | 再次引导（第 2 次） |
| V5 兜底 | V4 后回"不知道" | 生成"待确认"结构化数据+确认 |
| V6 命中已有 | "订单没有支付时间" | 走 D4 汇报，不触发充足度判定（N5 后查表命中分支） |

## 八、改动范围小结
- 新增 6 节点 + 1 会话变量 + 约 10 条边
- 改 2 个 LLM prompt（6250/6250b）+ 可能加 1 常量
- 不动 N6/6243/6244/6170/6171/6172/6601 主干（复用）
- 生成 v20.yml，v19 保持不变作回滚点
