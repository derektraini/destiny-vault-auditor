from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

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
    high_level_threshold: int = 30
    invested_level_threshold: int = 20
    clean_slate: bool = True


@dataclass
class Recommendation:
    item_id: str
    name: str
    bucket: str
    tag: str
    confidence: str
    reason: str
    sources: list[str] = field(default_factory=list)
    current_tag: str = ""

    @property
    def comment(self) -> str:
        source_text = f" Sources: {', '.join(self.sources)}." if self.sources else ""
        return f"DVA: {self.bucket.upper()} - {self.reason}.{source_text}"


def recommend(
    row: dict[str, str],
    destiny_report: DestinyReportIndex | None,
    config: AuditConfig | None = None,
) -> Recommendation:
    config = config or AuditConfig()
    row_id = row.get("Id", "")
    name = row.get("Name", "")
    current_tag = row.get("Tag") or ""
    level = int_field(row, "Crafted Level")
    tier = int_field(row, "Tier")
    season = int_field(row, "Season")
    perks = set(perk_names(row))
    rarity = row.get("Rarity", "")

    sources = ["DIM CSV"]

    if level > config.high_level_threshold:
        return Recommendation(
            item_id=row_id,
            name=name,
            bucket="protect",
            tag=_preserve_tag(current_tag),
            confidence="high",
            reason=f"weapon level {level} is above {config.high_level_threshold}; preserve high-investment gear",
            sources=sources,
            current_tag=current_tag,
        )

    if is_crafted(row):
        reason = "crafted/reshapeable weapon preserved"
        if level > config.invested_level_threshold:
            reason = f"crafted weapon level {level}; preserve and move on unless deliberately refarming"
        return Recommendation(row_id, name, "protect", _preserve_tag(current_tag), "high", reason, sources, current_tag)

    if rarity == "Exotic":
        return Recommendation(
            row_id,
            name,
            "protect",
            _preserve_tag(current_tag),
            "high",
            "exotic weapon preserved by default",
            sources,
            current_tag,
        )

    combo_reason = _exact_combo_reason(perks)
    replacement = _replacement_pressure(row, destiny_report) if destiny_report else None
    if replacement:
        sources.append("destiny.report")

    if combo_reason and replacement:
        return Recommendation(
            row_id,
            name,
            "keep-refarm",
            "keep",
            "high",
            f"{combo_reason}; keep until a newer/updated version is earned. Best path: {replacement}",
            sources,
            current_tag,
        )

    if combo_reason:
        return Recommendation(row_id, name, "keep", "keep", "high", combo_reason, sources, current_tag)

    if "PVP" in (row.get("Notes") or "").upper() and perks & HIGH_VALUE_TERMS:
        reason = "personal PvP note plus useful perk structure; preserve for feel-based testing"
        if replacement:
            reason += f"; newer/updated version exists. Best path: {replacement}"
            return Recommendation(row_id, name, "keep-refarm", "keep", "medium", reason, sources, current_tag)
        return Recommendation(row_id, name, "needs-review", "keep", "medium", reason, sources, current_tag)

    high_value_hits = sorted(perks & HIGH_VALUE_TERMS)
    if tier >= 5 and len(high_value_hits) >= 2:
        reason = f"Tier 5 roll with multiple useful terms ({', '.join(high_value_hits[:2])})"
        if replacement:
            reason += f"; keep until newer/updated replacement. Best path: {replacement}"
            return Recommendation(row_id, name, "keep-refarm", "keep", "medium", reason, sources, current_tag)
        return Recommendation(row_id, name, "keep", "keep", "medium", reason, sources, current_tag)

    if replacement:
        return Recommendation(
            row_id,
            name,
            "replace-now",
            "junk",
            "high",
            f"no standout current role; newer/updated version exists. Best path: {replacement}",
            sources,
            current_tag,
        )

    if tier >= 5 and high_value_hits:
        return Recommendation(
            row_id,
            name,
            "needs-review",
            "keep",
            "low",
            f"Tier 5 has one useful term ({high_value_hits[0]}) but needs human review",
            sources,
            current_tag,
        )

    return Recommendation(
        row_id,
        name,
        "junk",
        "junk",
        "medium",
        "no standout perk combo, tier advantage, investment, or replacement bridge role found",
        sources,
        current_tag,
    )


def _preserve_tag(current_tag: str) -> str:
    return current_tag if current_tag in {"favorite", "keep"} else "keep"


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
