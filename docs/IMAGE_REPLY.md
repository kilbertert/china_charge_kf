# 图片 / 视频回复全链路

让 H5 智能客服在合适场景下发送图片或视频（如充电桩故障排查视频、操作图示）。

---

## 1. 为什么不能直接把图片放进 Dify 知识库

Dify 知识库（截至 1.14.x）：
- ✅ 允许上传：txt / markdown / pdf / docx / html / csv
- ❌ **不允许** 上传图片、视频作为知识库文档
- ✅ Vision 附件机制：上传图片作为 LLM 输入（仅支持图片，**不支持视频**）

直接把图片放 Dify 文档里，召回时 LLM 拿到的是 **Dify 内部签名 URL**（`/files/<uuid>/file-preview?timestamp=...&nonce=...&sign=...`），前端没有签名密钥，**无法直接加载**。

---

## 2. 解决方案：OSS + 知识库 markdown

```
[运营] → 上传媒体到 OSS（公网 HTTPS URL）
       ↓
[运营] → 在知识库 markdown 文档里写「图片描述 + URL」
       ↓
[Dify RAG] → 向量召回时描述段被命中
       ↓
[LLM]     → 按 JSON 协议输出 {text, media: [{type, url, description}]}
       ↓
[后端]    → JSON 优先 + 正则兜底解析 → ChatResponse.media
       ↓
[前端]    → 渲染 <img> / <video>
```

**核心原则**：**媒体 URL 必须和描述写在同一段**，召回时才会一起命中。

---

## 3. 文件结构

```
kb-assets/
├── MANIFEST.md            # 87 张图的清单（含 oss_url）
├── KB-CHARGE-PILE.md       # 给 Dify 摄入的 markdown 知识库文档
├── DIFY_KB_UPLOAD_GUIDE.md  # 人工在 Dify Studio 上传 KB 的操作指南
├── images/                # 原始 PNG（已重命名 kebab-case）
│   ├── pc-backend-billing-template-domestic-four-wheel-1.png
│   └── ...
└── *.json                 # 提取过程产物（不入知识库）

scripts/
├── upload_kb_images.py    # 批量上传到 OSS
├── build_kb_doc.py        # 生成 KB-CHARGE-PILE.md
└── set_oss_cors.py        # 配置 OSS Bucket CORS
```

---

## 4. OSS 配置

推荐用阿里云 OSS（与本项目同区域 `oss-cn-guangzhou`）。

| 项 | 示例值 |
|---|---|
| Bucket | `trendpower-ai-customer-service` |
| Region | `oss-cn-guangzhou` |
| 公网域名 | `https://trendpower-ai-customer-service.oss-cn-guangzhou.aliyuncs.com` |
| AccessKey | RAM 子账户，只给 `oss:PutObject` + `oss:GetObject` 权限 |

**凭据存放**（**绝不入仓**）：

```bash
mkdir -p .oss-uploader
cat > .oss-uploader/.env <<'EOF'
OSS_AK=LTAIxxxxxxxxxxxxxxx
OSS_SK=xxxxxxxxxxxxxxxxxxxxxxxx
OSS_BUCKET=trendpower-ai-customer-service
OSS_ENDPOINT=https://oss-cn-guangzhou.aliyuncs.com
OSS_PUBLIC_BASE=https://trendpower-ai-customer-service.oss-cn-guangzhou.aliyuncs.com
OSS_KEY_PREFIX=kb/charge-pile
EOF
echo ".oss-uploader/" >> .gitignore
```

---

## 5. CORS 配置

**没有 CORS 规则 H5 加载图片会失败**。

控制台 → Bucket → 数据安全 → 跨域设置 → 创建规则：

| 来源 | 方法 | 允许 Header | 暴露 Header | 缓存时间 |
|---|---|---|---|---|
| `https://zcf.h5.qumall.qushiyun.com` | GET | * | ETag, Content-Length, Content-Type | 3600 |
| `http://localhost:5173`（开发） | GET | * | 同上 | 3600 |

或者用脚本 `scripts/set_oss_cors.py` 一键配。

验证：

```bash
curl -sI -H "Origin: https://zcf.h5.qumall.qushiyun.com" \
  https://trendpower-ai-customer-service.oss-cn-guangzhou.aliyuncs.com/kb/charge-pile/sample.png
# 应该有：Access-Control-Allow-Origin: https://zcf.h5.qumall.qushiyun.com
```

---

## 6. LLM 输出协议

Dify 工作流的 **3 个 LLM 节点** 末尾追加（强约束）：

```
【输出格式·强制】
仅输出 JSON 对象，不要 markdown 围栏，不要任何额外文字：
{
  "text": "<给用户看的文字回答>",
  "media": [
    {"type": "image", "url": "https://...", "description": "可选说明"},
    {"type": "video", "url": "https://...", "description": "可选说明"}
  ]
}
规则：
- URL 必须来自知识库召回结果，禁止编造或拼接。
- 没有相关媒体时 media 为空数组 []。
- text 中不要重复粘贴 media 里的 URL。
- type 只能是 image 或 video，按文件扩展名判断。
```

> ⚠️ 同时必须把原 prompt 里 `不输出 JSON` 那条规则删除（否则 LLM 会反复违反）。

