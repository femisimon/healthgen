from datetime import date
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest

from healthgen import generate, validate
from healthgen.x12 import money

FIXTURE = Path(__file__).parent / "fixtures" / "office_visit_v1.x12"


class GoldenClaimTests(unittest.TestCase):
    def test_golden_output_and_traceability(self):
        with TemporaryDirectory() as temp:
            first = generate(Path(temp) / "first")
            second = generate(Path(temp) / "second")
            self.assertEqual(first.read_bytes(), FIXTURE.with_name("office_visit_v2.x12").read_bytes())
            self.assertEqual(validate(first.read_bytes()), [])
            self.assertEqual(first.read_bytes()[104:106], b":~")
            self.assertEqual(first.read_bytes()[102:103], b"T")

            manifest = json.loads((first.parent / "manifest.json").read_bytes())
            self.assertEqual(manifest["claim_count"], 1)
            self.assertEqual(manifest["x12_guide"], "005010X222A1")
            for path in first.parent.iterdir():
                self.assertEqual(path.read_bytes(), (second.parent / path.name).read_bytes())
                if path.name != "manifest.json":
                    self.assertEqual(sha256(path.read_bytes()).hexdigest(), manifest["sha256"][path.name])
            record, = json.loads((first.parent / "expected.json").read_bytes())["claims"]
            self.assertIn(f"CLM*{record['claim_id']}*{money(record['charge_cents'])}", first.read_text())
            self.assertIn(f"ST*837*{record['edi']['transaction_control']}*", first.read_text())
            self.assertIn(f"*MI*{record['subscriber_id']}~", first.read_text())
            self.assertEqual(record["service_lines"][0]["charge_cents"], record["charge_cents"])
            with self.assertRaises(FileExistsError):
                generate(first.parent)
            self.assertEqual(first.read_bytes(), FIXTURE.with_name("office_visit_v2.x12").read_bytes())

    def test_seed_and_date_anchoring(self):
        with TemporaryDirectory() as temp:
            path = generate(Path(temp) / "different", seed=12, anchor=date(2026, 2, 1))
            self.assertNotEqual(path.read_bytes(), FIXTURE.read_bytes())
            claim, = json.loads((path.parent / "expected.json").read_bytes())["claims"]
            service = date.fromisoformat(claim["service_date"])
            self.assertTrue(1 <= (date(2026, 2, 1) - service).days <= 30)
            self.assertIn(f"DTP*472*D8*{service:%Y%m%d}~".encode(), path.read_bytes())
            self.assertEqual(validate(path.read_bytes()), [])

    def test_structural_failures(self):
        golden = FIXTURE.read_bytes()
        cases = (
            (b"HI*ABK:Z1331~\n", b"", "expected 27 segments"),
            (b"SE*23*0001", b"SE*23*0002", "SE02"),
            (b"SE*23*0001", b"SE*22*0001", "SE01"),
            (b"GE*1*1", b"GE*2*1", "GE01"),
            (b"IEA*1*000000001", b"IEA*1*000000002", "IEA02"),
            (b"HI*ABK:Z1331", b"HI*ZZ:Z1331", "HI01"),
            (b"SV1*HC:G0444*35.00", b"SV1*HC:G0444*34.99", "CLM02/SV102"),
            (b"1999999992", b"1999999993", "checksum"),
            (b"DTP*472*D8*20260108", b"DTP*472*D8*20260230", "invalid date"),
        )
        for before, after, message in cases:
            with self.subTest(message=message):
                self.assertIn(message, "\n".join(validate(golden.replace(before, after))))

    def test_cli_returns_nonzero_and_reports_invalid_edi(self):
        with TemporaryDirectory() as temp:
            path = Path(temp) / "invalid.x12"
            path.write_bytes(FIXTURE.read_bytes().replace(b"SE*23", b"SE*24"))
            result = subprocess.run(
                [sys.executable, "-m", "healthgen", "validate", "--file", str(path)],
                capture_output=True, text=True,
            )
            self.assertEqual(result.returncode, 1)
            self.assertFalse(json.loads(result.stdout)["passed"])


