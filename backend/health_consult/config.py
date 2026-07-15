"""Pydantic Settings — health_consult 模块。

读取 `.env.dify-consult` 文件,所有变量可通过环境变量覆盖。
"""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env.dify-consult",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # ---- Dify ----
    dify_api_base: str = "https://api.dify.ai/v1"
    dify_api_key: str = ""  # required in production
    dify_workflow_id: str = "AI_health_consultant_v2"
    # Dify workflow 输入变量名(与工作流"开始"节点对齐)
    dify_input_text: str = "input_text"
    dify_input_image: str = "input_img_id"
    dify_input_answers: str = "input_answers"
    dify_input_language: str = "input_language"
    dify_input_session_id: str = "input_session_id"
    dify_output_text: str = "output"
    dify_end_user: str = "h5-health-consult"
    # Knowledge base dataset ids(可选)
    dify_dataset_product: str = ""
    dify_dataset_questionnaire: str = ""
    dify_dataset_solution: str = ""

    # ---- App ----
    app_name: str = "health-consult"
    app_version: str = "0.1.0"
    app_cors_origins: str = "http://localhost:5173,http://localhost:8082"
    port: int = 8013

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.app_cors_origins.split(",") if o.strip()]


settings = Settings()  # type: ignore[call-arg]
