"""Format-neutral domain objects for the golden scenario."""

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class Address:
    street: str
    city: str
    state: str
    postal_code: str


@dataclass(frozen=True)
class Patient:
    id: str
    first_name: str
    last_name: str
    birth_date: date
    sex: str
    address: Address


@dataclass(frozen=True)
class Subscriber:
    member_id: str
    patient: Patient


@dataclass(frozen=True)
class Payer:
    id: str
    name: str


@dataclass(frozen=True)
class Coverage:
    subscriber: Subscriber
    payer: Payer
    program: str


@dataclass(frozen=True)
class Provider:
    id: str
    first_name: str
    last_name: str
    npi: str
    tax_id: str
    address: Address
    organization_name: str | None = None


@dataclass(frozen=True)
class Encounter:
    id: str
    patient: Patient
    provider: Provider
    service_date: date
    setting: str
    attending_provider: Provider | None = None


@dataclass(frozen=True)
class Diagnosis:
    system: str
    code: str


@dataclass(frozen=True)
class Procedure:
    system: str
    code: str


@dataclass(frozen=True)
class ServiceLine:
    number: int
    procedure: Procedure
    units: int
    charge_cents: int
    diagnosis: Diagnosis | None
    revenue_code: str | None = None


@dataclass(frozen=True)
class Claim:
    id: str
    encounter: Encounter
    coverage: Coverage
    lines: tuple[ServiceLine, ...]

    @property
    def charge_cents(self) -> int:
        return sum(line.charge_cents for line in self.lines)
