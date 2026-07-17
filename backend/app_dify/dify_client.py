from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Optional

import httpx


class DifyError(RuntimeError):
    """Raised for any Dify API failure (HTTP error or workflow-level failure)."""


# ----------------------------------------------------------------------
# 双 app 路由握手标记 - 与 WeCom 机器人 (wecom-ai-customer-service) 对齐。
# Chatflow app A/B 在回复里嵌入 HTML 注释标记驱动后端改投, 用户不可见。
# ----------------------------------------------------------------------
SWITCH_TO_BUG = "SWITCH_TO_BUG"                # A->B: A 检测 bug 意图, 改投 B (同条消息)
SWITCH_TO_KB_REENTRY = "SWITCH_TO_KB_REENTRY"  # B->A: B 判定非 bug/修改窗 NEW, 改投 A (同条消息)
SWITCH_TO_KB_DONE = "SWITCH_TO_KB_DONE"        # B->A: B 结束(放弃/无差异), 发 B 话术, 下条->A

# 匹配 <!--SYS:SWITCH_TO_XXX--> 握手标记
_SWITCH_MARKER_RE = re.compile(r"<!--SYS:(SWITCH_TO_[A-Z_]+)-->")


def parse_switch_markers(text: str) -> tuple[str, set]:
    """剥离并返回 SWITCH 路由标记。

    Returns:
        (剥离标记后的文本, {标记名集合})
        标记名 ∈ {SWITCH_TO_BUG, SWITCH_TO_KB_REENTRY, SWITCH_TO_KB_DONE}
    """
    if not text:
        return text or "", set()
    found = {m.group(1) for m in _SWITCH_MARKER_RE.finditer(text)}
    stripped = _SWITCH_MARKER_RE.sub("", text)
    return stripped, found


# 匹配所有 <!--SYS:...--> 控制注释 (SWITCH / TIMER / 未来扩展)。
# H5 不作用于这些协议标记(TIMER 的二阶段超时是 WeCom 专属), 统一从用户可见文本剥离。
_SYS_MARKER_RE = re.compile(r"<!--SYS:.*?-->", re.DOTALL)


def strip_sys_markers(text: str) -> str:
    """剥离所有 <!--SYS:...--> 控制标记, 返回干净的用户可见文本。"""
    if not text:
        return text or ""
    return _SYS_MARKER_RE.sub("", text).strip()


