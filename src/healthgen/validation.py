"""Structural checks for the supported professional, institutional, and dental profiles."""

import re
from datetime import datetime
from decimal import Decimal

from .x12 import DENTAL_GUIDE, GUIDE, INSTITUTIONAL_GUIDE

# This profile accepts one self-subscriber, one diagnosis, and one service line.
# Duplicate segment names are resolved by position in the supported loop sequence.
COMMON_PROFILE = (
    ("ISA", 16), ("GS", 8), ("ST", 3), ("BHT", 6),
    ("NM1", 9), ("PER", 4), ("NM1", 9),
    ("HL", 4), ("NM1", 9), ("N3", 1), ("N4", 3), ("REF", 2),
    ("HL", 4), ("SBR", 9), ("NM1", 9), ("N3", 1), ("N4", 3), ("DMG", 3),
    ("NM1", 9), ("CLM", 9),
)
PROFESSIONAL_TAIL = (("HI", 1), ("LX", 1), ("SV1", 7), ("DTP", 3))
INSTITUTIONAL_TAIL = (("DTP", 3), ("CL1", 3), ("HI", 1), ("NM1", 9), ("LX", 1), ("SV2", 5), ("DTP", 3))
DENTAL_TAIL = (("DTP", 3), ("LX", 1), ("SV3", 6))
TRAILER = (("SE", 2), ("GE", 2), ("IEA", 2))
CLAIM_TAILS = {GUIDE: PROFESSIONAL_TAIL, INSTITUTIONAL_GUIDE: INSTITUTIONAL_TAIL, DENTAL_GUIDE: DENTAL_TAIL}


