from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .armor_analysis import (
    analyze_armor,
    armor_context_reason,
    armor_profile_signals,
    strong_role_fit,
    useful_set_with_weak_stats,
)
from .armor_sets import ArmorSetIndex, normalize_set_name, rating_value
from .destiny_report import DestinyReportIndex, best_replacement_versions, version_label
from .dim_csv import int_field, is_crafted, perk_names


EXACT_COMBOS: tuple[tuple[tuple[str, ...], str], ...] = (
    (("Heal Clip", "Incandescent"), "Heal Clip/Incandescent solar sustain"),
    (("Repulsor Brace", "Destabilizing Rounds"), "Repulsor/Destabilizing Void loop"),
    (("Rimestealer", "Headstone"), "Rimestealer/Headstone Stasis loop"),
    (("Slice", "Hatchling"), "Slice/Hatchling Strand loop"),
    (("Shoot to Loot", "Explosive Payload"), "Shoot to Loot/Explosive utility"),
    (("Shoot to Loot", "Kinetic Tremors"), "Shoot to Loot/Kinetic Tremors utility"),
    (("Kinetic Tremors", "Explosive Payload"), "Kinetic Tremors/Explosive primary utility"),
    (("Zen Moment", "Headseeker"), "Zen Moment/Headseeker PvP consistency"),
    (("Keep Away", "Headseeker"), "Keep Away/Headseeker PvP consistency"),
    (("Lone Wolf", "Headseeker"), "Lone Wolf/Headseeker PvP consistency"),
    (("Slideshot", "Opening Shot"), "Slideshot/Opening Shot PvP roll"),
    (("Snapshot Sights", "Opening Shot"), "Snapshot/Opening Shot PvP special"),
    (("Firmly Planted", "Tap the Trigger"), "Firmly Planted/Tap the Trigger PvP fusion"),
    (("Fourth Time's the Charm", "Firing Line"), "FTTC/Firing Line precision DPS"),
    (("Fourth Time's the Charm", "Precision Instrument"), "FTTC/Precision Instrument DPS"),
    (("Envious Assassin", "Bait and Switch"), "Envious/Bait heavy DPS"),
    (("Envious Arsenal", "Bait and Switch"), "Envious Arsenal/Bait heavy DPS"),
    (("Auto-Loading Holster", "Bait and Switch"), "Auto-Loading/Bait heavy DPS"),
    (("Reconstruction", "Bait and Switch"), "Reconstruction/Bait heavy DPS"),
    (("Reconstruction", "Chill Clip"), "Reconstruction/Chill Clip utility"),
    (("Auto-Loading Holster", "Controlled Burst"), "Auto-Loading/Controlled Burst special DPS"),
    (("Lead from Gold", "Controlled Burst"), "Lead from Gold/Controlled Burst special DPS"),
    (("Disorienting Grenades", "Auto-Loading Holster"), "Disorienting/Auto-Loading utility"),
    (("Disorienting Grenades", "Lead from Gold"), "Disorienting/Lead from Gold utility"),
    (("Relentless Strikes", "Surrounded"), "Relentless/Surrounded sword DPS"),
)

HIGH_VALUE_TERMS = {
    "Incandescent",
    "Voltshot",
    "Jolting Feedback",
    "Destabilizing Rounds",
    "Headstone",
    "Hatchling",
    "Kinetic Tremors",
    "Explosive Payload",
    "One for All",
    "Frenzy",
    "Bait and Switch",
    "Explosive Light",
    "Full Court",
    "Lasting Impression",
    "Reservoir Burst",
    "Controlled Burst",
    "Chill Clip",
    "Cold Steel",
    "Opening Shot",
    "Headseeker",
    "Precision Instrument",
    "Firing Line",
}


