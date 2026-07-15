# 部署说明 - China_charge_seriver v2

> 给 Agent 4(集成与部署工程师)使用。本文档说明如何在 Dify 控制台完成 `China_charge_seriver_v2.yml` + 7 个知识库 + 后端的上线和验证。

**前置条件**:
- 服务器 `124.243.178.156` 上 Dify 已部署(参考 `china_charge_kf_ssh.md`)
- 已有 Dify 控制台管理员账号
- `Workflow-China_charge_seriver-draft-9380/` 目录已同步到 `/root/dify/china_charge_kf/`

---

## 步骤 1: 同步文件到服务器

```bash
rsync -avz "D:/AI/company-projects/ai-customer/china_charge_kf/Workflow-China_charge_seriver-draft-9380/" \
  root@124.243.178.156:/root/dify/china_charge_kf/Workflow-China_charge_seriver-draft-9380/

rsync -avz "D:/AI/company-projects/ai-customer/china_charge_kf/backend/charge_consult/" \
  root@124.243.178.156:/root/dify/china_charge_kf/backend/charge_consult/
```

确认文件:
```bash
ssh root@124.243.178.156 "ls -la /root/dify/china_charge_kf/Workflow-China_charge_seriver-draft-9380/workflow/"
# 期望: China_charge_seriver_v2.yml (38KB, 25 节点, 30 边)
ssh root@124.243.178.156 "ls -la /root/dify/china_charge_kf/Workflow-China_charge_seriver-draft-9380/knowledge_bases/charge/"
# 期望: 9 个 .md 文件
```

---

## 步骤 2: 在 Dify 控制台创建 7 个知识库

⚠️ **必须** 在导入工作流前创建完所有 KB,否则 yml 导入时会显示未知 dataset_id。

| 序 | 名称 | 数据源 | 对应 yml 占位 |
|----|------|--------|---------------|
| 1 | `china-charge-product-spec` | `knowledge_bases/charge/product_spec.md` | `<DATASET_PRODUCT_SPEC>` |
| 2 | `china-charge-product-changelog` | `knowledge_bases/charge/product_changelog.md` | `<DATASET_PRODUCT_CHANGELOG>` |
| 3 | `china-charge-faq` | `knowledge_bases/charge/faq_21nodes.md` | `<DATASET_FAQ>` |
| 4 | `china-charge-fault-diagnosis` | `knowledge_bases/charge/fault_diagnosis.md` | `<DATASET_FAULT_DIAGNOSIS>` |
| 5 | `china-charge-pricing` | `knowledge_bases/charge/pricing.md` | `<DATASET_PRICING>` |
| 6 | `china-charge-operation-guide` | `knowledge_bases/charge/operation_guide_zh/en/vi.md` (3 文件合并) | `<DATASET_OPERATION_GUIDE>` |

**操作**:
1. Dify 控制台 → 知识库 → 创建知识库
2. 名称按上表
3. 索引模式: 高质量(已有 rerank 模型)
4. 上传对应 .md 文件
5. 等待 embedding 完成(约 30-60s/库)
6. 复制 dataset_id(URL 中的 `datasets/{id}` 部分)

---

## 步骤 3: 替换 yml 中的占位符

