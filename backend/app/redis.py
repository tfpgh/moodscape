from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import redis.asyncio as redis

from app import config


@asynccontextmanager
async def get_redis_client() -> AsyncGenerator[redis.Redis]:
    redis_client = redis.Redis(
        host=config.redis_host,
        port=config.redis_port,
        password=config.redis_password.get_secret_value(),
        decode_responses=True,
    )

    try:
        yield redis_client
    finally:
        await redis_client.aclose()