@dataclass(frozen=True)
class AuditConfig:
    cleanup_mode: str = "clean-slate"
    high_level_threshold: int = 30
    invested_level_threshold: int = 20
    locked_behavior: str = "review"
    duplicate_pruning: str = "balanced"
    old_vs_new: str = "balanced"
    pvp_caution: str = "balanced"
    notes_behavior: str = "respect"
    low_power_below: int = 0

    @property
    def summary(self) -> dict[str, str | int]:
        return {
            "cleanup_mode": self.cleanup_mode,
            "high_level_threshold": self.high_level_threshold,
            "invested_level_threshold": self.invested_level_threshold,
            "locked_behavior": self.locked_behavior,
            "duplicate_pruning": self.duplicate_pruning,
            "old_vs_new": self.old_vs_new,
            "pvp_caution": self.pvp_caution,
            "notes_behavior": self.notes_behavior,
            "low_power_below": self.low_power_below,
        }

    @property
    def respect_notes(self) -> bool:
        return self.notes_behavior != "ignore"


@dataclass
class Recommendation:
    item_id: str
    item_hash: str
    name: str
    kind: str
    bucket: str
    tag: str
    confidence: str
    reason: str
    sources: list[str] = field(default_factory=list)
    current_tag: str = ""
    rank: str = ""
    signals: list[str] = field(default_factory=list)
    comment_override: str = ""
    duplicate_group: str = ""
    duplicate_group_label: str = ""
    duplicate_size: int = 0
    duplicate_role: str = ""

    @property
    def comment(self) -> str:
        if self.comment_override:
            return self.comment_override
        source_text = f" Sources: {', '.join(self.sources)}." if self.sources else ""
        reason = self.reason.rstrip(".")
        return f"DVA: {self.bucket.upper()} - {reason}.{source_text}"


