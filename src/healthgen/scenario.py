"""Compose synthetic claims for the supported screening and cleaning scenarios."""

from datetime import date, timedelta
from hashlib import sha256
from random import Random

from .model import Claim, Coverage, Diagnosis, Encounter, Payer, Procedure, ServiceLine, Subscriber
from .synthetic import REGIONS, make_patient, make_provider

SCENARIO = "office-visit"
OUTPATIENT_SCENARIO = "outpatient-hospital"
DENTAL_SCENARIO = "dental-cleaning"
SCENARIO_VERSION = 2
DEFAULT_ANCHOR = date(2026, 1, 15)
DEFAULT_SEED = 42
FIRST_SERVICE_DATE = date(2025, 1, 1)


def build_claim(
    seed: int, anchor: date, number: int = 1, *, scenario: str = SCENARIO,
) -> Claim:
    if type(seed) is not int or not 0 <= seed <= 2**64 - 1:
        raise ValueError("seed must be an unsigned 64-bit integer")
    if type(anchor) is not date or not date(2025, 1, 8) <= anchor <= date(2099, 12, 31):
        raise ValueError("anchor must be a date from 2025-01-08 through 2099-12-31")

    token = sha256(f"{scenario}:{SCENARIO_VERSION}:{seed}:{anchor}".encode("ascii")).hexdigest()
    suffix = f"{token[:12].upper()}{number:05d}"
    rng = Random(f"{token}:{number}")
    region_number = rng.randrange(len(REGIONS))
    region = REGIONS[region_number]
    maximum_lag = min(30, (anchor - FIRST_SERVICE_DATE).days)
    service_date = anchor - timedelta(days=rng.randint(1, maximum_lag))

    dental = scenario == DENTAL_SCENARIO
    institutional = scenario == OUTPATIENT_SCENARIO
    patient = make_patient(rng, suffix, region, service_date, 18 if dental else 65)
    slot = rng.randrange(2)
    program = "commercial-dental" if dental else "medicare-part-b"
    payer_type = "DENTAL" if dental else "MEDICARE"
    payer = Payer(f"TEST{payer_type}{region.state}", f"SYNTHETIC {region.label} {payer_type} PLAN")
    coverage = Coverage(Subscriber(f"MEM{suffix}", patient), payer, program)

    if dental:
        provider = make_provider(region_number, slot, "dental")
        line = ServiceLine(1, Procedure("CDT", "D1110"), 1, rng.randint(75, 140) * 100, None)
    else:
        provider = make_provider(region_number, slot, "hospital" if institutional else "primary-care")
        line = ServiceLine(
            1, Procedure("HCPCS", "G0444"), 1,
            rng.randint(45, 90) * 100 if institutional else rng.randint(25, 55) * 100,
            Diagnosis("ICD-10-CM", "Z13.31"), "0510" if institutional else None,
        )

    attending = make_provider(region_number, slot, "primary-care") if institutional else None
    setting = "outpatient-hospital" if institutional else "office"
    encounter = Encounter(f"ENC{suffix}", patient, provider, service_date, setting, attending)
    return Claim(f"CLM{suffix}", encounter, coverage, (line,))
