"""Generate synthetic X12 professional, institutional, and dental claims."""

from dataclasses import asdict
from datetime import date
from hashlib import sha256
import json
from pathlib import Path
import shutil
import tempfile

from .model import Claim
from .scenario import (
    DEFAULT_ANCHOR, DEFAULT_SEED, DENTAL_SCENARIO, OUTPATIENT_SCENARIO, SCENARIO,
    SCENARIO_VERSION, build_claim,
)
from .validation import validate
from .x12 import TRANSACTION_GUIDES, controls, serialize

__version__ = "0.1.0.dev5"
__all__ = ["generate", "validate"]
TRANSACTION_SCENARIOS = {"837p": SCENARIO, "837i": OUTPATIENT_SCENARIO, "837d": DENTAL_SCENARIO}


def _json(data: dict) -> bytes:
    return (json.dumps(data, indent=2, sort_keys=True) + "\n").encode("ascii")


def _record(claim: Claim, filename: str, number: int) -> dict:
    line, = claim.lines
    patient = claim.encounter.patient
    provider = claim.encounter.provider
    payer = claim.coverage.payer
    interchange, group, transaction = controls(number)
    record = {
        "claim_id": claim.id,
        "patient_id": patient.id,
        "patient": {
            "first_name": patient.first_name,
            "last_name": patient.last_name,
            "birth_date": patient.birth_date.isoformat(),
            "sex": patient.sex,
            "address": asdict(patient.address),
        },
        "encounter_id": claim.encounter.id,
        "subscriber_id": claim.coverage.subscriber.member_id,
        "provider_id": provider.id,
        "provider_npi": provider.npi,
        "billing_provider": provider.organization_name or f"{provider.first_name} {provider.last_name}",
        "provider_address": asdict(provider.address),
        "payer_id": payer.id,
        "payer": payer.name,
        "coverage_program": claim.coverage.program,
        "service_date": claim.encounter.service_date.isoformat(),
        "setting": claim.encounter.setting,
        "charge_cents": claim.charge_cents,
        "diagnoses": (
            [{"system": line.diagnosis.system, "code": line.diagnosis.code}] if line.diagnosis else []
        ),
        "service_lines": [{
            "number": line.number,
            "procedure_system": line.procedure.system,
            "procedure_code": line.procedure.code,
            "units": line.units,
            "charge_cents": line.charge_cents,
        }],
        "edi": {
            "file": filename,
            "interchange_control": interchange,
            "group_control": group,
            "transaction_control": transaction,
        },
    }

    if line.revenue_code is not None:
        record["service_lines"][0]["revenue_code"] = line.revenue_code
        record["billing_organization"] = claim.encounter.provider.organization_name
        record["bill_type"] = "131"
        record["statement_from"] = record["statement_through"] = record["service_date"]
        attending = claim.encounter.attending_provider
        if attending is not None:
            record["attending_provider"] = f"{attending.first_name} {attending.last_name}"
            record["attending_provider_id"] = attending.id
            record["attending_provider_npi"] = attending.npi
    elif line.diagnosis is not None:
        record["service_lines"][0]["diagnosis_pointer"] = 1
    return record


def generate(
    output: str | Path, *, seed: int = DEFAULT_SEED, anchor: date = DEFAULT_ANCHOR,
    count: int = 1, transaction: str = "837p", scenario: str | None = None,
) -> Path:
    """Generate a run into a new directory and return the first EDI path."""
    if type(count) is not int or not 1 <= count <= 10_000:
        raise ValueError("count must be an integer from 1 through 10000")
    if transaction not in TRANSACTION_SCENARIOS:
        raise ValueError(f"unsupported transaction: {transaction}")
    supported_scenario = TRANSACTION_SCENARIOS[transaction]
    if scenario is not None and scenario != supported_scenario:
        raise ValueError(f"{transaction} supports the {supported_scenario} scenario")
    guide = TRANSACTION_GUIDES[transaction]
    output = Path(output)
    if output.exists() or output.is_symlink():
        raise FileExistsError(f"output directory already exists: {output}")

    files = {}
    records = []
    results = []
    for number in range(1, count + 1):
        claim = build_claim(seed, anchor, number, scenario=supported_scenario)
        filename = f"claims_{number:03d}.x12"
        edi = serialize(claim, anchor, number, transaction_type=transaction)
        errors = validate(edi)
        if errors:
            raise ValueError(f"{filename} failed structural validation: " + "; ".join(errors))
        files[filename] = edi
        records.append(_record(claim, filename, number))
        results.append({"file": filename, "level": "structural", "passed": True, "errors": []})

    report = results[0] if count == 1 else {
        "level": "structural", "passed": True, "files": results,
    }
    files["expected.json"] = _json({"synthetic": True, "claims": records})
    files["validation_report.json"] = _json(report)
    files["manifest.json"] = _json({
        "synthetic": True, "usage": "test-only", "generator_version": __version__,
        "x12_guide": guide, "scenario": supported_scenario, "scenario_version": SCENARIO_VERSION,
        "seed": seed, "anchor": anchor.isoformat(), "claim_count": count,
        "sha256": {name: sha256(content).hexdigest() for name, content in files.items()},
    })

    output.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix=".healthgen-", dir=output.parent))
    try:
        for name, content in files.items():
            (stage / name).write_bytes(content)
        if output.exists() or output.is_symlink():
            raise FileExistsError(f"output directory already exists: {output}")
        stage.rename(output)
    finally:
        if stage.exists():
            shutil.rmtree(stage)
    return output / "claims_001.x12"