def recommend(
    row: dict[str, str],
    destiny_report: DestinyReportIndex | None,
    config: AuditConfig | None = None,
) -> Recommendation:
    config = config or AuditConfig()
    row_id = row.get("Id", "")
    row_hash = row.get("Hash", "")
    name = row.get("Name", "")
    current_tag = row.get("Tag") or ""
    level = int_field(row, "Crafted Level")
    tier = int_field(row, "Tier")
    season = int_field(row, "Season")
    power = int_field(row, "Power")
    perks = set(perk_names(row))
    rarity = row.get("Rarity", "")
    notes = (row.get("Notes") or "") if config.respect_notes else ""

    sources = ["DIM CSV"]
    signals = _intent_signals(row, config)

    if level > config.high_level_threshold:
        return _rec(
            item_id=row_id,
            item_hash=row_hash,
            name=name,
            kind="weapon",
            bucket="protect",
            tag=_preserve_tag(current_tag),
            confidence="high",
            reason=f"weapon level {level} is above {config.high_level_threshold}; preserve high-investment gear",
            sources=sources,
            current_tag=current_tag,
            signals=signals,
        )

    if is_crafted(row):
        reason = "crafted/reshapeable weapon preserved"
        if level > config.invested_level_threshold:
            reason = f"crafted weapon level {level}; preserve and move on unless deliberately refarming"
        return _rec(row_id, row_hash, name, "weapon", "protect", _preserve_tag(current_tag), "high", reason, sources, current_tag, signals=signals)

    if rarity == "Exotic":
        return _rec(
            row_id,
            row_hash,
            name,
            "weapon",
            "protect",
            _preserve_tag(current_tag),
            "high",
            "exotic weapon preserved by default",
            sources,
            current_tag,
            signals=signals,
        )

    if _is_locked(row) and config.locked_behavior == "protect":
        return _rec(
            row_id,
            row_hash,
            name,
            "weapon",
            "protect",
            _preserve_tag(current_tag),
            "medium",
            "locked in DIM; protected by audit configuration",
            sources,
            current_tag,
            signals=signals,
        )

    combo_reason = _exact_combo_reason(perks)
    replacement = _replacement_pressure(row, destiny_report) if destiny_report else None
    if replacement:
        sources.append("destiny.report")

    if combo_reason and replacement:
        if config.old_vs_new == "prefer-new" and config.cleanup_mode == "aggressive":
            bucket = "needs-review"
            confidence = "medium"
            reason = f"{combo_reason}; strong roll, but aggressive mode prefers the newer/updated version. Best path: {replacement}"
        else:
            bucket = "keep-refarm"
            confidence = "high"
            reason = f"{combo_reason}; keep until a newer/updated version is earned. Best path: {replacement}"
        return _rec(
            row_id,
            row_hash,
            name,
            "weapon",
            bucket,
            "keep",
            confidence,
            reason,
            sources,
            current_tag,
            signals=signals,
        )

    if combo_reason:
        return _rec(row_id, row_hash, name, "weapon", "keep", "keep", "high", combo_reason, sources, current_tag, signals=signals)

    if "PVP" in notes.upper() and perks & HIGH_VALUE_TERMS:
        reason = "personal PvP note plus useful perk structure; preserve for feel-based testing"
        if replacement:
            reason += f"; newer/updated version exists. Best path: {replacement}"
            return _rec(row_id, row_hash, name, "weapon", "keep-refarm", "keep", "medium", reason, sources, current_tag, signals=signals)
        tag = "keep" if config.pvp_caution != "strict" else "archive"
        return _rec(row_id, row_hash, name, "weapon", "needs-review", tag, "medium", reason, sources, current_tag, signals=signals)

    high_value_hits = sorted(perks & HIGH_VALUE_TERMS)
    if tier >= 5 and len(high_value_hits) >= 2:
        reason = f"Tier 5 roll with multiple useful terms ({', '.join(high_value_hits[:2])})"
        if replacement:
            reason += f"; keep until newer/updated replacement. Best path: {replacement}"
            return _rec(row_id, row_hash, name, "weapon", "keep-refarm", "keep", "medium", reason, sources, current_tag, signals=signals)
        return _rec(row_id, row_hash, name, "weapon", "keep", "keep", "medium", reason, sources, current_tag, signals=signals)

    if _is_locked(row) and config.locked_behavior == "review":
        reason = "locked in DIM but no standout current role found; confirm before changing"
        if replacement:
            reason += f". Newer/updated version exists. Best path: {replacement}"
        return _rec(row_id, row_hash, name, "weapon", "needs-review", _preserve_tag(current_tag), "low", reason, sources, current_tag, signals=signals)

    if replacement:
        tag = "junk"
        bucket = "replace-now"
        confidence = "high"
        if config.cleanup_mode == "gentle" or config.old_vs_new == "keep-bridges":
            tag = "keep"
            bucket = "keep-refarm"
            confidence = "medium"
        reason = "no standout current role; newer/updated version exists"
        if power and config.low_power_below and power <= config.low_power_below:
            reason += f"; power {power} is below low-power review threshold"
        return _rec(
            row_id,
            row_hash,
            name,
            "weapon",
            bucket,
            tag,
            confidence,
            f"{reason}. Best path: {replacement}",
            sources,
            current_tag,
            signals=signals,
        )

    if tier >= 5 and high_value_hits:
        return _rec(
            row_id,
            row_hash,
            name,
            "weapon",
            "needs-review",
            "keep",
            "low",
            f"Tier 5 has one useful term ({high_value_hits[0]}) but needs human review",
            sources,
            current_tag,
            signals=signals,
        )

    if config.cleanup_mode == "gentle" and current_tag in {"favorite", "keep"}:
        return _rec(
            row_id,
            row_hash,
            name,
            "weapon",
            "needs-review",
            current_tag,
            "low",
            "gentle mode preserves existing keep/favorite tag for human review",
            sources,
            current_tag,
            signals=signals,
        )

    reason = "no standout perk combo, tier advantage, investment, or replacement bridge role found"
    if power and config.low_power_below and power <= config.low_power_below:
        reason += f"; power {power} is below low-power review threshold"
    return _rec(
        row_id,
        row_hash,
        name,
        "weapon",
        "junk",
        "junk",
        "medium",
        reason,
        sources,
        current_tag,
        signals=signals,
    )


