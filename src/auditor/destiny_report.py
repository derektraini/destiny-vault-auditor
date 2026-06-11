from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class DestinyReportIndex:
    manifest_version: str
    generated_at: str
    by_hash: dict[str, dict[str, Any]]
    by_name: dict[str, list[dict[str, Any]]]


def load_destiny_report(path: Path) -> DestinyReportIndex:
    data = json.loads(path.read_text(encoding="utf-8"))
    weapons = list(data.get("weapons", {}).values())
    by_hash = {str(weapon["hash"]): weapon for weapon in weapons}
    by_name: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for weapon in weapons:
        by_name[weapon.get("name", "")].append(weapon)

    for versions in by_name.values():
        versions.sort(key=lambda item: ((item.get("season") or 0), item.get("hash") or 0))

    return DestinyReportIndex(
        manifest_version=data.get("manifestVersion", "unknown"),
        generated_at=data.get("generatedAt", "unknown"),
        by_hash=by_hash,
        by_name=dict(by_name),
    )


def source_text(weapon: dict[str, Any]) -> str:
    source = weapon.get("sourceString") or ""
    if source:
        return source
    source_list = weapon.get("source") or []
    return ", ".join(source_list) if source_list else "source not listed"


def version_label(weapon: dict[str, Any]) -> str:
    flags = []
    if weapon.get("isUpdated"):
        flags.append("updated")
    if weapon.get("isTiered"):
        flags.append("tiered")
    if weapon.get("isCraftable"):
        flags.append("craftable")
    if weapon.get("isEnhanceable"):
        flags.append("enhanceable")
    if weapon.get("isAdept"):
        flags.append("adept")
    flag_text = ", ".join(flags) if flags else "legacy"
    return f"S{weapon.get('season', '?')} {flag_text}; {source_text(weapon)}"


def best_replacement_versions(
    versions: list[dict[str, Any]], current_season: int
) -> list[dict[str, Any]]:
    def score(weapon: dict[str, Any]) -> tuple[int, int, int, int, int]:
        return (
            1 if weapon.get("isUpdated") else 0,
            1 if weapon.get("isTiered") else 0,
            1 if weapon.get("isCraftable") else 0,
            1 if weapon.get("isEnhanceable") else 0,
            weapon.get("season") or 0,
        )

    pressure_versions = [
        weapon
        for weapon in versions
        if (weapon.get("season") or 0) > current_season
        or weapon.get("isUpdated")
        or weapon.get("isTiered")
        or weapon.get("isCraftable")
    ]
    pool = pressure_versions or versions
    return sorted(pool, key=score, reverse=True)[:3]