```bash
cd /root/dify/china_charge_kf/Workflow-China_charge_seriver-draft-9380/workflow/

# 6 个 dataset_id 替换(操作指南用 3 个 ID 逗号分隔)
export DIFY_DATASET_PRODUCT_SPEC="<从控制台 URL 复制>"
export DIFY_DATASET_PRODUCT_CHANGELOG="<...>"
export DIFY_DATASET_FAQ="<...>"
export DIFY_DATASET_FAULT_DIAGNOSIS="<...>"
export DIFY_DATASET_PRICING="<...>"
export DIFY_DATASET_OPERATION_GUIDE="<zh-id>,<en-id>,<vi-id>"

sed -i "s|<DATASET_PRODUCT_SPEC>|$DIFY_DATASET_PRODUCT_SPEC|g" China_charge_seriver_v2.yml
sed -i "s|<DATASET_PRODUCT_CHANGELOG>|$DIFY_DATASET_PRODUCT_CHANGELOG|g" China_charge_seriver_v2.yml
sed -i "s|<DATASET_FAQ>|$DIFY_DATASET_FAQ|g" China_charge_seriver_v2.yml
sed -i "s|<DATASET_FAULT_DIAGNOSIS>|$DIFY_DATASET_FAULT_DIAGNOSIS|g" China_charge_seriver_v2.yml
sed -i "s|<DATASET_PRICING>|$DIFY_DATASET_PRICING|g" China_charge_seriver_v2.yml
sed -i "s|<DATASET_OPERATION_GUIDE>|$DIFY_DATASET_OPERATION_GUIDE|g" China_charge_seriver_v2.yml

# 验证替换完成
grep -c "DATASET_" China_charge_seriver_v2.yml
# 期望: 0(全部替换)
```

---

## 步骤 4: 验证 yml 完整性

```bash
cd /root/dify/china_charge_kf/

python -c "
import yaml
with open('Workflow-China_charge_seriver-draft-9380/workflow/China_charge_seriver_v2.yml') as f:
    d = yaml.safe_load(f)
print('nodes:', len(d['workflow']['graph']['nodes']))
print('edges:', len(d['workflow']['graph']['edges']))
print('dataset placeholders:', sum(1 for n in d['workflow']['graph']['nodes'] if 'dataset_ids' in n.get('data', {})))
ids = sorted({n['id'] for n in d['workflow']['graph']['nodes']}, key=lambda x: int(x.split('-')[0]))
print('ID range:', min(ids), '~', max(ids), '— 应在 5001-5099')
"
```

期望:
- 25 节点
- 30 边
- 5 个 KR 节点 dataset_ids 已替换
- 所有 ID 在 5001-5099

---

## 步骤 5: 导入工作流

1. Dify 控制台 → 工作流 → 导入 DSL 文件
2. 选择 `China_charge_seriver_v2.yml`
3. Dify 会自动解析节点;检查:
   - 25 个节点全部识别
   - 5 个 knowledge-retrieval 节点的 dataset_ids 显示为已存在的库
   - LLM 节点的模型选择: `doubao-seed-2-0-lite`
4. 点击"发布" → "发布更新"
5. 进入"访问 API"页,复制:
   - `workflow_id`(应是新生成的 ID)
   - `api_key` (以 `app-` 开头)

记录:
```bash
DIFY_WORKFLOW_CHARGE=China_charge_seriver_v2
DIFY_API_KEY_CHARGE=app-xxxxx
DIFY_WORKFLOW_ID_CHARGE=<新 ID>
```

---

## 步骤 6: 部署后端容器

```bash
cd /root/dify/china_charge_kf/backend

# 创建 .env.dify-charge(从模板复制并填值)
cp charge_consult/.env.dify-charge.example .env.dify-charge
vim .env.dify-charge
# 填 DIFY_API_KEY_CHARGE / DIFY_WORKFLOW_ID_CHARGE

# docker compose 启动(参考 health_consult 配置,新增 charge service)
docker compose up -d backend-dify-charge
docker logs -f backend-dify-charge | head -50
```

健康检查:
```bash
curl http://localhost:8014/api/charge-consult/health
# 期望: {"status":"ok","service":"AI Charge Consult","version":"0.1.0"}

curl 'http://localhost:8014/api/charge-consult/danger-keywords?endpoint=user' | head
# 期望: 11 个 user 端危险信号 JSON
```

---

## 步骤 7: 冒烟测试(7 个用例)

### 7.1 路径 A: 售前
```bash
curl -X POST http://localhost:8014/api/charge-consult/chat \
  -F "text=这桩有什么功能?" -F "session_id=test-A"
# 期望: scene=pre_sale, source=dify
```

### 7.2 路径 B: 危险信号(硬闸门)
```bash
curl -X POST http://localhost:8014/api/charge-consult/chat \
  -F "text=我的桩漏电了,跳闸后无法复位" -F "session_id=test-B-danger"
# 期望: scene=after_sales, risk_level=urgent, danger.matched=true
```