def recommend_armor(
    row: dict[str, str],
    config: AuditConfig | None = None,
    armor_sets: ArmorSetIndex | None = None,
) -> Recommendation:
    config = config or AuditConfig()
    row_id = row.get("Id", "")
    row_hash = row.get("Hash", "")
    name = row.get("Name", "")
    current_tag = row.get("Tag") or ""
    rarity = row.get("Rarity", "")
    armor_type = row.get("Type", "armor")
    notes = (row.get("Notes") or "") if config.respect_notes else ""
    tier = int_field(row, "Tier")
    power = int_field(row, "Power")
    total = _armor_total(row)
    max_stat = max(_armor_stats(row), default=0)
    two_spikes = sorted(_armor_stats(row), reverse=True)[:2]
    energy_capacity = _first_int(row, ("Energy Capacity", "Energy", "Capacity"))
    masterwork_tier = _first_int(row, ("Masterwork Tier", "Masterwork"))
    sources = ["DIM armor CSV"]
    signals = _intent_signals(row, config)
    armor_profile = analyze_armor(row)
    signals.extend(armor_profile_signals(armor_profile))
    armor_context = armor_context_reason(armor_profile)
    set_rating = _armor_set_rating(row, armor_sets)
    if set_rating:
        sources.append("armor set ratings")
        signals.append(f"set:{set_rating.set_name}")
        signals.append(f"set-rating:{set_rating.best_rating}")
    if total:
        signals.append(f"armor-total:{total}")
    if max_stat:
        signals.append(f"armor-spike:{max_stat}")

    if rarity == "Exotic":
        return _rec(
            row_id,
            row_hash,
            name,
            "armor",
            "protect",
            _preserve_tag(current_tag),
            "high",
            "exotic armor preserved for build coverage",
            sources,
            current_tag,
            signals=signals,
        )

    if _is_locked(row) and config.locked_behavior == "protect":
        return _rec(
            row_id,
            row_hash,
            name,
            "armor",
            "protect",
            _preserve_tag(current_tag),
            "medium",
            "locked armor protected by audit configuration",
            sources,
            current_tag,
            signals=signals,
        )

    if notes and _has_legacy_keep_intent(current_tag) and strong_role_fit(armor_profile):
        reason = "preserved legacy armor note with strong Armor 3.0 stat fit"
        if armor_context:
            reason += f"; {armor_context}"
        if total:
            reason += f"; {total} total"
        signals.append("returning-guardian:auto-preserve-note")
        return _rec(
            row_id,
            row_hash,
            name,
            "armor",
            "protect",
            _preserve_tag(current_tag),
            "medium",
            reason,
            sources,
            current_tag,
            signals=signals,
        )

    if notes:
        return _rec(
            row_id,
            row_hash,
            name,
            "armor",
            "needs-review",
            _preserve_tag(current_tag),
            "medium",
            "armor has a personal note; review before changing",
            sources,
            current_tag,
            signals=signals,
        )

    if energy_capacity >= 10 or masterwork_tier >= 10:
        return _rec(
            row_id,
            row_hash,
            name,
            "armor",
            "protect",
            _preserve_tag(current_tag),
            "medium",
            "masterworked or fully upgraded armor preserved as investment",
            sources,
            current_tag,
            signals=signals,
        )

    if armor_type.lower() == "class item":
        reason = "class item cleanup needs duplicate/build context"
        if set_rating and rating_value(set_rating.best_rating) >= rating_value("B+"):
            reason = f"class item covers useful {set_rating.label}; review duplicate/build context"
        return _rec(
            row_id,
            row_hash,
            name,
            "armor",
            "needs-review",
            _preserve_tag(current_tag),
            "low",
            reason,
            sources,
            current_tag,
            signals=signals,
        )

    if set_rating and rating_value(set_rating.best_rating) >= rating_value("A-"):
        reason = f"high-rated {set_rating.label}"
        if armor_context:
            reason += f"; {armor_context}"
        if total:
            reason += f"; {total} total"
        if useful_set_with_weak_stats(rating_value(set_rating.best_rating), armor_profile):
            reason = f"high-rated {set_rating.label}, but weak stat fit; {armor_context or 'review build fit'}"
            if total:
                reason += f"; {total} total"
            return _rec(row_id, row_hash, name, "armor", "needs-review", "keep", "low", reason, sources, current_tag, signals=signals)
        return _rec(row_id, row_hash, name, "armor", "keep", "keep", "medium", reason, sources, current_tag, signals=signals)

    if set_rating and rating_value(set_rating.best_rating) >= rating_value("B+"):
        reason = f"useful {set_rating.label}; review stat fit"
        if armor_context:
            reason += f"; {armor_context}"
        if total:
            reason += f"; {total} total"
        return _rec(row_id, row_hash, name, "armor", "needs-review", "keep", "low", reason, sources, current_tag, signals=signals)

    if total >= 66 or max_stat >= 27 or (len(two_spikes) == 2 and two_spikes[0] >= 23 and two_spikes[1] >= 20):
        reason = f"strong armor stat profile"
        if armor_context:
            reason += f"; {armor_context}"
        if total:
            reason += f" with {total} total"
        if max_stat:
            reason += f" and {max_stat} peak stat"
        return _rec(row_id, row_hash, name, "armor", "keep", "keep", "medium", reason, sources, current_tag, signals=signals)

    if strong_role_fit(armor_profile):
        reason = f"Armor 3.0 build-role fit; {armor_context}"
        if total:
            reason += f"; {total} total"
        return _rec(row_id, row_hash, name, "armor", "needs-review", "keep", "low", reason, sources, current_tag, signals=signals)

    if tier >= 5:
        reason = "Tier 5 armor without a strong stat read; review for Armor 3.0 role"
        if armor_context:
            reason += f"; {armor_context}"
        return _rec(
            row_id,
            row_hash,
            name,
            "armor",
            "needs-review",
            "keep",
            "low",
            reason,
            sources,
            current_tag,
            signals=signals,
        )

    if _is_locked(row) and config.locked_behavior == "review":
        return _rec(
            row_id,
            row_hash,
            name,
            "armor",
            "needs-review",
            _preserve_tag(current_tag),
            "low",
            "locked armor has no strong stat signal; confirm before changing",
            sources,
            current_tag,
            signals=signals,
        )

    if config.cleanup_mode == "gentle" and current_tag in {"favorite", "keep"}:
        return _rec(
            row_id,
            row_hash,
            name,
            "armor",
            "needs-review",
            current_tag,
            "low",
            "gentle mode preserves existing armor tag for human review",
            sources,
            current_tag,
            signals=signals,
        )

    missing = ["exotic", "lock"]
    if config.respect_notes:
        missing.append("note")
    missing.extend(["investment", "Tier 5", "strong stat profile"])
    reason = f"no {', '.join(missing[:-1])}, or {missing[-1]} found"
    if armor_context:
        reason += f"; {armor_context}"
    if total:
        reason += f"; {total} total"
    if power and config.low_power_below and power <= config.low_power_below:
        reason += f"; power {power} is below low-power review threshold"
    return _rec(row_id, row_hash, name, "armor", "junk", "junk", "medium", reason, sources, current_tag, signals=signals)


