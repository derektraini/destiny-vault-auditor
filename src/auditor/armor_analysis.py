from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import TYPE_CHECKING

from .armor_sets import ArmorSetIndex, normalize_set_name, rating_value
from .dim_csv import int_field

if TYPE_CHECKING:
    from .scoring import Recommendation


ARMOR_STATS = ("Mobility", "Resilience", "Recovery", "Discipline", "Intellect", "Strength")


@dataclass(frozen=True)
class ArmorProfile:
    armor_class: str = ""
    archetype: str = ""
    role: str = ""
    total: int = 0
    peak_stat: str = ""
    peak_value: int = 0
    stat_fit: str = ""


def analyze_armor(row: dict[str, str]) -> ArmorProfile:
    stats = _stat_values(row)
    total = _armor_total(row, stats)
    peak_stat, peak_value = _peak_stat(stats)
    archetype = _first_text(row, ("Archetype", "Armor Archetype", "Stat Archetype", "Intrinsic", "Armor 3.0 Archetype"))
    role = _role_from_text(archetype) or _role_from_stats(stats)
    return ArmorProfile(
        armor_class=_first_text(row, ("Class", "Equippable", "Owner Class", "Character Class")),
        archetype=archetype,
        role=role,
        total=total,
        peak_stat=peak_stat,
        peak_value=peak_value,
        stat_fit=_stat_fit(total, stats, role),
    )


def apply_armor_context(
    items: list[tuple[dict[str, str], "Recommendation"]],
    armor_sets: ArmorSetIndex | None,
) -> None:
    if not armor_sets:
        return

    groups: dict[tuple[str, str], list[tuple[dict[str, str], Recommendation]]] = defaultdict(list)
    for row, rec in items:
        if rec.kind != "armor":
            continue
        set_name = _set_name(row)
        slot = _clean(row.get("Type", ""))
        if set_name and slot:
            groups[(normalize_set_name(set_name), slot)].append((row, rec))

    for (set_key, _), grouped in groups.items():
        set_rating = armor_sets.get(set_key)
        if not set_rating or rating_value(set_rating.best_rating) < rating_value("B+"):
            continue
        if len(grouped) != 1:
            continue
        _, rec = grouped[0]
        if rec.bucket == "protect":
            continue
        _add_signal(rec, "only-copy-useful-set-slot")
        rec.reason = _append_reason(rec.reason, "only copy of a useful set/slot in this export")
        if rec.bucket == "junk":
            rec.bucket = "needs-review"
            rec.tag = "keep"
            rec.rank = "review"
            rec.confidence = "low"


def armor_context_reason(profile: ArmorProfile) -> str:
    parts: list[str] = []
    if profile.archetype:
        parts.append(f"{profile.archetype} archetype")
    if profile.role:
        parts.append(f"{profile.role} role")
    if profile.stat_fit:
        parts.append(profile.stat_fit)
    if profile.peak_stat and profile.peak_value:
        parts.append(f"{profile.peak_value} {profile.peak_stat}")
    return "; ".join(parts)


def armor_profile_signals(profile: ArmorProfile) -> list[str]:
    signals: list[str] = []
    if profile.armor_class:
        signals.append(f"armor-class:{_signal_text(profile.armor_class)}")
    if profile.archetype:
        signals.append(f"armor-archetype:{_signal_text(profile.archetype)}")
    if profile.role:
        signals.append(f"armor-role:{_signal_text(profile.role)}")
    if profile.stat_fit:
        signals.append(f"stat-fit:{_signal_text(profile.stat_fit)}")
    if profile.peak_stat and profile.peak_value:
        signals.append(f"peak:{_signal_text(profile.peak_stat)}:{profile.peak_value}")
    return signals


def useful_set_with_weak_stats(set_rating_value: int, profile: ArmorProfile) -> bool:
    return set_rating_value >= rating_value("B+") and profile.stat_fit == "weak stat fit"


def strong_role_fit(profile: ArmorProfile) -> bool:
    return profile.stat_fit in {"strong stat fit", "role stat fit"}


