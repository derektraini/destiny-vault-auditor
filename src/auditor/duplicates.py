from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from .dim_csv import int_field, is_crafted
from .scoring import AuditConfig, Recommendation


@dataclass(frozen=True)
class DuplicateSummary:
    groups: int = 0
    items: int = 0
    weapon_groups: int = 0
    armor_groups: int = 0


@dataclass
class DuplicateCandidate:
    key: tuple[str, ...]
    label: str
    row: dict[str, str]
    rec: Recommendation


def apply_duplicate_grouping(
    items: list[tuple[dict[str, str], Recommendation]],
    config: AuditConfig,
) -> DuplicateSummary:
    groups: dict[tuple[str, ...], list[DuplicateCandidate]] = defaultdict(list)
    for row, rec in items:
        candidate = _candidate(row, rec)
        if candidate:
            groups[candidate.key].append(candidate)

    duplicate_groups = [(key, candidates) for key, candidates in sorted(groups.items()) if len(candidates) > 1]
    for index, (_, candidates) in enumerate(duplicate_groups, start=1):
        _apply_group(f"duplicate-{index}", candidates, config)

    return DuplicateSummary(
        groups=len(duplicate_groups),
        items=sum(len(candidates) for _, candidates in duplicate_groups),
        weapon_groups=sum(1 for key, _ in duplicate_groups if key[0] == "weapon"),
        armor_groups=sum(1 for key, _ in duplicate_groups if key[0] == "armor"),
    )


def _candidate(row: dict[str, str], rec: Recommendation) -> DuplicateCandidate | None:
    if rec.kind == "weapon":
        name = _clean(row.get("Name", ""))
        weapon_type = _clean(row.get("Type", ""))
        if not name:
            return None
        label = row.get("Name", "")
        if row.get("Type"):
            label = f"{label} ({row['Type']})"
        return DuplicateCandidate(("weapon", name, weapon_type), label, row, rec)

    if rec.kind == "armor":
        slot = _clean(row.get("Type", ""))
        set_name = _clean(_first_text(row, ("Set Name", "Armor Set", "Set", "Armor Set Name")))
        rarity = _clean(row.get("Rarity", ""))
        shape = _armor_shape(row)
        if not slot or not set_name:
            return None
        label = f"{row.get('Set Name') or row.get('Name', 'Armor')} {row.get('Type', 'Armor')}"
        return DuplicateCandidate(("armor", slot, set_name, rarity, shape), label, row, rec)

    return None


def _apply_group(group_id: str, candidates: list[DuplicateCandidate], config: AuditConfig) -> None:
    ranked = sorted(candidates, key=lambda candidate: _score_candidate(candidate, config), reverse=True)
    best = ranked[0]
    label = best.label
    size = len(candidates)

    for position, candidate in enumerate(ranked, start=1):
        rec = candidate.rec
        rec.duplicate_group = group_id
        rec.duplicate_group_label = label
        rec.duplicate_size = size
        rec.duplicate_role = "best" if position == 1 else "copy"
        _add_signal(rec, f"duplicate-group:{group_id}")
        _add_signal(rec, "duplicate-best" if position == 1 else "duplicate-copy")

    best.rec.reason = _append_reason(
        best.rec.reason,
        f"best current copy in duplicate group of {size}; review weaker copies first",
    )
    if all(candidate.rec.tag == "junk" for candidate in ranked):
        best.rec.bucket = "needs-review"
        best.rec.tag = "archive"
        best.rec.confidence = "low"
        best.rec.rank = "review"
        best.rec.reason = _append_reason(best.rec.reason, "kept as the visible non-junk copy for this duplicate group")

    for candidate in ranked[1:]:
        rec = candidate.rec
        if _has_protective_intent(candidate.row, rec, config):
            rec.reason = _append_reason(rec.reason, f"duplicate copy in group of {size}, but preserved by investment or user intent")
            continue

        if config.duplicate_pruning == "keep-more":
            rec.reason = _append_reason(rec.reason, f"duplicate copy in group of {size}; keep-more mode leaves final call to review")
            continue

        if config.duplicate_pruning == "prune-hard":
            rec.bucket = "junk"
            rec.tag = "junk"
            rec.confidence = "medium"
            rec.rank = "junk"
            rec.reason = _append_reason(rec.reason, f"weaker duplicate copy in group of {size}; best copy is {best.rec.name}")
            continue

        if rec.bucket == "keep":
            rec.bucket = "needs-review"
            rec.tag = "archive"
            rec.confidence = "medium"
            rec.rank = "review"
            rec.reason = _append_reason(rec.reason, f"weaker duplicate copy in group of {size}; archive unless this exact roll has a role")
        else:
            rec.reason = _append_reason(rec.reason, f"duplicate copy in group of {size}; best copy is {best.rec.name}")


