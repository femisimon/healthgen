# Contributing

Use Python 3.12 or newer. From the project directory, run:

```sh
python -m pip install .
python -m unittest discover -s tests -v
```

For a bug report, include the HealthGen version, Python version, command, seed, and scenario. Use synthetic input and output in issues and pull requests.

Keep the shared domain model independent of X12 syntax. When changing a supported claim profile, update the affected fixture and structural checks together. Document any changes to seeded output. Add an independent validator result when a change affects X12 structure.

Keep third-party code catalogs and licensed implementation guides outside the repository. Cite references used to make format or coding decisions.