class InstitutionalClaimTests(unittest.TestCase):
    def test_outpatient_fixture_and_traceability(self):
        fixture = FIXTURE.with_name("outpatient_hospital_v2.x12").read_bytes()
        with TemporaryDirectory() as temp:
            first = generate(Path(temp) / "first", count=2, transaction="837i")
            self.assertEqual(first.read_bytes(), fixture)
            self.assertEqual(validate(fixture), [])
            manifest = json.loads((first.parent / "manifest.json").read_bytes())
            self.assertEqual(manifest["x12_guide"], "005010X223A2")
            records = json.loads((first.parent / "expected.json").read_bytes())["claims"]
            self.assertEqual(len({record["claim_id"] for record in records}), 2)
            for record in records:
                edi = (first.parent / record["edi"]["file"]).read_bytes()
                self.assertEqual(validate(edi), [])
                self.assertIn(f"CLM*{record['claim_id']}*{money(record['charge_cents'])}".encode(), edi)
                self.assertEqual(record["service_lines"][0]["revenue_code"], "0510")
                self.assertEqual(record["statement_from"], record["service_date"])
                self.assertIn(record["attending_provider_npi"].encode(), edi)

    def test_institutional_charge_and_statement_errors(self):
        fixture = FIXTURE.with_name("outpatient_hospital_v1.x12").read_bytes()
        self.assertIn("CLM02/SV203", "\n".join(validate(fixture.replace(b"G0444*55", b"G0444*54"))))
        self.assertIn("statement period", "\n".join(validate(fixture.replace(b"RD8*20260108", b"RD8*20260107"))))


class DentalClaimTests(unittest.TestCase):
    def test_dental_fixture_and_traceability(self):
        fixture = FIXTURE.with_name("dental_cleaning_v2.x12").read_bytes()
        with TemporaryDirectory() as temp:
            first = generate(Path(temp) / "dental", count=2, transaction="837d")
            self.assertEqual(first.read_bytes(), fixture)
            manifest = json.loads((first.parent / "manifest.json").read_bytes())
            self.assertEqual(manifest["x12_guide"], "005010X224A2")
            records = json.loads((first.parent / "expected.json").read_bytes())["claims"]
            self.assertEqual(len({record["claim_id"] for record in records}), 2)
            for record in records:
                edi = (first.parent / record["edi"]["file"]).read_bytes()
                self.assertEqual(validate(edi), [])
                self.assertIn(f"CLM*{record['claim_id']}*{money(record['charge_cents'])}".encode(), edi)
                self.assertEqual(record["service_lines"][0]["procedure_system"], "CDT")
                self.assertEqual(record["service_lines"][0]["procedure_code"], "D1110")
                self.assertEqual(record["diagnoses"], [])

    def test_dental_charge_and_qualifier_errors(self):
        fixture = FIXTURE.with_name("dental_cleaning_v1.x12").read_bytes()
        self.assertIn("CLM02/SV302", "\n".join(validate(fixture.replace(b"D1110*95", b"D1110*94"))))
        self.assertIn("SV301", "\n".join(validate(fixture.replace(b"AD:D1110", b"HC:D1110"))))


class SyntheticEngineTests(unittest.TestCase):
    def test_varied_profiles_and_stable_relationships(self):
        with TemporaryDirectory() as temp:
            for transaction in ("837p", "837i", "837d"):
                with self.subTest(transaction=transaction):
                    path = generate(Path(temp) / transaction, count=42, transaction=transaction)
                    records = json.loads((path.parent / "expected.json").read_bytes())["claims"]
                    for key in ("provider_id", "payer_id", "service_date", "charge_cents"):
                        self.assertGreater(len({record[key] for record in records}), 1)
                    self.assertEqual(len({record["patient_id"] for record in records}), 42)
                    self.assertGreater(len({record["patient"]["last_name"] for record in records}), 1)
                    providers = {}
                    for record in records:
                        patient = record["patient"]
                        born = date.fromisoformat(patient["birth_date"])
                        service = date.fromisoformat(record["service_date"])
                        age = service.year - born.year - ((service.month, service.day) < (born.month, born.day))
                        self.assertGreaterEqual(age, 18 if transaction == "837d" else 65)
                        self.assertEqual(patient["address"]["state"], record["provider_address"]["state"])
                        provider = (record["billing_provider"], record["provider_npi"], record["provider_address"])
                        self.assertEqual(providers.setdefault(record["provider_id"], provider), provider)
