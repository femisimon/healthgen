"""Local golden-claim CLI."""

import argparse
from datetime import date
import json
from pathlib import Path
import sys

from . import TRANSACTION_SCENARIOS, generate, validate
from .scenario import DEFAULT_ANCHOR, DEFAULT_SEED


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="healthgen")
    commands = parser.add_subparsers(dest="command", required=True)
    generator = commands.add_parser("generate", help="generate synthetic claims")
    generator.add_argument("standard", choices=["x12"])
    generator.add_argument("transaction", choices=TRANSACTION_SCENARIOS)
    generator.add_argument("--count", type=int, default=1, help="number of claims (1–10000)")
    generator.add_argument("--scenario", choices=TRANSACTION_SCENARIOS.values())
    generator.add_argument("--output", type=Path, default=Path("output"))
    generator.add_argument("--seed", type=int, default=DEFAULT_SEED)
    generator.add_argument("--anchor", type=date.fromisoformat, default=DEFAULT_ANCHOR)
    validator = commands.add_parser("validate", help="check a supported claim profile")
    validator.add_argument("--file", type=Path, required=True)
    args = parser.parse_args(argv)

    try:
        if args.command == "generate":
            first = generate(
                args.output, seed=args.seed, anchor=args.anchor, count=args.count,
                transaction=args.transaction, scenario=args.scenario,
            )
            if args.count == 1:
                print(first)
            else:
                print(f"Generated {args.count} claims in {first.parent}")
            return 0
        errors = validate(args.file.read_bytes())
    except (OSError, ValueError) as error:
        print(f"healthgen: {error}", file=sys.stderr)
        return 2

    print(json.dumps({
        "file": str(args.file), "level": "structural", "passed": not errors, "errors": errors,
    }, indent=2))
    return int(bool(errors))
