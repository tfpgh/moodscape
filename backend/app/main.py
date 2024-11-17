import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from app.data import (
    MoodReport,
    RedisMoodReport,
    map_data_connection_manager,
    map_update_loop,
)
from app.redis import get_redis_client


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    asyncio.create_task(map_update_loop())

    yield


app = FastAPI(lifespan=lifespan)

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


@app.get("/")
def root() -> str:
    return "Hello, moodscape!"


@app.websocket("/map_data")
async def map_data(
    websocket: WebSocket,
) -> None:
    await map_data_connection_manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        map_data_connection_manager.disconnect(websocket)


@app.post("/mood_report")
@limiter.limit("100/hour")
async def add_mood_report(
    mood_report: MoodReport,
    request: Request,
) -> None:
    async with get_redis_client() as redis_client:
        if request.client is None:
            raise ValueError("request.client is None!")

        redis_mood_report = RedisMoodReport(
            **mood_report.model_dump(), host=request.client.host
        )
        await redis_client.xadd("reports", redis_mood_report.model_dump())  # type: ignore[arg-type]
