# 报价表 — <DATASET_PRICING>

> 用途: 流程3 报价查询(SPEC-C3, 节点 5015, multi_retrieval 权重 0.8)  
> 触发: scene=pricing

## 字段结构

| 列 | 类型 | 说明 |
|----|------|------|
| sku | string | 产品/配件 SKU |
| product_name_zh | string | 中文名 |
| product_name_en | string | 英文名 |
| category | enum | 充电桩 / 充电枪 / 线缆 / 安装 / 延保 / 配件 |
| power_kw | int | 7/11/21/30/60/120 |
| region | string | CN / OVERSEAS-NA / OVERSEAS-EU / OVERSEAS-SEA |
| price | decimal | 价格 |
| currency | string | CNY / USD / EUR / VND |
| valid_from | date | 生效日期 |
| valid_until | date | 失效日期(可空) |
| channel | enum | direct / distributor / both |

## 占位样例

### CHARGER-AC-7KW-CN — 7kW 家用交流充电桩 (CN)
- power_kw: 7 / region: CN / price: 2580.00 CNY
- valid: 2026-01-01 ~ 2026-12-31
- notes: 含 5 米线缆,基础安装

### CHARGER-AC-11KW-CN-PUBLIC — 11kW 公共交流桩 (CN)
- power_kw: 11 / price: 8500.00 CNY
- notes: 不含安装,需现场报价

### CHARGER-DC-60KW-NA — 60kW 直流快充 (NA)
- power_kw: 60 / region: OVERSEAS-NA / price: 18500.00 USD
- notes: 出口美国/加拿大

### GUN-TYPE2-32A — Type 2 充电枪 32A (EU)
- category: 充电枪 / region: OVERSEAS-EU / price: 380.00 EUR

### INSTALL-BASIC-CN — 基础安装服务 (CN)
- category: 安装服务 / price: 800.00 CNY
- notes: 含 30 米以内线缆

## 价格严格规则(LLM 必须遵守)

1. 价格必须从本库原文复制,不允许编造
2. 货币必须与 region 匹配(CN-CNY, NA-USD, EU-EUR, SEA-VND)
3. 过期价格标注"已过期"
4. 不允许"促销推荐"等模糊话术
5. 无匹配返回"暂无报价,请联系销售"

## 待补充
- [ ] 30+ SKU 完整列表
- [ ] 季度价格有效期管理
