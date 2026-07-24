# Autonomous single-cell WGS

> RESEARCH USE ONLY - not clinically validated.

A method-agnostic single-cell WGS preparation-state simulator with a
runtime-configured computational handoff.

The public project models orchestration boundaries, not laboratory execution. It
contains no reagent recipe, supplier selection, physical setting, control map, or
wet-lab acceptance criterion. All simulation scores are unitless and synthetic.

## Quickstart

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python scripts/run_all.py --n 16
python tests/test_end_to_end.py
```

Generated artifacts:

- a functional planning checklist;
- a non-executable WGS workflow planning brief;
- a deterministic simulation report;
- a sample manifest and fail-closed external-analysis runner.

## Hardware boundary

`mode=hardware` is denied by default. Physical execution requires ignored
`config/validated.local.yaml` containing `validated: true` and an
`execution_adapter` in `module:function` form. That laboratory-owned adapter is
responsible for all validated method details and safety controls.

## Analysis boundary

The external WGS pipeline checkout, execution profile, sample manifest, output
location, and any method-specific analysis options are runtime inputs.

Code is licensed under the MIT License.
