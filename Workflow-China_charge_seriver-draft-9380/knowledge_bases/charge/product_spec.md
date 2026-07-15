# 充电桩产品功能矩阵 — <DATASET_PRODUCT_SPEC>

> 来源: V2.4.1 xlsx 9 个 sheet  
> 用途: 流程1 功能匹配预检(SPEC-C1, 节点 5011)  
> 检索策略: multi_retrieval, weights 0.7(本库) + 0.3(changelog)

## 字段结构

| 列 | 类型 | 说明 |
|----|------|------|
| id | string | func_001 |
| category | enum | 登陆/注册 / 首页 / 充电站 / 订单 / 钱包 / 优惠券 / 后台 / 家充 |
| module | string | 模块名 |
| name | string | 功能点 |
| endpoint | enum | user / butler / pc |
| region | enum | cn / overseas / both |
| pile_type | enum | public / home / both |
| version_added | string | V2.0 ~ V2.4.1 |
| is_implemented | bool | true / false |
| description | text | 200-500 字 |
| keywords_zh | list | 中文检索关键词 |
| keywords_en | list | 英文检索关键词 |

## 占位样例(从 V2.4.1 摘要)

### func_001 — 用户自主注册 (CN, both, V2.0+)
- endpoint: user / region: cn / pile_type: both
- description: 为用户提供自主注册,注册信息包括手机号、密码、验证码
- keywords: 注册,手机号注册,验证码注册 / register, signup

### func_002 — 微信小程序授权登录 (CN only, V2.0+)
- endpoint: user / region: cn
- notes: 仅小程序支持,App/H5 不要用

### func_003 — 谷歌第三方登录 (overseas, V2.1+)
- endpoint: user / region: overseas
- notes: 需开通 Google OAuth

### func_004 — 附近充电站列表 (public, both, V2.0+)
- endpoint: user
- description: 列表显示附近充电设备,按距离推荐

### func_005 — 充电中订单提醒 (V2.0+)
### func_006 — 设备通讯协议对接 (PC, V2.0+)
### func_007 — 结算账单生成 (PC, V2.0+)
### func_008 — Platform Coupon 平台券 (V2.0+)
### func_009 — Site Coupon 站点券 (V2.0+)
### func_010 — 家充桩用户注册 (V2.4+, home)

## 端类型分布

| endpoint | 估计功能点数 |
|----------|-------------|
| user | 18+ |
| butler | 12+ |
| pc | 25+ |
| 合计 | 55+ |

## 待补充
- [ ] V2.4.1 全部 9 sheet 提取(约 100+ 条)
- [ ] 海外版独有功能补全
- [ ] 家充 vs 公共桩功能差异标注
- [ ] 与 FAQ 21 节点交叉引用