def validate(data: bytes) -> list[str]:
    """Return location-tagged structural errors. An empty list means pass."""
    try:
        edi = data.decode("ascii")
    except UnicodeDecodeError:
        return ["Interchange must contain ASCII bytes"]
    if len(edi) < 106 or (edi[3], edi[82], edi[104], edi[105]) != ("*", "^", ":", "~"):
        return ["ISA: invalid fixed-width header or unsupported delimiters"]
    parts = [part.lstrip("\r\n") for part in edi.split("~")]
    if parts.pop():
        return ["IEA: missing final segment terminator or unexpected trailing data"]
    segments = [part.split("*") for part in parts]
    guide = segments[1][8] if len(segments) > 1 and len(segments[1]) == 9 else GUIDE
    if guide not in CLAIM_TAILS:
        return ["GS08: unsupported implementation guide"]
    institutional = guide == INSTITUTIONAL_GUIDE
    dental = guide == DENTAL_GUIDE
    profile = COMMON_PROFILE + CLAIM_TAILS[guide] + TRAILER
    if len(segments) != len(profile):
        return [f"Interchange: expected {len(profile)} segments, found {len(segments)}"]
    for number, (segment, (tag, count)) in enumerate(zip(segments, profile), 1):
        if segment[0] != tag or len(segment) != count + 1:
            return [f"Segment {number} ({tag}): expected {tag} with {count} elements"]

    errors = []

    def check(index: int, element: int, pattern: str) -> None:
        value = segments[index][element]
        if not re.fullmatch(pattern, value):
            errors.append(f"Segment {index + 1} {segments[index][0]}{element:02d}: invalid value")

    text = r"[A-Z0-9 .-]"
    identifier = r"[A-Z0-9-]"
    amount = r"[0-9]{1,8}(?:\.[0-9]{1,2})?"
    fields = {
        0: ("00", " {10}", "00", " {10}", "ZZ", f"{text}{{15}}", "ZZ", f"{text}{{15}}",
            "[0-9]{6}", "[0-9]{4}", r"\^", "00501", "[0-9]{9}", "0", "T", ":"),
        1: ("HC", f"{identifier}{{2,15}}", f"{identifier}{{2,15}}", "[0-9]{8}",
            "[0-9]{4}", "[0-9]{1,9}", "X", guide),
        2: ("837", f"{identifier}{{4,9}}", guide),
        3: ("0019", "00", f"{identifier}{{1,50}}", "[0-9]{8}", "[0-9]{4}", "CH"),
        4: ("41", "2", f"{text}{{1,60}}", "", "", "", "", "46", f"{identifier}{{2,15}}"),
        5: ("IC", f"{text}{{1,60}}", "TE", "[0-9]{10}"),
        6: ("40", "2", f"{text}{{1,60}}", "", "", "", "", "46", f"{identifier}{{2,15}}"),
        7: ("1", "", "20", "1"),
        8: ("85", "1", f"{text}{{1,60}}", f"{text}{{1,35}}", "", "", "", "XX", "[0-9]{10}"),
        9: (f"{text}{{1,55}}",),
        10: (f"{text}{{2,30}}", "[A-Z]{2}", "[0-9]{9}"),
        11: ("EI", "[0-9]{9}"),
        12: ("2", "1", "22", "0"),
        13: ("P", "18", "", "", "", "", "", "", "CI" if dental else "MB"),
        14: ("IL", "1", f"{text}{{1,60}}", f"{text}{{1,35}}", "", "", "", "MI",
             f"{identifier}{{2,80}}"),
        15: (f"{text}{{1,55}}",),
        16: (f"{text}{{2,30}}", "[A-Z]{2}", "[0-9]{5}(?:[0-9]{4})?"),
        17: ("D8", "[0-9]{8}", "[FMU]"),
        18: ("PR", "2", f"{text}{{1,60}}", "", "", "", "", "PI", f"{identifier}{{2,80}}"),
    }
    claim_number = f"{identifier}{{1,20}}"
    if institutional:
        fields.update({
            8: ("85", "2", f"{text}{{1,60}}", "", "", "", "", "XX", "[0-9]{10}"),
            19: (claim_number, amount, "", "", "13:A:1", "", "A", "Y", "Y"),
            20: ("434", "RD8", "[0-9]{8}-[0-9]{8}"),
            21: ("3", "", "01"),
            22: ("ABK:Z1331",),
            23: ("71", "1", f"{text}{{1,60}}", f"{text}{{1,35}}", "", "", "", "XX", "[0-9]{10}"),
            24: ("1",),
            25: ("0510", "HC:G0444", amount, "UN", "1"),
        })
    elif dental:
        fields.update({
            19: (claim_number, amount, "", "", "11:B:1", "Y", "C", "Y", "Y"),
            21: ("1",),
            22: ("AD:D1110", amount, "", "", "", "1"),
        })
    else:
        fields.update({
            19: (claim_number, amount, "", "", "11:B:1", "Y", "A", "Y", "Y"),
            20: ("ABK:Z1331",),
            21: ("1",),
            22: ("HC:G0444", amount, "UN", "1", "", "", "1"),
        })
    service_date_index = 20 if dental else len(segments) - 4
    fields.update({
        service_date_index: ("472", "D8", "[0-9]{8}"),
        len(segments) - 3: (str(len(segments) - 4), re.escape(segments[2][2])),
        len(segments) - 2: ("1", re.escape(segments[1][6])),
        len(segments) - 1: ("1", re.escape(segments[0][13])),
    })
    for index, patterns in fields.items():
        for element, pattern in enumerate(patterns, 1):
            check(index, element, pattern)

    isa, gs, _, bht = segments[:4]
    if [len(value) for value in isa[1:]] != [2, 10, 2, 10, 2, 15, 2, 15, 6, 4, 1, 5, 9, 1, 1, 1]:
        errors.append("ISA: incorrect fixed-width elements")
    if (isa[6].rstrip(), isa[8].rstrip()) != (gs[2], gs[3]):
        errors.append("GS02/GS03: sender and receiver must match ISA06/ISA08")
    if (gs[2], gs[3]) != (segments[4][9], segments[6][9]):
        errors.append("1000A/1000B NM109: submitter and receiver must match GS02/GS03")
    if (isa[9], isa[10]) != (gs[4][2:], gs[5]) or gs[4:6] != bht[4:6]:
        errors.append("ISA09/ISA10, GS04/GS05 and BHT04/BHT05: dates or times differ")
    if errors:
        return errors

    try:
        created = datetime.strptime(bht[4] + bht[5], "%Y%m%d%H%M").date()
        born = datetime.strptime(segments[17][2], "%Y%m%d").date()
        service = datetime.strptime(segments[service_date_index][3], "%Y%m%d").date()
    except ValueError:
        errors.append("BHT04/BHT05, DMG02 or DTP03: invalid date or time")
    else:
        age = service.year - born.year - ((service.month, service.day) < (born.month, born.day))
        if age < 18 or service > created:
            errors.append("DMG02/DTP03: expected an adult patient and service on or before creation")

    if institutional:
        service_day = segments[service_date_index][3]
        if segments[20][3] != f"{service_day}-{service_day}":
            errors.append("DTP03: statement period must match the single service date")
        if not _valid_npi(segments[23][9]):
            errors.append("2310A NM109: invalid attending NPI prefix or checksum")
    if not _valid_npi(segments[8][9]):
        errors.append("2010AA NM109: invalid NPI prefix or checksum")

    line = segments[-4] if dental else segments[-5]
    charge_element = 3 if institutional else 2
    charge = Decimal(line[charge_element])
    if Decimal(segments[19][2]) != charge or charge <= 0:
        charge_field = f"{line[0]}{charge_element:02d}"
        errors.append(f"CLM02/{charge_field}: claim total must equal the positive service line charge")
    return errors


def _valid_npi(value: str) -> bool:
    digits = [int(digit) for digit in reversed("80840" + value)]
    doubled = [digit * (1 + index % 2) for index, digit in enumerate(digits)]
    return value[0] in "12" and sum(digit - 9 if digit > 9 else digit for digit in doubled) % 10 == 0