def _rec(
    item_id: str,
    item_hash: str,
    name: str,
    kind: str,
    bucket: str,
    tag: str,
    confidence: str,
    reason: str,
    sources: list[str],
    current_tag: str,
    signals: list[str] | None = None,
) -> Recommendation:
    return Recommendation(
        item_id=item_id,
        item_hash=item_hash,
        name=name,
        kind=kind,
        bucket=bucket,
        tag=tag,
        confidence=confidence,
        reason=reason,
        sources=sources,
        current_tag=current_tag,
        rank=_rank_for(bucket, tag),
        signals=signals or [],
    )


def _rank_for(bucket: str, tag: str) -> str:
    if bucket == "protect" or tag == "favorite":
        return "favorite"
    if bucket == "needs-review":
        return "review"
    if tag == "junk":
        return "junk"
    return "keep"


def _preserve_tag(current_tag: str) -> str:
    return current_tag if current_tag in {"favorite", "keep"} else "keep"


def _has_legacy_keep_intent(current_tag: str) -> bool:
    return current_tag in {"favorite", "keep"}


def _is_locked(row: dict[str, str]) -> bool:
    value = (row.get("Locked") or row.get("Lock") or "").strip().lower()
    return value in {"true", "yes", "y", "locked", "1"}


def _intent_signals(row: dict[str, str], config: AuditConfig) -> list[str]:
    signals: list[str] = []
    if _is_locked(row):
        signals.append(f"locked:{config.locked_behavior}")
    current_tag = row.get("Tag") or ""
    if current_tag:
        signals.append(f"current-tag:{current_tag}")
    notes = (row.get("Notes") or "") if config.respect_notes else ""
    if notes:
        signals.append("notes")
    power = int_field(row, "Power")
    if power and config.low_power_below and power <= config.low_power_below:
        signals.append(f"low-power:{power}")
    if (row.get("Holofoil") or "").lower() == "true":
        signals.append("holofoil")
    return signals


