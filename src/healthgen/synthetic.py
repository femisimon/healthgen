"""Offline synthetic identities shared by healthcare scenarios."""

from dataclasses import dataclass
from datetime import date
from random import Random

from .model import Address, Patient, Provider

FIRST_NAMES = {
    "F": ("AMELIA", "CAMILA", "ELENA", "FATIMA", "GRACE", "MAYA", "NAOMI", "SOFIA"),
    "M": ("ADRIAN", "DANIEL", "ETHAN", "JULIAN", "MATEO", "NOAH", "OMAR", "SAMUEL"),
}
LAST_NAMES = ("BROOKS", "CHEN", "GARCIA", "HAYES", "KIM", "PATEL", "REED", "WILSON")
STREETS = ("MAPLE EXAMPLE LN", "CEDAR EXAMPLE DR", "WILLOW EXAMPLE CT", "ASPEN EXAMPLE WAY")


@dataclass(frozen=True)
class Region:
    city: str
    state: str
    zip_code: str
    label: str

    def address(self, street: str, unit: int) -> Address:
        return Address(street, self.city, self.state, f"{self.zip_code}{unit:04d}")


REGIONS = (
    Region("SACRAMENTO", "CA", "95814", "SIERRA"),
    Region("PORTLAND", "OR", "97205", "CASCADE"),
    Region("DENVER", "CO", "80202", "FRONT RANGE"),
    Region("RALEIGH", "NC", "27601", "PIEDMONT"),
)


def make_patient(
    rng: Random, suffix: str, region: Region, service_date: date, minimum_age: int,
) -> Patient:
    sex = rng.choice(("F", "M"))
    age = rng.randint(minimum_age, 89 if minimum_age == 65 else 79)
    month, day = rng.randint(1, 12), rng.randint(1, 28)
    birth_year = service_date.year - age - ((month, day) > (service_date.month, service_date.day))
    address = region.address(f"{rng.randint(100, 8999)} {rng.choice(STREETS)}", rng.randint(1, 9999))
    return Patient(
        f"PAT{suffix}", rng.choice(FIRST_NAMES[sex]), rng.choice(LAST_NAMES),
        date(birth_year, month, day), sex, address,
    )


def _fixture_npi(number: int, organization: bool) -> str:
    """Build a checksum-valid placeholder with no assignment assertion."""
    base = f"{2 if organization else 1}{number:08d}"
    digits = [int(digit) * (2 if index % 2 == 0 else 1)
              for index, digit in enumerate(reversed("80840" + base))]
    return base + str(-sum(digit - 9 if digit > 9 else digit for digit in digits) % 10)


def make_provider(region_number: int, slot: int, role: str) -> Provider:
    region = REGIONS[region_number]
    role_number = {"primary-care": 1, "hospital": 2, "dental": 3}[role]
    number = 90_000_000 + 100 * region_number + 10 * role_number + slot
    organization = None
    if role == "hospital":
        hospital_type = ("COMMUNITY", "REGIONAL")[slot]
        organization = f"SYNTHETIC {region.label} {hospital_type} HOSPITAL"
    sex = ("F", "M")[slot]
    return Provider(
        f"PROV{number}",
        "" if organization else FIRST_NAMES[sex][region_number + 2 * (role == "dental")],
        "" if organization else LAST_NAMES[2 * region_number + slot],
        _fixture_npi(number, organization is not None),
        f"{number:09d}",
        region.address(f"{100 + 10 * role_number + slot} EXAMPLE MEDICAL DR", 100 + slot),
        organization,
    )
