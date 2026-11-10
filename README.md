# HealthGen

HealthGen generates synthetic X12 837P professional claims targeting `005010X222A1`, 837I institutional claims targeting `005010X223A2`, and 837D dental claims targeting `005010X224A2`. The professional fixture represents a depression screening in a primary-care office. The institutional fixture represents the facility claim for a screening at an outpatient hospital. The dental fixture represents a routine adult cleaning at a dental office. Each uses a synthetic adult self-subscriber, a primary payer, and one service line.

## Quick start

With Python 3.12 or newer, install [HealthGen from PyPI](https://pypi.org/project/healthgen/) and generate one synthetic 837P professional claim:

```sh
python -m pip install healthgen
healthgen generate x12 837p --count 1 --seed 42 --output claims-demo
healthgen validate --file claims-demo/claims_001.x12
```

Open `claims-demo/expected.json` to see the fictional patient, provider, payer, service, and charges. Open `claims-demo/claims_001.x12` to see the raw X12 claim. Choose a new output directory when you run the command again.

Use `837i` for an institutional claim or `837d` for a dental claim. The installed package uses only the Python standard library at runtime.

## Run from source

Clone this repository or download the source archive, then run these commands from the project directory.

```sh
python -m pip install .
healthgen generate x12 837p --count 1 --scenario office-visit --seed 42 --output output
healthgen validate --file output/claims_001.x12
healthgen generate x12 837i --scenario outpatient-hospital --seed 42 --output output-837i
healthgen validate --file output-837i/claims_001.x12
healthgen generate x12 837d --scenario dental-cleaning --seed 42 --output output-837d
healthgen validate --file output-837d/claims_001.x12
```

Use `--count 42` for 42 claims. HealthGen writes one EDI file per claim and includes all 42 patient records in `expected.json`. The seed controls reproducibility. Choose a new output directory for each run. Generation publishes the directory after writing and structurally validating the complete run. `--anchor YYYY-MM-DD` sets the interchange date. Service dates are selected up to 30 days earlier, starting no earlier than January 1, 2025. The default anchor is January 15, 2026. Matching generation settings and generator versions produce identical output bytes.

- Each numbered `claims_*.x12` file contains one test interchange, group, transaction, and claim.
- `expected.json` comes from the synthetic data model and links the claim and service line to the EDI file and control numbers. Charges use integer cents.
- `manifest.json` identifies the generator and scenario versions, seed, anchor, guide version, and SHA-256 hashes of the other files.
- `validation_report.json` records the local structural result.

The `validate` command prints JSON and returns 0 on success, 1 for structural errors, or 2 for command or file errors. It checks the specific golden scenario shape, including the standard delimiters, envelope counts and controls, required fields, NPI checksum, service timing, diagnosis pointer, and charge balance.

The Python API provides the same generation and structural validation.

```python
from datetime import date

from healthgen import generate, validate

edi_path = generate("output", seed=42, anchor=date(2026, 1, 15))
errors = validate(edi_path.read_bytes())
```

## Synthetic data engine

Scenario version 2 generates names, birth dates, fictional street addresses, regional providers and payer plans, service dates, and scenario-specific charges from the seed. It uses four US city and ZIP prefixes with invented street addresses and ZIP+4 extensions. Medical scenarios pair adult patients aged 65–89 at service with synthetic Medicare Part B plans. Dental scenarios pair adults aged 18–79 with synthetic commercial dental plans. Recurring provider and payer IDs identify consistent profiles. The claim JSON includes billing provider, address, payer name, and coverage program alongside patient demographics and service lines.

Each transaction still models one supported screening or cleaning scenario. Charge ranges are synthetic fixture inputs. Version 2 changes seeded output from earlier versions. The original v1 fixtures remain available for validation regression tests.

## Independent validation

The v2 [837P](tests/fixtures/office_visit_v2.x12) and [837I](tests/fixtures/outpatient_hospital_v2.x12) fixtures passed Pyx12 4.1.0. The v2 [837D](tests/fixtures/dental_cleaning_v2.x12) fixture passed Moov X12 v0.1.1.

Pyx12 4.1.0 accepted [the golden fixture](tests/fixtures/office_visit_v1.x12) using its `837.5010.X222.A1.xml` map. Its JSON report had no errors, and the acknowledgment contained `IK5*A` and `AK9*A*1*1*1`. The fixture SHA-256 is `a78c6809fe2ba1457c34e11ca414b094e52e2b385ea206a620f889d487911061`. [Pyx12 project](https://github.com/azoner/pyx12)

Pyx12 4.1.0 also accepted [the outpatient 837I fixture](tests/fixtures/outpatient_hospital_v1.x12). The 837I target is `005010X223A2`, which Pyx12 maps to its file named `837Q3.I.5010.X223.A1.xml`. The acknowledgment identified `005010X223A2` and accepted the group and transaction. The scenario uses hospital outpatient bill type 131, clinic revenue code 0510, and the same G0444 screening code. [CMS institutional billing reference](https://www.cms.gov/regulations-and-guidance/guidance/transmittals/downloads/r2359cp.pdf) · [CMS revenue code reference](https://bluebutton.cms.gov/resources/variables/rev_cntr/)

Moov X12 v0.1.1 parsed and accepted [the 837D fixture](tests/fixtures/dental_cleaning_v1.x12) with its `005010X224A2` rules. This scenario uses a single CDT procedure identifier, D1110, published in a CMS billing reference. The repository contains no CDT catalog. [Moov dental rules](https://pkg.go.dev/github.com/moov-io/x12@v0.1.1/rules/rule_5010_837d) · [CMS procedure code reference](https://www.cms.gov/files/document/r12419cp.pdf)

To repeat the Pyx12 check, install the validator in a separate environment and run it against a scratch copy of the fixture. Pyx12 writes its acknowledgment and JSON report alongside the input. Check the report for the selected guide, accepted group and transaction, and absence of errors.

```sh
python -m pip install pyx12==4.1.0
x12valid --verbose --json-output office_visit_v1.x12
```

HealthGen's structural result covers its supported scenario. Pyx12 and Moov check their respective independent rules. Payer acceptance is a separate process that may include enrollment, identifier lookup, and coverage edits. All identities and addresses in the fixture are synthetic. The checksum-valid NPI and other identifiers are placeholders with no assertion of assignment or eligibility. Use the fixture only in test systems.

The scenario uses the CMS-published HCPCS Level II code G0444 and ICD-10-CM code Z13.31. The package contains no CPT catalog or X12 implementation-guide text. A plausible fixture serves as test data only. [CMS HCPCS and office billing reference](https://www.cms.gov/regulations-and-guidance/guidance/manuals/downloads/clm104c18pdf.pdf) · [CMS ICD-10-CM reference](https://www.cms.gov/icd10m/FY2026-fr-v43-fullcode-cms/fullcode_cms/P1016.html)

## Run tests

```sh
python -m unittest discover -s tests -v
```

## Contributing and license

See [CONTRIBUTING.md](CONTRIBUTING.md) to report issues or submit changes. HealthGen source code is released under the [Apache License 2.0](LICENSE). Third-party standards and terminology are subject to their respective terms. [ADA dental terminology licensing](https://www.ada.org/publications/ada-store-products/licensing-for-commercial-users)