def _score_candidate(candidate: DuplicateCandidate, config: AuditConfig) -> int:
    rec = candidate.rec
    row = candidate.row
    score = {
        "protect": 100,
        "keep": 75,
        "keep-refarm": 70,
        "needs-review": 45,
        "replace-now": 25,
        "junk": 0,
    }.get(rec.bucket, 0)
    score += {"favorite": 20, "keep": 10, "archive": 3, "junk": 0}.get(rec.tag, 0)
    score += {"high": 8, "medium": 4, "low": 1}.get(rec.confidence, 0)
    score += min(int_field(row, "Tier"), 5) * 3
    score += min(int_field(row, "Crafted Level"), 50)
    if is_crafted(row):
        score += 35
    if _is_locked(row):
        score += 25
    if config.respect_notes and row.get("Notes"):
        score += 15
    if rec.kind == "armor":
        total = _first_int(row, ("Total", "Base Total", "Stat Total", "Stats Total"))
        score += min(total, 70)
        score += _set_rating_score(rec)
    return score


def _has_protective_intent(row: dict[str, str], rec: Recommendation, config: AuditConfig) -> bool:
    if rec.bucket == "protect" or rec.tag == "favorite":
        return True
    if is_crafted(row) or int_field(row, "Crafted Level") > config.invested_level_threshold:
        return True
    if _is_locked(row) or (config.respect_notes and row.get("Notes")):
        return True
    if row.get("Rarity") == "Exotic":
        return True
    return False


def _armor_shape(row: dict[str, str]) -> str:
    stats = []
    for stat in ("Mobility", "Resilience", "Recovery", "Discipline", "Intellect", "Strength"):
        value = _first_int(row, (stat, f"Base {stat}", f"{stat} (Base)", f"Stat {stat}"))
        if value >= 20:
            stats.append(stat.lower())
    return "+".join(stats[:2]) if stats else "flat"


def _set_rating_score(rec: Recommendation) -> int:
    for signal in rec.signals:
        if not signal.startswith("set-rating:"):
            continue
        rating = signal.removeprefix("set-rating:")
        return {"S": 30, "A+": 26, "A": 24, "A-": 22, "B+": 18, "B": 15, "C": 8}.get(rating, 0)
    return 0


def _append_reason(reason: str, addition: str) -> str:
    if addition in reason:
        return reason
    return f"{reason}; {addition}" if reason else addition


def _add_signal(rec: Recommendation, signal: str) -> None:
    if signal not in rec.signals:
        rec.signals.append(signal)


def _first_text(row: dict[str, str], fields: tuple[str, ...]) -> str:
    for field in fields:
        value = row.get(field, "")
        if value:
            return value
    return ""


def _first_int(row: dict[str, str], fields: tuple[str, ...]) -> int:
    for field in fields:
        value = int_field(row, field)
        if value:
            return value
    return 0


def _is_locked(row: dict[str, str]) -> bool:
    value = (row.get("Locked") or row.get("Lock") or "").strip().lower()
    return value in {"true", "yes", "y", "locked", "1"}


def _clean(value: str) -> str:
    return " ".join((value or "").strip().lower().split())