**End 节点**输出变量保持 `output`（值为整段 JSON 字符串），不新增 Dify 输出变量。

---

## 7. 后端解析策略（`backend/app_dify/response_parser.py`）

**两层解析**：

```
1. JSON 优先
   outputs["output"] → json.loads → {text, media}

2. 正则兜底（JSON 失败时）
   text 内扫 https URL → 按扩展名 (.jpg/.mp4 等) 分类
   → 同时从 text 里删除这些 URL，避免前端重复显示

3. 安全过滤（无论哪条路径都走）
   - 仅接受 http(s):// scheme
   - type 必须和扩展名匹配（image 类型必须是图片扩展名）
   - 拒绝 javascript:/data:/vbscript:/file: 等危险 scheme
```

测试覆盖（`backend/app_dify/tests/test_response_parser.py`）：
- JSON 路径（plain / fenced / 带 think 块）
- 正则兜底路径
- 跨扩展名交叉验证（拒绝 .pdf 当 image）
- URL scheme 白名单
- 中文标点 trailing 字符处理
- 36/36 + 3/3 集成测试通过

---

## 8. 前端渲染（`frontend/src/App.tsx`）

```typescript
type MediaItem = { type: 'image' | 'video'; url: string; description?: string }

type ChatMessage = {
  ...
  media?: MediaItem[]   // 后端响应里的 media 数组
}
```

气泡渲染分支：

```tsx
{m.media?.length ? (
  <div className="mediaList">
    {m.media.map((mi, idx) => (
      <div key={idx} className="mediaItem">
        {mi.type === 'image' ? (
          <img className="mediaImage" src={mi.url} alt={mi.description || ''} loading="lazy" />
        ) : (
          <video className="mediaVideo" src={mi.url} controls preload="metadata" playsInline />
        )}
        {mi.description ? <div className="mediaCaption">{mi.description}</div> : null}
      </div>
    ))}
  </div>
) : null}
```

CSS：`frontend/src/App.css`：

```css
.mediaBubble { max-width: 78%; }
.mediaList { display: flex; flex-direction: column; gap: 8px; }
.mediaItem { display: flex; flex-direction: column; gap: 4px; }
.mediaImage, .mediaVideo {
  max-width: 100%;
  max-height: 240px;
  border-radius: 8px;
  border: 0.5px solid rgba(0, 0, 0, 0.1);
}
.mediaVideo { background: #000; }
.mediaCaption { font-size: 12px; color: rgba(0, 0, 0, 0.55); }
```

**安全要点**：
- 不使用 `dangerouslySetInnerHTML`
- `src` 全部走原生 `<img>` / `<video>`，后端已用 scheme 白名单过滤
- `loading="lazy"` 让首屏以外的图片懒加载
- `preload="metadata"` 视频只下载元数据（首帧 + 时长），不下载整段

---

## 9. 知识库运营规范

### 9.1 文档写作规范

```markdown
## 充电桩黑屏排查

如果客户反馈充电桩屏幕黑屏，可以让客户查看以下视频，按步骤排查。

视频：充电桩黑屏排查标准流程
https://oss.example.com/videos/zcf-blackscreen-2026.mp4

涉及步骤：检查电源 → 重启 → 联系运维。
```

**要求**：
- URL 与描述放在**同一段或紧邻段落**
- 描述里要含用户可能的 query 关键词（如「黑屏」「设置电价」「添加角色」）
- 一张图只描述一个核心场景，避免 LLM 召回时混淆

### 9.2 Dify 分段参数

| 项 | 推荐值 | 说明 |
|---|---|---|
| 索引模式 | 高质量 | Embedding + 全文混合 |
| 分段长度 | 1024 tokens | 默认即可 |
| 段落重叠 | 50 tokens | 默认即可 |
| 分段标识符 | `\n\n` | 用 markdown 段落分隔 |
| Q&A 模式 | **关闭** | 我们用的是文档召回，不是问答对 |
| URL 移除 | **关闭** | 必须保留图片 src |

---

## 10. 端到端验证

```bash
# 1. 知识库召回测试（Dify Studio）
#    输入：如何给充电桩设置阶梯电价
#    期望召回段落含 pc-backend-billing-template-domestic-four-wheel-*.png 的描述

# 2. API 端到端测试
curl -X POST http://ai.trendpower.cc/chat/api/chat \
  -F "text=如何给充电桩设置阶梯电价" \
  -F "language=中文" | python -m json.tool

# 期望响应中：
# - assistant_text: 文字回答
# - media: [{type: "image", url: "https://...oss...", description: "..."}]

# 3. 前端验证
# 浏览器硬刷新，问同样问题，助手气泡里应能看到图
```

---

## 11. 已知风险

| 风险 | 兜底 |
|---|---|
| LLM 不守 JSON 协议（输出散文） | 正则兜底路径 + 可加 few-shot example |
| OSS 公网域名跨大陆慢 | 后续挂 CDN（阿里云 CDN / Cloudflare） |
| 视频流量大 | `preload="metadata"` + 移动端按需加载 |
| URL 失效（OSS 文件被删） | 用版本号目录 `kb/charge-pile/v2/...` 平滑迁移 |
| 知识库找不到匹配图 | 在 `KB-CHARGE-PILE.md` 里把图 + 描述写得更长更显眼 |