### 7.3 路径 C: 操作指导(链接保留)
```bash
curl -X POST http://localhost:8014/api/charge-consult/chat \
  -F "text=App 怎么报修?" -F "session_id=test-C"
# 期望: scene=operation, manual.deep_link 含 /charge/pages/malfunction/malfunction
```

### 7.4 路径 D: 报价
```bash
curl -X POST http://localhost:8014/api/charge-consult/chat \
  -F "text=7kW 充电桩多少钱?" -F "session_id=test-D"
# 期望: scene=pricing, pricing_table 非空
```

### 7.5 路径 E: 兜底
```bash
curl -X POST http://localhost:8014/api/charge-consult/chat \
  -F "text=hello" -F "session_id=test-E"
# 期望: scene=fallback, next_actions 含 4 类引导
```

### 7.6 4 维分类: 家充
```bash
curl -X POST http://localhost:8014/api/charge-consult/chat \
  -F "text=家充桩怎么用?" -F "session_id=test-home"
# 期望: pile_type=home
```

### 7.7 4 维分类: 海外 + 端
```bash
curl -X POST http://localhost:8014/api/charge-consult/chat \
  -F "text=How to set Role Management?" -F "language=en" -F "session_id=test-overseas"
# 期望: scene=faq, region=overseas, endpoint=pc
```

---

## 步骤 8: E2E 浏览器验证

1. 浏览器打开 `http://ai.trendpower.cc/chat/?view=charge`
2. 屏 1:输入"这桩有什么功能" → 跳屏 2
3. 输入"我的桩漏电了" → 红色警示条 + call_support
4. 输入"App 怎么报修" → 步骤 + 跳转链接
5. 输入"7kW 充电桩多少钱" → 报价表
6. 控制台:无 404 / CORS / JS error
7. 网络: `POST /api/charge-consult/chat` 200 OK

---

## 回滚方案

若上线后发现问题:
1. 后端 `DIFY_WORKFLOW_CHARGE` 改回旧 workflow_id(若有)
2. `docker compose restart backend-dify-charge`
3. 前端 `?view=charge` 路由保留,降级到 `local_fallback` 仍可用

---

## 节点 ID 对照表(部署时验证用)

| ID | 名称 | 类型 | SPEC |
|----|------|------|------|
| 5001 | start | start | - |
| 5002-1 | code_4维分类 | code | B1 |
| 5002-2 | KR_FAQ | knowledge-retrieval | B1 |
| 5002-3 | code_FAQ包装 | code | B1 |
| 5002-4 | llm_意图分类降级 | llm | B1 |
| 5002-5 | code_fallback | code | B1 |
| 5003 | if-else_scene路由 | if-else | B1 |
| 5010 | llm_功能咨询 | llm | D1 |
| 5011 | 流程1_KR_功能匹配 | knowledge-retrieval | C1 |
| 5012 | code_流程1验证 | code | C1 |
| 5013 | 流程2_KR_清单校验 | knowledge-retrieval | C2 |
| 5014 | code_流程2验证 | code | C2 |
| 5015 | 流程3_KR_报价 | knowledge-retrieval | C3 |
| 5017 | code_路径A包装 | code | D1 |
| 5020 | code_危险信号判定 | code | D2 |
| 5021 | llm_业务诊断 | llm | D2 |
| 5022 | code_紧急路径 | code | D2 |
| 5030 | KR_操作手册 | knowledge-retrieval | D3 |
| 5031 | llm_多语言指引 | llm | D3 |
| 5032 | code_链接保留 | code | D3 |
| 5040 | llm_报价整理 | llm | C3 |
| 5080 | aggregator_5路汇聚 | variable-aggregator | E1 |
| 5081 | code_打包SceneResponse | code | E1 |
| 5090 | llm_兜底 | llm | B1 |
| 5099 | 结束 | end | E1 |

---

## 变更日志

| 日期 | 变更 |
|------|------|
| 2026-06-18 | 初版,SPEC-H1 部署文档,与 v2 yml 同步 |
