"""Core domain types for APIx."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from enum import Enum
from typing import Optional


class ComplianceStatus(str, Enum):
    PERMITTED = "permitted"
    PERMITTED_WITH_DELAY = "permitted_with_delay"
    BLOCKED = "blocked"
    BLOCKED_PARTIAL = "blocked_partial"
    BLOCKED_UNVERIFIABLE = "blocked_unverifiable"

    @property
    def collectable(self) -> bool:
        return self in (ComplianceStatus.PERMITTED, ComplianceStatus.PERMITTED_WITH_DELAY)


class QuoteStatus(str, Enum):
    OK = "ok"
    NO_SERVICE = "no_service"          # carrier does not fly this pair/date
    SOLD_OUT = "sold_out"
    NOT_COLLECTED = "not_collected"    # source disallowed / disabled
    FETCH_FAILED = "fetch_failed"      # transport error, retried and gave up
    BLOCKED_BY_SITE = "blocked_by_site"  # 403/429/challenge — we stop, we do not evade
    REJECTED_QC = "rejected_qc"


@dataclass(frozen=True)
class Cell:
    """The 'item' of the index: the finest stratum we match across time.

    Matched-model indices require comparing like with like. For airfares the
    physical good is not a persistent SKU, so the cell is the closest stable
    analogue: a specific carrier's economy seat on a specific city pair bought
    a specific number of days ahead, quoted by a specific source.

    `source_id` is part of the cell identity on purpose. An OTA quote and an
    airline-direct quote for the same seat are different prices — the OTA
    applies its own markup and is often shown different fare inventory. Putting
    the source inside the cell means the index only ever compares a source
    against itself over time, so a source dropping in or out shifts coverage
    but never injects a spurious price movement. See METHODOLOGY.md,
    "Source is part of the item".
    """
    route: str
    carrier: str
    advance_days: int
    source_id: str
    cabin: str = "ECONOMY"

    def key(self) -> str:
        return f"{self.source_id}|{self.route}|{self.carrier}|T+{self.advance_days}|{self.cabin}"

    @property
    def stratum(self) -> str:
        """Parent stratum used for class-mean imputation of a missing cell."""
        return f"{self.route}|T+{self.advance_days}|{self.cabin}"

    def __str__(self) -> str:  # pragma: no cover - display only
        return self.key()


@dataclass
class RawQuote:
    """A single fare observation exactly as scraped, before normalisation."""
    source_id: str
    collected_at: datetime
    route: str
    origin: str
    destination: str
    departure_date: date
    advance_days: int
    carrier: Optional[str] = None
    flight_number: Optional[str] = None
    cabin: str = "ECONOMY"
    fare_family: Optional[str] = None
    total_inr: Optional[float] = None
    base_inr: Optional[float] = None
    taxes_inr: Optional[float] = None
    surcharges_inr: Optional[float] = None
    currency: str = "INR"
    is_refundable: Optional[bool] = None
    stops: Optional[int] = None
    status: QuoteStatus = QuoteStatus.OK
    raw_payload: dict = field(default_factory=dict)


@dataclass
class NormalisedQuote:
    """A quote that passed normalisation and QC, assigned to a cell."""
    source_id: str
    collected_on: date
    cell: Cell
    departure_date: date
    price_inr: float              # the index price concept, see METHODOLOGY.md
    total_inr: float
    base_inr: float
    taxes_inr: float
    flight_number: Optional[str] = None
    stops: Optional[int] = None
    qc_flags: list[str] = field(default_factory=list)


@dataclass
class CellPrice:
    """Elementary aggregate: one price per cell per day."""
    cell: Cell
    on_date: date
    price: float                  # geometric mean of quotes in the cell
    n_quotes: int
    imputed: bool = False
    imputation_source: Optional[str] = None


@dataclass
class IndexPoint:
    on_date: date
    value: float
    frequency: str                # daily | weekly | monthly
    n_cells_matched: int
    n_cells_imputed: int
    coverage: float               # weight-share of the basket actually observed
    imputation_share: float       # weight-share carried by imputation
    quality: str                  # ok | warn | fail
    notes: list[str] = field(default_factory=list)
