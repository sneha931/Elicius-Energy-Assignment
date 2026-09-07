from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "AI Q&A Platform"
    app_env: str = "development"

    database_url: str
    redis_url: str

    jwt_secret: str
    jwt_algorithm: str = "HS256"

    llm_api_key: str
    llm_model: str
    llm_fallback_model: str
    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=False,
        extra="ignore",
    )


settings = Settings()