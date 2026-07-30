from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # ---- App ----
    app_cors_origins: str = "http://localhost:5173"
    port: int = 8012  # default 8012 to avoid collision with coze backend (8011)

    # ---- Dify ----
    # M4 运行态只使用 A=KB 问答；B token 可保留为人工回滚资产。
    dify_api_base: str = "https://api.dify.ai/v1"
    # app A token (必填)。dify_api_key 为旧单 app 兼容回退。
    dify_api_key_a: str = ""
    dify_api_key_b: str = ""  # 旧 app B token，仅回滚时人工使用
    dify_api_key: str = ""  # 旧字段, 仅当 dify_api_key_a 为空时作 A 回退
    # end-user 标识 (Dify 强制要求)。H5 用 session_id 作 end_user 实现按会话隔离;
    # 此字段为健康检查展示与兜底默认值。
    dify_end_user: str = "h5-frontend-user"
    # chatflow user_input_form select 字段透传 (L1 板块路由)。前端发 language ->
    # input_language。留空则不传, Dify 用字段 default。
    dify_chatflow_input_language: str = ""

    # ---- Bug v2 编排服务 ----
    bugtrack_api_base: str = ""
    bugtrack_image_cache_timeout: float = 20.0
    bugtrack_orchestrator_mode: str = "off"
    bugtrack_orchestrator_fallback_to_dify_b: bool = False
    bugtrack_orchestrator_timeout: float = 45.0

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.app_cors_origins.split(",") if o.strip()]

    @property
    def api_key_a(self) -> str:
        """app A 的有效 token (优先 key_a, 回退旧 key)。"""
        return self.dify_api_key_a or self.dify_api_key


settings = Settings()  # type: ignore[call-arg]
