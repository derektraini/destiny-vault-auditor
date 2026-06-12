from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from .dim_csv import perk_names
from .scoring import Recommendation


STALE_AFTER_DAYS = 540
REFERENCE_DATE = date(2026, 6, 10)


@dataclass(frozen=True)
class WishlistEntry:
    name: str = ""
    item_hash: str = ""
    role: str = ""
    notes: str = ""
    source_name: str = "wishlist"
    author: str = ""
    source_date: str = ""
    confidence: str = "medium"
    contexts: tuple[str, ...] = ()
    recommended_combos: tuple[tuple[str, ...], ...] = ()


@dataclass(frozen=True)
class WishlistMatch:
    entry: WishlistEntry
    strength: str
    matched_combo: tuple[str, ...] = ()

    @property
    def stale(self) -> bool:
        parsed = _parse_date(self.entry.source_date)
        if not parsed:
            return False
        return (REFERENCE_DATE - parsed).days > STALE_AFTER_DAYS

    @property
    def source_label(self) -> str:
        parts = [self.entry.source_name]
        if self.entry.author:
            parts.append(self.entry.author)
        if self.entry.source_date:
            parts.append(self.entry.source_date)
        return " / ".join(parts)


@dataclass(frozen=True)
class WishlistIndex:
    entries: tuple[WishlistEntry, ...] = ()
    source_label: str = "wishlist/triage source"

    def match(self, row: dict[str, str]) -> WishlistMatch | None:
        row_hash = str(row.get("Hash") or "")
        row_name = _normalize(row.get("Name", ""))
        row_perks = set(perk_names(row))
        best: WishlistMatch | None = None

        for entry in self.entries:
            hash_matches = bool(entry.item_hash and entry.item_hash == row_hash)
            name_matches = bool(entry.name and _normalize(entry.name) == row_name)
            if not hash_matches and not name_matches:
                continue

            match = _combo_match(entry, row_perks, hash_matches)
            if not match:
                continue
            if best is None or _strength_score(match) > _strength_score(best):
                best = match

        return best


def load_wishlist(path: Path) -> WishlistIndex:
    if path.suffix.lower() == ".json":
        return _load_json(path)
    if path.suffix.lower() == ".csv":
        return _load_csv(path)
    raise ValueError(f"unsupported wishlist source type: {path.suffix}")


def apply_wishlist_matches(
    items: list[tuple[dict[str, str], Recommendation]],
    wishlist: WishlistIndex | None,
) -> int:
    if not wishlist:
        return 0

    applied = 0
    for row, rec in items:
        if rec.kind != "weapon":
            continue
        match = wishlist.match(row)
        if not match:
            continue
        _apply_match(rec, match)
        applied += 1
    return applied


def _load_json(path: Path) -> WishlistIndex:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, list):
        raw_entries = payload
        source_label = "wishlist/triage JSON"
    else:
        raw_entries = payload.get("entries") or payload.get("recommendations") or payload.get("wishlists") or []
        source_label = payload.get("source_name") or payload.get("source") or "wishlist/triage JSON"

    entries = tuple(_entry_from_mapping(raw) for raw in raw_entries if isinstance(raw, dict))
    return WishlistIndex(entries=entries, source_label=source_label)


def _load_csv(path: Path) -> WishlistIndex:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        entries = tuple(_entry_from_mapping(row) for row in csv.DictReader(handle))
    return WishlistIndex(entries=entries, source_label="wishlist/triage CSV")


def _entry_from_mapping(raw: dict[str, Any]) -> WishlistEntry:
    combos = raw.get("recommended_combos") or raw.get("combos") or raw.get("combo") or raw.get("perks") or ""
    contexts = raw.get("contexts") or raw.get("context") or ()
    return WishlistEntry(
        name=str(raw.get("name") or raw.get("weapon_name") or raw.get("item_name") or ""),
        item_hash=str(raw.get("hash") or raw.get("item_hash") or raw.get("Hash") or ""),
        role=str(raw.get("role") or raw.get("purpose") or raw.get("bucket") or ""),
        notes=str(raw.get("notes") or raw.get("reason") or raw.get("description") or ""),
        source_name=str(raw.get("source_name") or raw.get("source") or "wishlist"),
        author=str(raw.get("author") or ""),
        source_date=str(raw.get("source_date") or raw.get("date") or ""),
        confidence=str(raw.get("confidence") or "medium").lower(),
        contexts=tuple(_split_values(contexts)),
        recommended_combos=tuple(tuple(combo) for combo in _parse_combos(combos)),
    )


