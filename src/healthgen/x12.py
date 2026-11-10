"""Map supported claims to X12 837 test interchanges."""

from datetime import date

from .model import Claim

GUIDE = "005010X222A1"
INSTITUTIONAL_GUIDE = "005010X223A2"
DENTAL_GUIDE = "005010X224A2"
TRANSACTION_GUIDES = {"837p": GUIDE, "837i": INSTITUTIONAL_GUIDE, "837d": DENTAL_GUIDE}


def controls(number: int) -> tuple[str, str, str]:
    return f"{number:09d}", str(number), f"{number:04d}"


def money(cents: int) -> str:
    return f"{cents // 100}.{cents % 100:02d}"


def serialize(claim: Claim, anchor: date, number: int = 1, *, transaction_type: str = "837p") -> bytes:
    interchange, group, transaction = controls(number)
    patient = claim.encounter.patient
    provider = claim.encounter.provider
    payer = claim.coverage.payer
    line, = claim.lines
    day = anchor.strftime("%Y%m%d")
    time = "1200"
    sender = "HEALTHGENTEST"
    receiver = payer.id
    guide = TRANSACTION_GUIDES[transaction_type]
    dental = guide == DENTAL_GUIDE
    billing_name = (
        ("2", provider.organization_name, "") if provider.organization_name is not None
        else ("1", provider.last_name, provider.first_name)
    )
    segments = [
        ("ISA", "00", " " * 10, "00", " " * 10, "ZZ", sender.ljust(15), "ZZ",
         receiver.ljust(15), day[2:], time, "^", "00501", interchange, "0", "T", ":"),
        ("GS", "HC", sender, receiver, day, time, group, "X", guide),
        ("ST", "837", transaction, guide),
        ("BHT", "0019", "00", claim.id, day, time, "CH"),
        ("NM1", "41", "2", "HEALTHGEN SYNTHETIC", "", "", "", "", "46", sender),
        ("PER", "IC", "HEALTHGEN TEST", "TE", "9165550100"),
        ("NM1", "40", "2", payer.name, "", "", "", "", "46", receiver),
        ("HL", "1", "", "20", "1"),
        ("NM1", "85", *billing_name, "", "", "", "XX", provider.npi),
        ("N3", provider.address.street),
        ("N4", provider.address.city, provider.address.state, provider.address.postal_code),
        ("REF", "EI", provider.tax_id),
        ("HL", "2", "1", "22", "0"),
        ("SBR", "P", "18", "", "", "", "", "", "", "CI" if dental else "MB"),
        ("NM1", "IL", "1", patient.last_name, patient.first_name, "", "", "", "MI",
         claim.coverage.subscriber.member_id),
        ("N3", patient.address.street),
        ("N4", patient.address.city, patient.address.state, patient.address.postal_code),
        ("DMG", "D8", patient.birth_date.strftime("%Y%m%d"), patient.sex),
        ("NM1", "PR", "2", payer.name, "", "", "", "", "PI", payer.id),
    ]
    service_day = claim.encounter.service_date.strftime("%Y%m%d")
    if dental:
        segments.extend((
            ("CLM", claim.id, money(claim.charge_cents), "", "", "11:B:1", "Y", "C", "Y", "Y"),
            ("DTP", "472", "D8", service_day),
            ("LX", str(line.number)),
            ("SV3", "AD:" + line.procedure.code, money(line.charge_cents), "", "", "", str(line.units)),
        ))
    else:
        segments.extend(_medical_segments(claim, service_day, guide == INSTITUTIONAL_GUIDE))

    segments.extend((
        ("SE", str(len(segments) - 1), transaction),
        ("GE", "1", group),
        ("IEA", "1", interchange),
    ))
    return "".join("*".join(segment) + "~\n" for segment in segments).encode("ascii")


def _medical_segments(claim: Claim, service_day: str, institutional: bool) -> list[tuple[str, ...]]:
    line, = claim.lines
    if line.diagnosis is None:
        raise ValueError("medical claim requires a diagnosis")
    diagnosis = "ABK:" + line.diagnosis.code.replace(".", "")
    procedure = "HC:" + line.procedure.code
    if institutional:
        attending = claim.encounter.attending_provider
        if attending is None or line.revenue_code is None:
            raise ValueError("institutional claim requires an attending provider and a revenue code")
        segments = [
            ("CLM", claim.id, money(claim.charge_cents), "", "", "13:A:1", "", "A", "Y", "Y"),
            ("DTP", "434", "RD8", f"{service_day}-{service_day}"),
            ("CL1", "3", "", "01"),
            ("HI", diagnosis),
            ("NM1", "71", "1", attending.last_name, attending.first_name, "", "", "", "XX", attending.npi),
            ("LX", str(line.number)),
            ("SV2", line.revenue_code, procedure, money(line.charge_cents), "UN", str(line.units)),
        ]
    else:
        segments = [
            ("CLM", claim.id, money(claim.charge_cents), "", "", "11:B:1", "Y", "A", "Y", "Y"),
            ("HI", diagnosis),
            ("LX", str(line.number)),
            ("SV1", procedure, money(line.charge_cents), "UN", str(line.units), "", "", "1"),
        ]
    segments.append(("DTP", "472", "D8", service_day))
    return segments
