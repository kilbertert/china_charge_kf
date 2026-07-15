# 多轮会话设计 — SPEC-A2

> 状态: 已设计,后端 Redis 待 SPEC-H1 部署
> 关联: `04_CONTRACT_SCENE_RESPONSE.md` § 3.2 (ChargeChatRequest)
>       `05_NODE_TOPOLOGY.md` § 5001 (start inputs)

## 1. 目标

支持两轮对话 + 第三轮之后回流(架构图右侧"流回输入到后台")。
后端用 Redis 存会话状态,Dify yml 只透传 session_id / turn,不存状态。

## 2. 输入字段(5001 start)

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `input_session_id` | string | 否 | 后端自动生成 UUID if 空 |
| `input_turn` | int 1-20 | 否 | 默认 1 |
| `input_context_json` | string (JSON) | 否 | 上一轮 {flow1, flow2, flow3, scene, danger} 序列化 |
| `input_language` | enum | 否 | zh / en / vi |
| `input_hint_endpoint` | enum | 否 | user / butler / pc |
| `input_hint_region` | enum | 否 | cn / overseas |

## 3. 后端 Redis Schema

Key: `charge:session:{session_id}`  
TTL: 3600s(1 小时)  
Value: JSON

```json
{
  "session_id": "uuid-xxx",
  "created_at": "2026-06-18T...",
  "last_turn_at": "2026-06-18T...",
  "turn_count": 2,
  "language": "zh",
  "endpoint": "user",
  "history": [
    {
      "turn": 1,
      "user_text": "我的桩漏电了",
      "scene_response": {<ChargeSceneResponse>}
    }
  ],
  "context": {
    "flow1_matched": null,
    "flow2_verified": null,
    "flow3_pricing": null,
    "last_scene": "after_sales",
    "last_danger_matched": true
  }
}
```

## 4. 多轮流转

### Turn 1 (第一轮)
- 5002-1 scene_classifier 判定 scene
- 后台三流 5011/5013/5015 预检
- 走对应路径 A/B/C/D/E
- 5081 打包输出 SceneResponse
- 后端把 {turn=1, scene_response} 写入 Redis.history[0]
- 后端把 {flow1/2/3, scene, danger} 写入 Redis.context

### Turn 2 (第二轮)
- 用户带 session_id 进入
- 后端从 Redis 读出 context,作为 input_context_json 注入
- 5002-1 用 context.last_scene 作为"上一轮 scene 提示",可能不重新分类
- 后台三流只在用户提到新功能时重跑,否则复用 Turn 1 结果
- 业务路径走"细化诊断"分支(根据场景 A/B/C 不同)

### Turn 3+ (回流)
- 用户可发起全新问题,回流到 Turn 1 的入口
- 后端检测"用户意图已切换"(scene 与 last_scene 不同),重置 context
- 否则继续多轮延续

## 5. 实现路径

| 层 | 实现 |
|----|------|
| 后端 | `backend/charge_consult/session_store.py` — Redis 封装 |
| API | `POST /api/charge-consult/chat` 自动 read/write Redis |
| Dify | 5001 start 接收 input_session_id + input_turn,透传到 inputs |
| 前端 | localStorage 缓存 session_id,每次请求带 |

## 6. MVP 简化

为了 SPEC-A2 MVP 阶段,先实现**最小可用**:
- 后端从 Redis 读 context(没有就空)
- 写 history(每次 chat 追加一条)
- 不做"scene 已切换"检测,统一用 input_context_json 透传
- TTL 3600s,后续可调

## 7. 后续拓展

- [ ] WebSocket 推送(用于流式输出)
- [ ] 工单系统集成(turn > 3 时自动建议)
- [ ] 多模态历史(图片/语音 cache)
- [ ] 会话分类标签(用于运营分析)

## 8. 与 SPEC-G1 的衔接

`backend/charge_consult/main.py:chat()` 端点:
1. 接收 session_id,turn
2. 从 Redis 读 `charge:session:{sid}` (若存在)
3. 合并到 inputs 作为 `input_context_json`
4. 调 Dify / 本地兜底
5. 写回 Redis(增量,不全量覆盖)

## 9. 变更日志

| 日期 | 变更 |
|------|------|
| 2026-06-18 | 初版,SPEC-A2 设计完成 |