def _combo_match(entry: WishlistEntry, row_perks: set[str], hash_matches: bool) -> WishlistMatch | None:
    if not entry.recommended_combos:
        return WishlistMatch(entry=entry, strength="exact" if hash_matches else "partial")

    best_partial: WishlistMatch | None = None
    for combo in entry.recommended_combos:
        combo_set = set(combo)
        if combo_set and combo_set <= row_perks:
            return WishlistMatch(entry=entry, strength="exact", matched_combo=combo)
        if combo_set & row_perks:
            best_partial = WishlistMatch(entry=entry, strength="partial", matched_combo=tuple(sorted(combo_set & row_perks)))
    return best_partial


def _apply_match(rec: Recommendation, match: WishlistMatch) -> None:
    entry = match.entry
    source = match.source_label
    if source not in rec.sources:
        rec.sources.append(source)

    if match.strength == "exact":
        _add_signal(rec, "wishlist-match")
    else:
        _add_signal(rec, "wishlist-partial")
    if match.stale:
        _add_signal(rec, "wishlist-stale")
    if entry.role:
        _add_signal(rec, f"wishlist-role:{_signal_text(entry.role)}")

    role = entry.role or "curated role"
    combo_text = f" ({' + '.join(match.matched_combo)})" if match.matched_combo else ""
    stale_text = "; source is older, so review against current sandbox" if match.stale else ""
    note_text = f": {entry.notes}" if entry.notes else ""

    if match.strength == "exact" and not match.stale:
        if rec.bucket in {"junk", "replace-now", "needs-review"}:
            rec.bucket = "keep"
            rec.tag = "keep"
            rec.rank = "keep"
        rec.confidence = _max_confidence(rec.confidence, entry.confidence)
        rec.reason = _append_reason(rec.reason, f"curated wishlist match for {role}{combo_text}{note_text}")
        return

    if rec.bucket == "junk":
        rec.bucket = "needs-review"
        rec.tag = "archive"
        rec.rank = "review"
    elif rec.bucket == "replace-now":
        rec.bucket = "needs-review"
        rec.tag = "archive"
        rec.rank = "review"
    elif rec.bucket == "keep":
        rec.rank = "keep"
    rec.confidence = "low" if match.stale else _max_confidence(rec.confidence, "medium")
    rec.reason = _append_reason(rec.reason, f"curated wishlist {match.strength} for {role}{combo_text}{stale_text}{note_text}")


def _parse_combos(value: Any) -> list[list[str]]:
    if isinstance(value, list):
        if all(isinstance(item, str) for item in value):
            return [_split_values(value)]
        combos = []
        for item in value:
            if isinstance(item, list):
                combos.append(_split_values(item))
            elif isinstance(item, str):
                combos.append(_split_values(item))
        return [combo for combo in combos if combo]
    if isinstance(value, str):
        return [_split_values(part) for part in value.split(";") if _split_values(part)]
    return []


def _split_values(value: Any) -> list[str]:
    if isinstance(value, (list, tuple)):
        return [str(item).strip() for item in value if str(item).strip()]
    text = str(value or "")
    separators = ["|", ",", "+"]
    for separator in separators:
        text = text.replace(separator, ";")
    return [part.strip() for part in text.split(";") if part.strip()]


def _max_confidence(current: str, candidate: str) -> str:
    order = {"low": 1, "medium": 2, "high": 3}
    return current if order.get(current, 0) >= order.get(candidate, 0) else candidate


def _strength_score(match: WishlistMatch) -> tuple[int, int]:
    return (2 if match.strength == "exact" else 1, len(match.matched_combo))


def _append_reason(reason: str, addition: str) -> str:
    if addition in reason:
        return reason
    return f"{reason}; {addition}" if reason else addition


def _add_signal(rec: Recommendation, signal: str) -> None:
    if signal not in rec.signals:
        rec.signals.append(signal)


def _parse_date(value: str) -> date | None:
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        return None


def _signal_text(value: str) -> str:
    return "-".join(part for part in _normalize(value).split() if part)


def _normalize(value: str) -> str:
    return " ".join((value or "").strip().lower().split())
