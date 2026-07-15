# 充电桩客服 — 知识库索引

> 配套工作流: China_charge_seriver v2 (node ID 5001-5099)  
> 配套后端: backend/charge_consult/  
> 数据源: 32-6.17 充电桩知识库(7 份原始资料)

## 7 个数据集清单

| 占位 ID | 文件 | 节点 | 检索策略 | 状态 |
|---------|------|------|----------|------|
| DATASET_PRODUCT_SPEC | product_spec.md | 5011 | multi_retrieval 0.7 | 占位 |
| DATASET_PRODUCT_CHANGELOG | product_changelog.md | 5011, 5013 | multi_retrieval 0.3, 0.5 | 占位 |
| DATASET_FAQ | faq_21nodes.md | 5002-2, 5013 | 单独 + 0.5 | 占位 |
| DATASET_FAULT_DIAGNOSIS | fault_diagnosis.md | 5015 | multi_retrieval 0.2 | 占位 |
| DATASET_PRICING | pricing.md | 5015 | multi_retrieval 0.8 | 占位 |
| DATASET_OPERATION_GUIDE | operation_guide_{zh,en,vi}.md | 5030 | metadata filter language | 占位 |
| DATASET_I18N_FALLBACK | (前端独立) | — | — | 待生成 |

## 占位 vs 真实数据

所有 md 文件当前是 **占位骨架**:
- 字段结构已定义
- 真实内容由产品运营按 V2.4.1 xlsx + FAQ xlsx + 手册 docx 填充
- Dify 索引前需先回填内容

## 部署占位符替换

参考 DEPLOY_INSTRUCTIONS.md 步骤 5:
```bash
cd workflow
sed -i "s|<DATASET_PRODUCT_SPEC>|$DIFY_DATASET_PRODUCT_SPEC|g" China_charge_seriver.yml
sed -i "s|<DATASET_PRODUCT_CHANGELOG>|$DIFY_DATASET_PRODUCT_CHANGELOG|g" China_charge_seriver.yml
sed -i "s|<DATASET_FAQ>|$DIFY_DATASET_FAQ|g" China_charge_seriver.yml
sed -i "s|<DATASET_FAULT_DIAGNOSIS>|$DIFY_DATASET_FAULT_DIAGNOSIS|g" China_charge_seriver.yml
sed -i "s|<DATASET_PRICING>|$DIFY_DATASET_PRICING|g" China_charge_seriver.yml
sed -i "s|<DATASET_OPERATION_GUIDE>|$DIFY_DATASET_OPERATION_GUIDE|g" China_charge_seriver.yml
```

## 验证清单(SPEC-H1 部署前)

- [ ] 7 个 Dify KB 已在控制台创建
- [ ] 每个 KB 都有真实数据(非占位)
- [ ] 嵌入完成(约 30-60s/库)
- [ ] dataset_id 已替换 yml 占位符
- [ ] 后端 `.env.dify-charge` 配置新 workflow_id 和 api_key
