from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ArmorSetRating:
    set_name: str
    two_piece_name: str
    two_piece_rating: str
    four_piece_name: str
    four_piece_rating: str
    source: str
    source_type: str

    @property
    def best_rating(self) -> str:
        return best_rating(self.two_piece_rating, self.four_piece_rating)

    @property
    def label(self) -> str:
        return f"{self.set_name} set bonus ({self.two_piece_rating}/{self.four_piece_rating})"


ArmorSetIndex = dict[str, ArmorSetRating]


RATING_ORDER = {
    "S": 7,
    "A+": 6,
    "A": 5,
    "A-": 4,
    "B+": 3,
    "B": 2,
    "B-": 1,
    "PVP": 3,
}


def load_armor_set_ratings(path: Path) -> ArmorSetIndex:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.reader(handle)
        rows = list(reader)

    index: ArmorSetIndex = {}
    for row in rows:
        if len(row) < 7:
            continue
        set_name = row[0].strip()
        if not set_name or set_name in {"Set Pick List", "Set Name"}:
            continue
        if set_name.startswith("Spreadsheet Credit") or set_name.startswith("NOTE:"):
            continue

        rating = ArmorSetRating(
            set_name=set_name,
            two_piece_name=_cell(row, 1),
            two_piece_rating=_cell(row, 3),
            four_piece_name=_cell(row, 4),
            four_piece_rating=_cell(row, 6),
            source=_cell(row, 7),
            source_type=_cell(row, 8),
        )
        index[normalize_set_name(set_name)] = rating
    return index


def normalize_set_name(value: str) -> str:
    return "".join(ch for ch in value.lower() if ch.isalnum())


def best_rating(*ratings: str) -> str:
    cleaned = [rating.strip().upper().replace("?", "") for rating in ratings if rating.strip()]
    if not cleaned:
        return ""
    return max(cleaned, key=lambda rating: RATING_ORDER.get(rating, 0))


def rating_value(rating: str) -> int:
    return RATING_ORDER.get(rating.strip().upper().replace("?", ""), 0)


def _cell(row: list[str], index: int) -> str:
    return row[index].strip() if index < len(row) else ""
