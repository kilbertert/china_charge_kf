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
    # Cloud (海外): https://api.dify.ai/v1
    # 阿里云/国服:  https://api.dify.ai/v1  (统一域名,自动路由)
    dify_api_base: str = "https://api.dify.ai/v1"
    dify_api_key: str  # 必填, 形如 app-xxxx
    # Workflow 输入变量名 — 与 Dify 工作流"开始"节点保持一致
    dify_input_text: str = "input_text"
    dify_input_image: str = "input_img_id"
    dify_input_audio: str = "input_audio_id"
    dify_input_language: str = "language"
    # end-user 标识 (Dify 强制要求)
    dify_end_user: str = "h5-frontend-user"
    # 输出变量名 — workflow 结束节点"直接回复"里设置的变量
    dify_output_text: str = "output"
    # 可选: workflow 若把 media 单独输出为一个变量,指明其变量名;目前实现把
    # 整个响应 JSON 解析在 dify_output_text 里,所以此字段留作未来扩展位。
    dify_output_media: str = "media"

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.app_cors_origins.split(",") if o.strip()]


settings = Settings()  # type: ignore[call-arg]
