import itertools
from datetime import datetime
from typing import Annotated

import nanoid
from pydantic import BaseModel, Field, StringConstraints
from pydantic.functional_validators import AfterValidator

# Must be square
MOOD_GRID: list[list[str]] = [
    ["Enraged", "Shocked", "Annoyed", "Excited", "Proud", "Ecstatic"],
    ["Terrified", "Anxious", "Frustrated", "Energized", "Enthusiastic", "Optimistic"],
    ["Envious", "Nervous", "Uneasy", "Pleased", "Alive", "Accomplished"],
    ["Humiliated", "Disheartened", "Bored", "Calm", "Understood", "Blissful"],
    ["Pessimistic", "Lost", "Fatigued", "Hopeful", "Content", "Moved"],
    ["Miserable", "Helpless", "Glum", "Carefree", "Grateful", "Serene"],
]
MOOD_LIST: list[str] = list(itertools.chain.from_iterable(MOOD_GRID))


def _check_mood(mood: str) -> str:
    if mood not in MOOD_LIST:
        raise ValueError(f"{mood} is not a valid mood")
    return mood


def _get_mood_location(mood: str) -> tuple[float, float]:
    for row_index, row in enumerate(MOOD_GRID):
        for cell_index, cell in enumerate(row):
            if mood == cell:
                return (cell_index, row_index)

    raise ValueError(f"{mood} is not a valid mood")


# See spreadsheet for logic
def get_mood_values(mood: str) -> tuple[float, float]:
    mood_location = _get_mood_location(mood)
    mood_values = (mood_location[0] - 3, -mood_location[1] + 2)
    if mood_values[0] >= 0:
        mood_values = (mood_values[0] + 1, mood_values[1])
    if mood_values[1] >= 0:
        mood_values = (mood_values[0], mood_values[1] + 1)
    return mood_values


class MoodReport(BaseModel):
    zipcode: Annotated[
        str,
        StringConstraints(
            strip_whitespace=True, min_length=5, max_length=5, pattern="^[0-9]{5}$"
        ),
    ]
    mood: Annotated[str, AfterValidator(_check_mood)]


class RedisMoodReport(MoodReport):
    id: Annotated[str, Field(default_factory=nanoid.generate)]
    time: Annotated[datetime, Field(default_factory=datetime.now)]
    host: str
