import asyncio

from app.mood import RedisMoodReport
from app.redis import get_redis_client


async def generate_map_data_loop() -> None:
    redis_client = await get_redis_client().__anext__()
    while True:
        reports: list[RedisMoodReport] = []
        for report_bytes in await redis_client.smembers("reports"):  # type: ignore[misc]
            report = RedisMoodReport.model_validate_json(report_bytes)
            reports.append(report)
        print(reports)

        await asyncio.sleep(60)
