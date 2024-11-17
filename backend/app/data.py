import asyncio
import itertools
import time
from datetime import UTC, datetime
from typing import Annotated, Literal, NoReturn

from fastapi import WebSocket
from pydantic import BaseModel, Field, StringConstraints, field_serializer
from pydantic.functional_validators import AfterValidator

from app.redis import get_redis_client
from app.zip_codes import STATE_LIST, ZIP_CODE_MAPPING

LOOP_SLEEP_TIME = 2  # In seconds
EXPIRED_LIST_EXPIRY_CYCLE_LENGTH = (
    10  # Number of main loop cycles to leave expired values in the cache
)

EXPIRY_OFFSET = 60 * 60 * 24  # Number of seconds a report stays valid

# Must be square and have an even size (4, 6, 8, etc.)
MOOD_GRID: list[list[str]] = [
    ["Enraged", "Shocked", "Annoyed", "Excited", "Proud", "Ecstatic"],
    ["Terrified", "Anxious", "Frustrated", "Energized", "Enthusiastic", "Optimistic"],
    ["Envious", "Nervous", "Uneasy", "Pleased", "Alive", "Blissful"],
    ["Humiliated", "Disheartened", "Bored", "Calm", "Understood", "Accomplished"],
    ["Pessimistic", "Lost", "Fatigued", "Hopeful", "Content", "Moved"],
    ["Miserable", "Helpless", "Glum", "Carefree", "Grateful", "Serene"],
]
MOOD_LIST: list[str] = list(itertools.chain.from_iterable(MOOD_GRID))

MOOD_QUADRANTS: dict[str, Literal[0, 1, 2, 3]] = {}
for row_index, row in enumerate(MOOD_GRID):
    for col_index, mood in enumerate(row):
        if row_index < (len(MOOD_GRID) / 2) and col_index >= (len(MOOD_GRID) / 2):
            MOOD_QUADRANTS[mood] = 0
        elif row_index < (len(MOOD_GRID) / 2) and col_index < (len(MOOD_GRID) / 2):
            MOOD_QUADRANTS[mood] = 1
        elif row_index >= (len(MOOD_GRID) / 2) and col_index < (len(MOOD_GRID) / 2):
            MOOD_QUADRANTS[mood] = 2
        else:
            MOOD_QUADRANTS[mood] = 3


def _check_mood(mood: str) -> str:
    if mood not in MOOD_LIST:
        raise ValueError(f"{mood} is not a valid mood")
    return mood


class MoodReport(BaseModel):
    zip_code: Annotated[
        str,
        StringConstraints(
            strip_whitespace=True, min_length=5, max_length=5, pattern="^[0-9]{5}$"
        ),
    ]
    mood: Annotated[str, AfterValidator(_check_mood)]


class RedisMoodReport(MoodReport):
    time: Annotated[datetime, Field(default_factory=lambda: datetime.now(UTC))]
    host: str

    @field_serializer("time")
    def serialize_time(self, time: datetime) -> str:
        return time.isoformat()


class StateData(BaseModel):
    quadrent_counts: list[int] = [0, 0, 0, 0]
    color: str = "#DBDBDB"


class MapData(BaseModel):
    states: dict[str, StateData] = Field(
        default_factory=lambda: {state: StateData() for state in STATE_LIST}
    )


current_map_data = MapData()


class MapDataConnectionManager:
    def __init__(self) -> None:
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self.active_connections.append(websocket)

        await websocket.send_text(current_map_data.model_dump_json())

    def disconnect(self, websocket: WebSocket) -> None:
        self.active_connections.remove(websocket)

    async def broadcast_map_data(self) -> None:
        for connection in self.active_connections:
            await connection.send_text(current_map_data.model_dump_json())


map_data_connection_manager = MapDataConnectionManager()

expired_ids: list[list[str]] = []


def update_map(
    new_reports: dict[str, RedisMoodReport], expired_reports: dict[str, RedisMoodReport]
) -> None:
    global current_map_data

    new_expired_ids: list[str] = []

    if len(expired_ids) > EXPIRED_LIST_EXPIRY_CYCLE_LENGTH:
        expired_ids.pop(0)

    flattened_expired_ids = list(itertools.chain.from_iterable(expired_ids))

    updated_map_data = current_map_data.model_copy(deep=True)
    for report in new_reports.values():
        updated_map_data.states[ZIP_CODE_MAPPING[report.zip_code]].quadrent_counts[
            MOOD_QUADRANTS[report.mood]
        ] += 1

    for id, report in expired_reports.items():
        # Trim takes a little while
        # We need to check to make sure reports aren't double expired
        if id not in flattened_expired_ids:
            updated_map_data.states[ZIP_CODE_MAPPING[report.zip_code]].quadrent_counts[
                MOOD_QUADRANTS[report.mood]
            ] -= 1
        new_expired_ids.append(id)

    current_map_data = updated_map_data

    expired_ids.append(new_expired_ids)


async def map_update_loop() -> NoReturn:
    last_id = "-"
    async with get_redis_client() as redis_client:
        while True:
            # Get new reports
            raw_new_reports = list(
                await redis_client.xrange("reports", min=last_id, max="+")
            )

            new_reports: dict[str, RedisMoodReport] = {}

            if (last_id == "-" and len(raw_new_reports) > 0) or (
                last_id != "-" and len(raw_new_reports) > 1
            ):
                if last_id != "-":
                    raw_new_reports.pop(0)

                last_id = raw_new_reports[-1][0]

                new_reports = {
                    key: RedisMoodReport.model_validate(data)
                    for key, data in raw_new_reports
                }

            # Get expired reports
            expiry_id = str(int((time.time() - EXPIRY_OFFSET) * 1000))
            raw_expired_reports = list(
                await redis_client.xrange("reports", min="-", max=expiry_id)
            )

            expired_reports: dict[str, RedisMoodReport] = {
                key: RedisMoodReport.model_validate(data)
                for key, data in raw_expired_reports
            }

            update_map(new_reports, expired_reports)

            await redis_client.xtrim("reports", minid=expiry_id)

            await map_data_connection_manager.broadcast_map_data()
            await asyncio.sleep(LOOP_SLEEP_TIME)
