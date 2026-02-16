from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env")

    openai_api_key: str = "not-set"
    openrouter_api_key: str = "not-set"
    llm_model: str = "google/gemini-2.5-flash"
    host: str = "0.0.0.0"
    port: int = 8000


settings = Settings()