@dataclass(frozen=True)
class DifyClient:
    """Dify Chatflow (advanced-chat) app 客户端。

    一个实例绑定一个 app token (A 或 B)。跨 app 改投由上层 ChatflowRouter
    切换两个 client 实现, 不在此处处理。
    """

    api_base: str  # e.g. https://api.dify.ai/v1 或 http://api:5001/v1
    api_key: str  # app-xxx
    end_user: str  # Dify 每次调用强制要求 user 标识 (H5 用 session_id)
    app_mode: str = "chatflow"  # 固定 chatflow; 保留字段以便将来扩展 workflow

    def _headers(self, *, content_type: Optional[str] = None) -> dict[str, str]:
        h = {"Authorization": f"Bearer {self.api_key}"}
        if content_type:
            h["Content-Type"] = content_type
        return h

    # ------------------------------------------------------------------
    # 1. File upload
    # ------------------------------------------------------------------
    async def upload_file(
        self,
        *,
        filename: str,
        content: bytes,
        content_type: str | None,
    ) -> str:
        """上传文件到【本 client 绑定的 app】。

        Endpoint:  POST {api_base}/files/upload
        Form:      file (binary), user (string)
        Response:  201 { id, name, mime_type, ... }

        关键: Dify 文件库按 app 隔离, 必须在发送时(目标 app 已知)上传, 才能
        保证跨 app 改投(A->B)时文件归属正确, 根除 "A 的 file_id 发给 B 报
        Invalid upload file"。因此上传动作放在 ChatflowRouter 发送点调用本方法,
        而非入口处统一上传。
        """
        url = f"{self.api_base.rstrip('/')}/files/upload"
        files = {"file": (filename, content, content_type or "application/octet-stream")}
        data = {"user": self.end_user}

        async with httpx.AsyncClient(timeout=httpx.Timeout(60.0), verify=False) as client:
            resp = await client.post(url, headers=self._headers(), files=files, data=data)

        if resp.status_code >= 400:
            raise DifyError(f"Dify upload failed: HTTP {resp.status_code} {resp.text}")

        body = resp.json()
        file_id = body.get("id")
        if not file_id:
            raise DifyError(f"Dify upload returned no id: {body}")
        return str(file_id)

    # ------------------------------------------------------------------
    # 2. Chatflow execution
    # ------------------------------------------------------------------
    async def run_chatflow(
        self,
        *,
        query: str,
        inputs: dict[str, Any] | None = None,
        files: list[dict[str, Any]] | None = None,
        response_mode: str = "blocking",
        conversation_id: str = "",
    ) -> dict[str, Any]:
        """运行 Chatflow (advanced-chat) app。

        Endpoint:  POST {api_base}/chat-messages
        Body:      { query, inputs, files, response_mode, conversation_id, user }
        Response:  blocking -> JSON { answer, conversation_id, message_id,
                                      metadata: { retriever_resources, usage, ... } }

        与已废弃的 workflow /workflows/run 的关键差异:
            - 用户文本走 ``query`` (顶层), 不放 inputs
            - 文件走顶层 ``files`` 数组, 不放 inputs[<file_var>]
            - 响应扁平: ``answer`` + ``metadata.retriever_resources``,
              没有 ``data.outputs`` 嵌套 (由上层 ChatflowRouter 归一化)
            - 多轮: 传 conversation_id 续接, 首次传 "" 新建

        IMPORTANT: HTTP 200 即成功 (chatflow blocking 无 data.status 字段);
        业务级失败(如模型报错)会以非 200 返回, 由下方 HTTP 检查捕获。
        """
        url = f"{self.api_base.rstrip('/')}/chat-messages"
        payload: dict[str, Any] = {
            "inputs": inputs or {},
            "query": query,
            "response_mode": response_mode,
            "conversation_id": conversation_id or "",
            "user": self.end_user,
        }
        if files:
            payload["files"] = files

        async with httpx.AsyncClient(timeout=httpx.Timeout(120.0), verify=False) as client:
            resp = await client.post(
                url,
                headers=self._headers(content_type="application/json"),
                json=payload,
            )

        if resp.status_code >= 400:
            raise DifyError(f"Dify chatflow HTTP error: {resp.status_code} {resp.text}")

        return resp.json()

    # ------------------------------------------------------------------
    # 3. Workflow execution (并列后端 health_consult / charge_consult 用)
    # ------------------------------------------------------------------
    async def run_workflow(
        self,
        *,
        inputs: dict[str, Any] | None = None,
        response_mode: str = "blocking",
    ) -> dict[str, Any]:
        """运行 Workflow app(非 chatflow)。

        供 health_consult / charge_consult 等仍使用 workflow 类型 Dify app 的并列
        后端调用。H5 主链路用 run_chatflow, 本方法为向后兼容保留(不强行把并列
        后端迁 chatflow, 因其 Dify app 仍是 workflow 类型)。

        Endpoint:  POST {api_base}/workflows/run
        Body:      { inputs, response_mode, user }
        Response:  blocking -> { task_id, workflow_run_id,
                    data: { id, workflow_id, status, outputs, error } }

        与 chatflow 差异: 无 query/conversation_id; 用户文本与文件均放 inputs;
        响应嵌套在 data.outputs (由各 dify_proxy.parse_dify_output 归一化)。
        """
        url = f"{self.api_base.rstrip('/')}/workflows/run"
        payload: dict[str, Any] = {
            "inputs": inputs or {},
            "response_mode": response_mode,
            "user": self.end_user,
        }
        async with httpx.AsyncClient(timeout=httpx.Timeout(120.0), verify=False) as client:
            resp = await client.post(
                url,
                headers=self._headers(content_type="application/json"),
                json=payload,
            )

        if resp.status_code >= 400:
            raise DifyError(f"Dify workflow HTTP error: {resp.status_code} {resp.text}")

        return resp.json()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    @staticmethod
    def file_ref(upload_file_id: str, file_type: str) -> dict[str, Any]:
        """构造 chatflow files 数组里的文件对象。

        file_type: 'image' | 'audio' | 'document' | 'video'
        """
        return {
            "type": file_type,
            "transfer_method": "local_file",
            "upload_file_id": upload_file_id,
        }

    def dump_for_debug(self, body: dict[str, Any]) -> str:
        try:
            return json.dumps(body, ensure_ascii=False, indent=2)[:2000]
        except Exception:
            return str(body)[:2000]
