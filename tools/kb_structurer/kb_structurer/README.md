# KB Structurer — 充电桩客服知识库拆解工具

把原始素材(CSV / Excel / Word / 手工)拆解为 Dify 知识库可直接消费的 Markdown 文档。

## 适用场景

- 接到新业务模块,需要把 Excel/Word 整理成 KB
- 现有 KB 内容过期,需要按新格式重新生成
- 多份同主题素材需要合并梳理

## 工具架构

```
kb_structurer/
├── structurer.py            # 主 CLI(入口)
├── parsers/                 # 各格式解析器
│   ├── __init__.py
│   ├── csv_parser.py        # CSV → menu 文档
│   ├── xlsx_parser.py       # Excel → faq/规则 文档
│   ├── docx_parser.py       # Word → SOP/process 文档
│   └── manual.py            # 手工编辑 → 模板填充
├── templates/               # Jinja2 MD 模板
│   ├── menu.md.j2
│   ├── faq.md.j2
│   ├── business_rule.md.j2
│   └── process.md.j2
├── configs/
│   └── kb_types.yaml        # KB 类型配置
└── examples/
    └── csv_to_menu.py       # 完整示例:CSV → menu_docs
```

## 设计原则

1. **确定性拆分**:不靠 LLM 自由发挥,按结构化规则拆
2. **可重跑**:同一份输入每次产出同样的 MD(diff 干净)
3. **可版本化**:MD 文件名带 NNNN 前缀,git diff 友好
4. **多对一映射**:N 个源文件 → 1 个 MD(按主题聚合,避免碎片化)

## 快速开始

### 1. CSV → menu KB

```bash
python3 structurer.py csv-to-menu \
  --input /path/to/data_processed.csv \
  --output /tmp/menu_docs/ \
  --encoding utf-8-sig
```

产出:
```
/tmp/menu_docs/
├── menu_0001_代码生成.md
├── menu_0002_管理员设置.md
...
└── menu_0719_xxx.md
```

每个 MD:
```markdown
# 菜单名

## 路径
- **菜单层级**: 平台>平台设置>常用工具>代码生成
- **顶级菜单**: 平台
- **菜单 ID**: `f513f9e7cb53c16e5de982e12268b070`

## 字段中英文对照
| 字段 Key | 中文 | English |
|---|---|---|

## 检索关键词
代码生成, 平台, 平台设置, 常用工具
```

### 2. Excel FAQ → faq KB

```bash
python3 structurer.py xlsx-to-faq \
  --input /path/to/faq.xlsx \
  --output /tmp/seed_faq/ \
  --topic-mapping configs/topic_mapping.yaml
```

### 3. Word SOP → process KB

```bash
python3 structurer.py docx-to-process \
  --input /path/to/sop.docx \
  --output /tmp/seed_proc/ \
  --sections "站点创建,运营商入驻,设备投放,退款流程,充电订单"
```

### 4. 手工模板填充

```bash
python3 structurer.py from-template \
  --template templates/business_rule.md.j2 \
  --data configs/biz_seed.yaml \
  --output /tmp/seed_biz/ \
  --batch
```

## 拆分策略详解

### 策略 1:CSV 菜单拆分(确定性)

输入:有层级路径的菜单 CSV
拆分:
- 按 `(name, hierarchy_path)` 组合去重(同一菜单可能在不同位置,合并)
- 同一菜单的多个 i18n 行合并到一个 MD
- 文件名:`menu_{4位序号}_{菜单名}.md`

边界:
- 单 MD 不超过 200 行(过大就拆分)
- 关键词提取:菜单名 + 顶级菜单 + 路径分段

### 策略 2:Excel FAQ 拆分(主题聚合)

输入:FAQ Excel(节点 / 问题 / 答案)
拆分:
- 按 N 个节点聚合到 4-6 个主题(MD 数 = 主题数,不是节点数)
- 每个主题选 3-5 个高频 Q&A
- 答案保留英文/中文原文,不要改写

边界:
- 主题映射表配置在 `configs/topic_mapping.yaml`
- 主题数推荐 4-6,不要超过 8(避免 KB 碎片化)

### 策略 3:Word SOP 拆分(场景识别)

输入:Word SOP 文档
拆分:
- 按 H1/H2 标题识别场景
- 关键词过滤:`流程`,`步骤`,`操作`,`入口`
- 每个场景 = 一个 MD,带 `## 步骤` `## 常见拦截` `## 检索关键词`

边界:
- 场景数推荐 5-8
- 不要把整个 SOP 拆成 1 个 MD(检索精度差)

### 策略 4:手工模板填充(快速迭代)

输入:专家写的种子 YAML
拆分:
- 用 Jinja2 模板生成 MD
- 字段:`name`, `steps`, `traps`, `keywords`

## 与 Dify 对接

```python
from kb_structurer.uploader import bulk_upload
bulk_upload(
    kb_id="c1b76f43-...",  # Dify KB ID
    md_dir="/tmp/menu_docs/",
    api_key="app-xxx",
)
```

走 console API:
1. POST `/files/upload` (multipart) → file_id
2. POST `/datasets/<id>/documents` (JSON) → document
3. 一次上传一批(已实现,绕过 5 文件限制)

## 复用场景示例

| 业务变更 | 操作 |
|---|---|
| 新菜单上线 | 更新 CSV → 重跑 `csv-to-menu` → Dify 自动索引 |
| FAQ 文档更新 | Excel 重出 → 跑 `xlsx-to-faq` → 上传 |
| 新流程上线 | 写 1 份 YAML → `from-template` 生成 MD |
| 多语言 KB | 同一份 input,切换 `--language` |

## 输出文件名规范

```
{type}_{NNNN}_{slug}.md

例:
menu_0001_代码生成.md        # 菜单
faq_01_role_management.md    # FAQ
biz_01_pricing.md            # 业务规则
proc_01_create_site.md       # 流程
```

NNNN 4 位补零,slug 用 `_` 连接,保留原文(不翻译)。

## 扩展

新增 KB 类型只需:
1. 在 `parsers/` 加一个解析器
2. 在 `templates/` 加一个 Jinja2 模板
3. 在 `configs/kb_types.yaml` 注册