def _role_from_text(value: str) -> str:
    text = value.lower()
    if any(term in text for term in ("survival", "tank", "resilience")):
        return "survival"
    if any(term in text for term in ("grenade", "discipline")):
        return "grenade"
    if any(term in text for term in ("melee", "strength")):
        return "melee"
    if any(term in text for term in ("weapon", "handling", "reload")):
        return "weapon-stat"
    if any(term in text for term in ("pvp", "dueling")):
        return "pvp"
    if any(term in text for term in ("raid", "dungeon", "utility", "set")):
        return "raid/dungeon utility"
    return ""


def _role_from_stats(stats: dict[str, int]) -> str:
    if stats.get("Resilience", 0) >= 20 and stats.get("Discipline", 0) >= 20:
        return "survival/grenade"
    if stats.get("Resilience", 0) >= 20:
        return "survival"
    if stats.get("Discipline", 0) >= 20:
        return "grenade"
    if stats.get("Strength", 0) >= 20:
        return "melee"
    if stats.get("Recovery", 0) >= 20 or stats.get("Mobility", 0) >= 20:
        return "pvp"
    return ""


def _stat_fit(total: int, stats: dict[str, int], role: str) -> str:
    peak = max(stats.values(), default=0)
    if total >= 66 or peak >= 27:
        return "strong stat fit"
    if role and any(_role_stat_value(stats, role) >= value for value in (22,)):
        return "role stat fit"
    if total and total < 58 and peak < 20:
        return "weak stat fit"
    return "mixed stat fit"


def _role_stat_value(stats: dict[str, int], role: str) -> int:
    role_stats = {
        "survival": ("Resilience",),
        "grenade": ("Discipline",),
        "melee": ("Strength",),
        "weapon-stat": ("Mobility", "Recovery"),
        "pvp": ("Mobility", "Recovery", "Resilience"),
        "survival/grenade": ("Resilience", "Discipline"),
        "raid/dungeon utility": ("Resilience", "Discipline", "Recovery"),
    }.get(role, ())
    return max((stats.get(stat, 0) for stat in role_stats), default=0)


def _stat_values(row: dict[str, str]) -> dict[str, int]:
    return {stat: _first_int(row, (stat, f"Base {stat}", f"{stat} (Base)", f"Stat {stat}")) for stat in ARMOR_STATS}


def _armor_total(row: dict[str, str], stats: dict[str, int]) -> int:
    total = _first_int(row, ("Total", "Base Total", "Stat Total", "Stats Total"))
    return total or sum(stats.values())


def _peak_stat(stats: dict[str, int]) -> tuple[str, int]:
    if not stats:
        return "", 0
    stat, value = max(stats.items(), key=lambda item: item[1])
    return stat, value


def _set_name(row: dict[str, str]) -> str:
    return _first_text(row, ("Set Name", "Armor Set", "Set", "Armor Set Name"))


def _first_text(row: dict[str, str], fields: tuple[str, ...]) -> str:
    for field in fields:
        value = row.get(field, "")
        if value:
            return value
    return ""


def _first_int(row: dict[str, str], fields: tuple[str, ...]) -> int:
    normalized = {_normalize_field(key): value for key, value in row.items()}
    for field in fields:
        value = int_field(row, field)
        if value:
            return value
        value = normalized.get(_normalize_field(field), "")
        try:
            parsed = int(value)
        except (TypeError, ValueError):
            parsed = 0
        if parsed:
            return parsed
    return 0


def _append_reason(reason: str, addition: str) -> str:
    if addition in reason:
        return reason
    return f"{reason}; {addition}" if reason else addition


def _add_signal(rec: Recommendation, signal: str) -> None:
    if signal not in rec.signals:
        rec.signals.append(signal)


def _signal_text(value: str) -> str:
    return "-".join(part for part in _clean(value).split() if part)


def _clean(value: str) -> str:
    return " ".join((value or "").strip().lower().split())


def _normalize_field(field: str) -> str:
    return "".join(ch for ch in field.lower() if ch.isalnum())
