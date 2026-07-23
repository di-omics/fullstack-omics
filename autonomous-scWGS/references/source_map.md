# Source and interface map

Public configuration uses stable, neutral identifiers. Keep supplier names, ordering
details, document locations, and licensed pipeline checkout details in local files that
are excluded from version control.

## Stable identifiers

| Identifier | Version | Public role |
|---|---|---|
| `WGA-SOURCE-A` | `WGA-A-2025-05` | 96-well single-cell WGA procedure |
| `LIBPREP-SOURCE-B` | `B-2.0-2023-05` | library-preparation procedure |
| `WGS-ANALYSIS-INTERFACE-C` | `C-1.0` | generated analysis handoff |

The identifiers and versions are recorded in `config/protocol_params.yaml`. They are
stable references for code, tests, and audit records; they are not supplier or product
identifiers.

## Private source map

Use the ignored file `config/source_map.local.yaml` for authorized local source records:

```yaml
sources:
  WGA-SOURCE-A:
    document_title: "<authorized document title>"
    document_version: "<authorized document version>"
    document_path: "<local path or document-system identifier>"
    license_reference: "<local license record>"
  LIBPREP-SOURCE-B:
    document_title: "<authorized document title>"
    document_version: "<authorized document version>"
    document_path: "<local path or document-system identifier>"
    license_reference: "<local license record>"
  WGS-ANALYSIS-INTERFACE-C:
    checkout_path: "<compatible local checkout>"
    interface_version: "C-1.0"
    license_reference: "<local license record>"
```

Do not commit this file. It is an audit map for the local operator; public code refers
only to the stable identifiers.

## Private procurement configuration

`autoscwgs.params.load_params()` automatically merges the ignored
`config/reagents.local.yaml` over `config/reagents.yaml`. Mapping values merge
recursively; lists replace the corresponding public list as a unit. A local WGA
configuration therefore supplies the complete orderable entries:

```yaml
wga_kit:
  - name: "Single-cell whole-genome amplification kit, 96 reactions"
    vendor: "<configured supplier>"
    catalog: "<configured SKU>"
    purchase_channel: "<browser|vendor_direct|po>"
    verify: false
    scale: per_kit
wga_accessories:
  - name: "<configured accessory>"
    vendor: "<configured supplier>"
    catalog: "<configured SKU>"
    purchase_channel: "<browser|vendor_direct|po>"
    verify: false
    scale: per_run
```

Until supplier, SKU, channel, and verification state are populated, procurement routes
the entries to `verify` and `place_orders()` refuses the whole batch.

## Analysis interface contract

The generated `run_wgs_analysis.sh` targets `WGS-ANALYSIS-INTERFACE-C` version `C-1.0`:

- Required environment: `WGS_PIPELINE_DIR`, `DNASCOPE_MODEL`, `SENTIEON_LICENSE`.
- Required checkout entrypoint: `$WGS_PIPELINE_DIR/main.nf`.
- Default input: `input.csv` beside the generated runner; `INPUT_CSV` may explicitly
  select another file.
- Input header: `biosampleName,read1,read2`.
- Required host tools: Java, Nextflow, Docker, and AWS CLI.
- Generated invocation supplies input, publish directory, genome, platform, model,
  minimum reads, CPU, and memory parameters.
- Any missing environment value, file, entrypoint, or host tool exits nonzero before
  external analysis starts.

The simulator generates and validates this handoff. Executing the separately licensed
external pipeline is an operator-controlled step outside the simulator.
