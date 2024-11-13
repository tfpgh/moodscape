from pydantic import SecretStr
from pydantic_settings import BaseSettings


class Config(BaseSettings):
    redis_host: str
    redis_port: int
    redis_password: SecretStr


config = Config(_env_file=".env", _env_file_encoding="utf-8")  # type: ignore[call-arg]
