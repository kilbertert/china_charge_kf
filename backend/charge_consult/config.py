"""Pydantic Settings — charge_consult 模块配置。

从环境变量 / .env.dify-charge 加载。
"""

from __future__ import annotations

from typing import List

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """配置 — 与 .env.dify-charge 字段严格对齐。"""

    model_config = SettingsConfigDict(
        env_file=".env.dify-charge",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # ── 应用基础 ──
    app_name: str = Field(default="AI Charge Consult", description="服务名")
    app_version: str = Field(default="0.1.0", description="版本号")

    # ── Dify workflow ──
    dify_workflow_id: str = Field(default="", description="Dify workflow_id(China_charge_seriver v2)")
    dify_api_base: str = Field(default="https://api.dify.ai/v1", description="Dify API base URL")
    dify_api_key: str = Field(default="", description="Dify API key, app-xxxxx")
    dify_end_user: str = Field(default="charge-consult-default", description="Dify end_user 标识")
    dify_timeout_seconds: float = Field(default=15.0, description="Dify 调用超时")

    # ── HTTP 服务 ──
    port: int = Field(default=8014, description="FastAPI 监听端口")
    host: str = Field(default="0.0.0.0", description="FastAPI 监听地址")
    cors_origins: str = Field(
        default="http://localhost:5173,http://localhost:8082",
        description="CORS allowed origins,逗号分隔",
    )

    # ── 危险信号 ──
    danger_signal_cache_ttl_seconds: int = Field(default=60, description="危险信号配置缓存 TTL")

    @field_validator("cors_origins")
    @classmethod
    def _strip_cors(cls, v: str) -> str:
        return v.strip()

    @property
    def cors_origins_list(self) -> List[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


settings = Settings()