def _armor_total(row: dict[str, str]) -> int:
    total = _first_int(row, ("Total", "Base Total", "Stat Total", "Stats Total"))
    if total:
        return total
    stats = _armor_stats(row)
    return sum(stats) if stats else 0


def _armor_stats(row: dict[str, str]) -> list[int]:
    values: list[int] = []
    for stat in ("Mobility", "Resilience", "Recovery", "Discipline", "Intellect", "Strength"):
        value = _first_int(row, (stat, f"Base {stat}", f"{stat} (Base)", f"Stat {stat}"))
        if value:
            values.append(value)
    return values


def _armor_set_rating(row: dict[str, str], armor_sets: ArmorSetIndex | None):
    if not armor_sets:
        return None
    for field in ("Set Name", "Armor Set", "Set", "Set Bonus", "Armor Set Name"):
        value = row.get(field, "")
        if value:
            found = armor_sets.get(normalize_set_name(value))
            if found:
                return found
    return armor_sets.get(normalize_set_name(row.get("Name", "")))


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


def _normalize_field(field: str) -> str:
    return "".join(ch for ch in field.lower() if ch.isalnum())


def _exact_combo_reason(perks: set[str]) -> str:
    for combo, reason in EXACT_COMBOS:
        if all(term in perks for term in combo):
            return reason
    return ""


def _replacement_pressure(
    row: dict[str, str],
    destiny_report: DestinyReportIndex,
) -> str:
    name = row.get("Name", "")
    season = int_field(row, "Season")
    versions = destiny_report.by_name.get(name, [])
    if not versions:
        return ""

    current = destiny_report.by_hash.get(row.get("Hash", ""))
    current_is_modern = bool(
        current
        and (
            current.get("isUpdated")
            or current.get("isTiered")
            or current.get("isCraftable")
            or current.get("isEnhanceable")
        )
    )
    if current_is_modern and int_field(row, "Tier") >= 5:
        return ""

    pressure_versions = [
        weapon
        for weapon in versions
        if (weapon.get("season") or 0) > season
        or weapon.get("isUpdated")
        or weapon.get("isTiered")
        or weapon.get("isCraftable")
    ]
    if not pressure_versions:
        return ""

    return " / ".join(version_label(weapon) for weapon in best_replacement_versions(pressure_versions, season))
