# 方案：用户 bug 截图插入飞书 bug 记录表

## 一、需求理解
用户在 B 工作流（charge_charging_B_bugtrack）反馈 bug 时发的截图，要能**一起写入飞书 bug 记录表**，且在飞书表格里**内联可见**（不是一段 URL 文本）。

## 二、现状（已核实）
1. **图片流转**：WeCom 收图 → `message_processor` 下载图片字节 → 上传 Dify 文件库拿 `upload_file_id`（KF 默认 `app="A"`，bug 路由切 B 后可能跨 app）→ 以 `files` 数组发 Dify B chatflow → Dify 侧 `sys.files`（**仅当轮可见**）。
2. **多轮 bug 流**：图片轮 ≠ 写表轮（turn1 发图+描述→6201 分类 bug→6243 引导确认；turn2 确认→6260a 组装 fields→6260b POST `/add`→6260c 解析 record_id→cv_record_id）。图片 `upload_file_id` 跨轮丢失。
3. **6260a 节点**：入参全是会话变量（cv_mokuai/cv_feedback_zh/cv_leixing/cv_huanjing），返回 `{"body_json": json.dumps({"fields": fields})}`，6260b 原样 POST 到 `/internal/bugtrack/add`。**只组装文本 fields，无图片**。
4. **后端 `/add`**：`AddRecordRequest{fields}` → `feishu_add_record(fields)`。`dify_client` 有 `upload_file` 无 download。`feishu_bitable` 无附件上传。
5. **飞书表 schema**：18 字段，`截图1/2/3` 是 **type=1 文本**，**无附件字段（type=17）**。生产表 `app_token=DUCdbcr2ya2o5gszVKac2NuBnHh` / `table_id=tblkYK8aFYHLVQTa` / app `cli_aacde99d74f9dbda`。
6. **⚠️ 本地 .env 飞书配置是旧表**（cli_a90edceb0ef99cda / tbl1XIU7FSCvsTLk），所有飞书操作须在 120 生产用生产凭据。
7. **WeCom 后端 `workers=1`**（默认，生产未覆盖）→ 进程内缓存可靠。

## 三、方案（3 层改动）

### Layer 1 — 飞书表：新增附件字段
- 生产表新增字段 **"Bug截图"** `type=17`（附件）。`截图1/2/3` 文本字段保留不动（未用）。
- 一次性脚本（`feishu_bitable` 加 `create_field`，或直接 `POST /bitable/v1/apps/{app_token}/tables/{table_id}/fields` body `{"field_name":"Bug截图","type":17}`）。
- ⚠️ 在 120 执行，用生产凭据；本地 .env 不动。

### Layer 2 — Dify B 工作流：跨轮捕获图片 + 传给 /add
1. **新增会话变量** `cv_image_file_ids`（array[string]，存 Dify `upload_file_id` 列表）。
2. **新增 code 节点 "捕获截图"**（bug 流入口处，每轮执行）：读 `sys.files`，提取 image 类型的 `upload_file_id`，**追加**到 `cv_image_file_ids`（累积多张，去重）。
   - 兜底：若 chatflow code 节点取不到 `sys.files`，改由 WeCom 后端把 `file_image_id` 经 `inputs["input_image_file_id"]` 传入（需 B 开始节点加该输入变量 + `dify._run_chatflow` 加 inputs），code 节点读 input。
3. **改 6260a "N16 组装飞书fields"**：新增入参 `image_file_ids`（来自 cv_image_file_ids）；返回改为
   `{"body_json": json.dumps({"fields": fields, "image_file_ids": ids}, ensure_ascii=False)}`（`image_file_ids` 在 `fields` **外**，顶层）。
4. **写表后复位**：6260c/IDLE reset 节点清空 `cv_image_file_ids`，为下个 bug 复位。

### Layer 3 — WeCom 后端：/add 收 image_file_ids，上传飞书附件
1. **`dify.py` upload_file**：上传 Dify 成功后，顺手缓存 `{upload_file_id: (content_bytes, filename, content_type)}` 到模块级 TTL dict（30min，cap 100）。workers=1 故可靠。
2. **`feishu_bitable.py` 新增 `upload_attachment(content, filename, content_type) -> file_token`**：`POST /drive/v1/medias/upload_all`（multipart，`parent_type=bitable_image`，`parent_node=<app_token>`）→ 返回 `file_token`。
3. **`dify_client.py` 新增 `download_file(file_id, app) -> bytes`**（兜底，缓存 miss 时用）：`GET {api_base}/files/{file_id}/content`，先试 app B token，404/403 回退 app A。
4. **`bugtrack_internal.py`**：
   - `AddRecordRequest` 加 `image_file_ids: List[str] = []`。
   - `/add` 端点：对每个 id → 优先查缓存（miss 走 Dify download 兜底）→ `upload_attachment` 得 `file_token` → 汇总成 `[{"file_token": tok}, ...]` → 放入 `fields["Bug截图"]` → 再 `feishu_add_record(fields)`。
   - 单张失败不阻断写表（记 warning，跳过该图）。

## 四、风险与验证项
- **`sys.files` 在 chatflow code 节点可访问性**：先验；不通走 inputs 兜底。
- **Feishu 附件上传权限**：`bitable:app` 可能不够，或需 `drive:drive:write`；首次调用看 code，缺则后台加 scope。
- **Dify download 兜底**：app token 归属（A/B）+ end_user 所有权；缓存命中是主路径，download 仅 miss 兜底，影响面小。
- **本地 .env 旧表**：飞书操作一律在 120 生产。
- **多张截图**：cv 累积 + 附件字段多 file_token，验证 2~3 张。
- **非图片 bug**：`image_file_ids` 为空，`fields` 不含 "Bug截图"，不报错。

## 五、部署
- **WeCom 后端**：tar+scp 同步 120 → `systemctl restart wecom-api wecom-celery-worker`（无 .env 改动，除非加 scope）。
- **Dify B 工作流**：DB 热补丁改 `workflows.graph`（生产版）或 studio 导入 yml 后发布。
- **飞书表**：120 一次性建 "Bug截图" 附件字段。

## 六、验证清单
- [ ] 飞书表出现 "Bug截图" 附件字段（type=17）
- [ ] 单轮：发图+bug 描述 → 确认 → 飞书记录含内联截图
- [ ] 多张截图累积入同一条记录
- [ ] 跨轮：turn1 发图、turn2 确认，截图仍入表（cv 跨轮生效）
- [ ] 非图片 bug 不报错
- [ ] 缓存 miss 兜底（Dify download）可用
