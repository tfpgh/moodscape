import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated

import redis.asyncio as redis
from fastapi import Depends, FastAPI, Request
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from app.map_data import generate_map_data_loop
from app.mood import MoodReport, RedisMoodReport
from app.redis import get_redis_client


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    asyncio.create_task(generate_map_data_loop())

    yield


app = FastAPI(lifespan=lifespan)

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


@app.get("/map_data")
async def get_map_data(
    redis_client: Annotated[redis.Redis, Depends(get_redis_client)],
) -> list[RedisMoodReport]:
    reports: list[RedisMoodReport] = []
    for report_bytes in await redis_client.smembers("reports"):  # type: ignore[misc]
        report = RedisMoodReport.model_validate_json(report_bytes)
        reports.append(report)

    return reports


@app.post("/mood_report")
@limiter.limit("100/hour")
async def add_mood_report(
    mood_report: MoodReport,
    redis_client: Annotated[redis.Redis, Depends(get_redis_client)],
    request: Request,
) -> str:
    if request.client is None:
        raise ValueError("request.client is None!")

    redis_mood_report = RedisMoodReport(
        **mood_report.model_dump(), host=request.client.host
    )
    await redis_client.sadd("reports", redis_mood_report.model_dump_json())  # type: ignore[misc]

    return str(redis_mood_report)
