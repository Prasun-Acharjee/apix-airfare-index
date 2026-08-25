"""Configuration loading and basket construction."""
from __future__ import annotations

import functools
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Iterator

import yaml

from .models import Cell, ComplianceStatus

CONFIG_DIR = Path(__file__).resolve().parent.parent / "config"


@dataclass(frozen=True)
class SourceConfig:
    id: str
    name: str
    kind: str
    carrier_codes: tuple[str, ...]
    base_url: str
    search_path_template: str
    enabled: bool
    status: ComplianceStatus
    note: str
    crawl_delay_s: float
    user_agent: str
    timeout_s: int
    max_rph: int

    @property
    def collectable(self) -> bool:
        """Enabled AND audited as permitted. Both must hold."""
        return self.enabled and self.status.collectable


@dataclass(frozen=True)
class Basket:
    base_period: date
    base_value: float
    route_weights: dict[str, float]
    window_weights: dict[int, float]
    carrier_weights: dict[str, float]
    cabins: tuple[str, ...]
    qc: dict
    meta: dict
    # Sources this basket is currently weighted over. None = whatever is
    # collectable per sources.yaml. Set explicitly when replaying a fixed
    # dataset (a backfill, a synthetic run) so weights match the data in hand
    # rather than today's compliance posture.
    active_sources: tuple[str, ...] | None = None

    def with_sources(self, source_ids: tuple[str, ...]) -> "Basket":
        import dataclasses
        return dataclasses.replace(self, active_sources=tuple(sorted(set(source_ids))))

    def _resolve(self, source_ids: tuple[str, ...] | None) -> tuple[str, ...]:
        if source_ids is not None:
            return source_ids
        if self.active_sources is not None:
            return self.active_sources
        return tuple(s.id for s in collectable_sources())

    def cells(self, source_ids: tuple[str, ...] | None = None) -> Iterator[Cell]:
        """Enumerate the full target basket.

        `source_ids` defaults to the sources that are actually collectable, so
        the enumerated basket is the basket we can in principle observe. Pass
        an explicit tuple to enumerate a hypothetical basket.
        """
        source_ids = self._resolve(source_ids)
        for route in self.route_weights:
            for carrier in self.carrier_weights:
                for days in self.window_weights:
                    for cabin in self.cabins:
                        for sid in self._sources_for_carrier(carrier, source_ids):
                            yield Cell(
                                route=route, carrier=carrier, advance_days=days,
                                source_id=sid, cabin=cabin,
                            )

    @staticmethod
    def _sources_for_carrier(carrier: str, source_ids: tuple[str, ...]) -> tuple[str, ...]:
        by_id = {s.id: s for s in load_sources()}
        out = []
        for sid in source_ids:
            cfg = by_id.get(sid)
            if cfg is None:
                # A source not in the registry (synthetic replay, or a backfill
                # from an archived feed). Treat it as quoting every carrier;
                # the data itself decides which cells actually exist.
                out.append(sid)
            elif carrier in cfg.carrier_codes:
                out.append(sid)
        return tuple(out)

    def cell_weight(self, cell: Cell, source_ids: tuple[str, ...] | None = None) -> float:
        """Product of the three stratum weights, split across quoting sources.

        Independence across strata is an assumption, not a fact: booking-lead
        distributions genuinely differ by route (leisure pairs book earlier).
        With O-D x lead-time cross-tabs from DGCA or a GDS feed this should be
        replaced by the joint distribution. Documented in METHODOLOGY.md.

        The source split is equal-weight. Splitting by channel share of actual
        bookings (direct vs OTA) would be better and needs an industry source.
        """
        source_ids = self._resolve(source_ids)
        peers = self._sources_for_carrier(cell.carrier, source_ids)
        if not peers or cell.source_id not in peers:
            return 0.0
        return (
            self.route_weights.get(cell.route, 0.0)
            * self.carrier_weights.get(cell.carrier, 0.0)
            * self.window_weights.get(cell.advance_days, 0.0)
            / len(peers)
        )


def _normalise(d: dict) -> dict:
    total = sum(d.values())
    if total <= 0:
        raise ValueError("weight vector sums to zero")
    return {k: v / total for k, v in d.items()}


@functools.lru_cache(maxsize=None)
def load_basket(path: Path | None = None) -> Basket:
    path = path or CONFIG_DIR / "basket.yaml"
    raw = yaml.safe_load(path.read_text())
    meta = raw["meta"]
    return Basket(
        base_period=date.fromisoformat(str(meta["base_period"])),
        base_value=float(meta.get("base_value", 100.0)),
        route_weights=_normalise({r["pair"]: float(r["pax_share"]) for r in raw["routes"]}),
        window_weights=_normalise({int(w["days"]): float(w["booking_share"]) for w in raw["advance_windows"]}),
        carrier_weights=_normalise({c["code"]: float(c["market_share"]) for c in raw["carriers"]}),
        cabins=tuple(c["code"] for c in raw["cabins"] if c.get("include")),
        qc=raw["qc"],
        meta=meta,
    )


@functools.lru_cache(maxsize=None)
def load_sources(path: Path | None = None) -> tuple[SourceConfig, ...]:
    path = path or CONFIG_DIR / "sources.yaml"
    raw = yaml.safe_load(path.read_text())
    d = raw.get("defaults", {})
    out = []
    for s in raw["sources"]:
        c = s.get("compliance", {})
        out.append(
            SourceConfig(
                id=s["id"],
                name=s["name"],
                kind=s["kind"],
                carrier_codes=tuple(s.get("carrier_codes", [])),
                base_url=s["base_url"].rstrip("/"),
                search_path_template=s.get("search_path_template", "/"),
                enabled=bool(s.get("enabled", False)),
                status=ComplianceStatus(c.get("status", "blocked_unverifiable")),
                note=" ".join(c.get("note", "").split()),
                crawl_delay_s=float(c.get("crawl_delay_s", d.get("min_crawl_delay_s", 5.0))),
                user_agent=d.get("user_agent", "APIx-ResearchBot/0.1"),
                timeout_s=int(d.get("timeout_s", 45)),
                max_rph=int(d.get("max_requests_per_host_per_hour", 240)),
            )
        )
    return tuple(out)


def collectable_sources() -> tuple[SourceConfig, ...]:
    return tuple(s for s in load_sources() if s.collectable)


def collectable_carriers() -> set[str]:
    out: set[str] = set()
    for s in collectable_sources():
        out.update(s.carrier_codes)
    return out
