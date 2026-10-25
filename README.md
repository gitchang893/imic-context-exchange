# IMIC Context Exchange

Reproducibility artifacts for the study:

**Purpose-Bounded Context Exchange in Enterprise Agentic AI Systems: An Inter-Module Information Contract Architecture**

This repository contains the synthetic benchmark, reference oracle, implementation code, downstream language-model experiment records, execution manifests, response logs, and analysis scripts used to evaluate the Inter-Module Information Contract (IMIC) architecture.

## Overview

The study examines governance of contextual information exchanged across functional modules in enterprise agentic AI systems.

IMIC treats each proposed information transfer as a pre-execution decision and evaluates task-specific information requirements together with provenance-related metadata, semantic and temporal validity, permitted information scope, and applicable originating constraints.

The evaluation distinguishes:

- exchange-action correctness;
- information-boundary correctness;
- downstream task correctness; and
- joint correctness.

The experiments compare four implemented exchange methods:

- **B1 — Full Context**
- **B2 — Reduced Context**
- **B3 — Strong Structured Handoff**
- **B4 — IMIC**

These implementations are experimental comparators defined for the study and should not be interpreted as representing all architectures that could be described by the same general method names.

## Experimental Design

The deterministic benchmark contains **32 synthetic conditions** derived from a common customer-service, inventory-management, and quotation workflow.

The downstream integration experiment evaluates **14 selected conditions** across **four local language models** and **three generation seeds**, producing:

- **168 case–model–seed blocks**
- **672 method-level records**

The multi-hop conditions include four explicitly represented originating-constraint classes:

- general onward-transfer permission;
- permitted onward recipient;
- permitted onward purpose; and
- permitted onward field scope.

## Repository Contents

The repository is organized to separate benchmark definitions, implementation code, experiments, results, and analysis.

```text
imic-context-exchange/
├── benchmark/
│   ├── scenarios/
│   ├── oracle/
│   └── hashes/
├── src/
│   ├── b1_full_context/
│   ├── b2_reduced_context/
│   ├── b3_structured_handoff/
│   └── b4_imic/
├── experiments/
│   ├── deterministic/
│   └── downstream_llm/
├── results/
│   ├── deterministic/
│   ├── downstream_raw/
│   ├── response_logs/
│   └── merged/
├── analysis/
└── docs/
```

Additional files and reproduction instructions will be added as the publication artifacts are finalized.

## Benchmark Artifacts

The `benchmark/` directory contains the frozen benchmark inputs, canonical reference oracle, benchmark lock metadata, source scenario definitions, and checksum records used to support reproducibility of the deterministic benchmark and downstream language-model integration experiment.

### `benchmark/inputs/`

- `benchmark_inputs_v10.json`  
  Canonical frozen input artifact used by the publication benchmark.  
  The file contains the 32 synthetic benchmark conditions evaluated across the S1--S4 scenario families, including request data, policies, workflow configuration, scenario-specific mutations, and explicitly represented originating restrictions where applicable.

### `benchmark/oracle/`

- `benchmark_oracle_v10.json`  
  Canonical reference oracle used for publication-level evaluation.  
  For each benchmark condition, the oracle specifies the acceptable exchange action, permitted A-to-B and B-to-C field sets, and expected normalized business result.  
  It also records the `originating_constraint_class` for the S4 multi-hop conditions:
  - `onward_permission`
  - `recipient`
  - `purpose`
  - `field_scope`

### `benchmark/lock/`

- `benchmark_lock_v10.json`  
  Benchmark lock metadata generated for the frozen v1.0 benchmark.  
  The file records the benchmark version, reference clock, number of benchmark conditions, and SHA-256 digests of the canonicalized frozen input and oracle objects.  
  It is used by the benchmark code to verify that the loaded inputs and oracle match the frozen publication artifacts before evaluation.

### `benchmark/source_definitions/`

- `imic_v09_scenario_definitions.json`  
  Source scenario-definition artifact retained for provenance.  
  It contains the synthetic scenario definitions from which the benchmark inputs were derived during development.  
  This file is provided to document the development lineage of the benchmark and should not be confused with `benchmark_inputs_v10.json`, which is the canonical frozen input artifact used by the publication benchmark.

### `benchmark/hashes/`

- `v10_checksums.sha256`  
  File-level SHA-256 checksums for selected benchmark artifacts.  
  These checksums provide an additional integrity check on the exact files distributed in the repository.

On Linux, the checksum file can be verified with:

```bash
sha256sum -c benchmark/hashes/v10_checksums.sha256
```

The file-level checksums in this directory are distinct from the canonicalized object digests recorded in `benchmark_lock_v10.json`.  
The former verify distributed files byte-for-byte, whereas the latter are generated by the benchmark code from canonical JSON representations of the benchmark input and oracle objects.

### Canonical Publication Benchmark

For the publication evaluation, the canonical benchmark artifacts are:

- `benchmark/inputs/benchmark_inputs_v10.json`
- `benchmark/oracle/benchmark_oracle_v10.json`
- `benchmark/lock/benchmark_lock_v10.json`

The publication benchmark is identified in the benchmark lock as `IMIC-BENCH-1.0`.  
The `imic_v09_scenario_definitions.json` file is retained separately as a provenance artifact and is not the canonical frozen input loaded for the publication evaluation.

## Source Code

The `src/original/` directory contains the original experimental source files used to construct, execute, and evaluate the benchmark and downstream Ollama integration experiment.

These files are retained in their experimental form to preserve provenance.  
They have not been reorganized or refactored solely for publication.

### `src/original/imic_proto.py`

Core prototype functions and shared data structures used by the IMIC implementation.

### `src/original/imic_v03.py`

Earlier multi-hop and onward-transfer implementation components reused by the publication benchmark.

### `src/original/imic_v04.py`

Contract, template, and validation components used by the stronger structured-handoff and IMIC implementations.

### `src/original/imic_schema_v04.py`

Schema definitions and validation support used by the prototype implementation.

### `src/original/imic_v10_core.py`

Core deterministic simulator implementing the four evaluated exchange methods:

- `B1` — Full Context
- `B2` — Reduced Context
- `B3` — Strong Structured Handoff
- `B4` — IMIC

The file includes the common business functions, structured-handoff validation, IMIC validation, multi-hop transfer logic, and originating-constraint evaluation used in the deterministic benchmark.

### `src/original/imic_v10.py`

Benchmark driver for the 32-condition publication benchmark.

It defines the S1--S4 benchmark conditions, constructs and freezes the benchmark inputs and reference oracle, verifies benchmark digests, executes the four-method deterministic comparison, and produces benchmark result and summary artifacts.

### `src/original/imic_v11_ollama.py`

Downstream language-model integration driver using the frozen v1.0 benchmark.

It evaluates the 14 selected benchmark conditions across the four exchange methods, prepares downstream task prompts, invokes local Ollama models, records model and run metadata, normalizes model outputs, and scores exchange governance and downstream task outcomes separately.

### Provenance Note

The files in `src/original/` are provided as publication artifacts corresponding to the experimental implementation.

Minor historical comments, version labels, or development remnants may remain in these files because they are preserved for provenance rather than rewritten as a cleaned software release.

A future cleaned or refactored implementation, if provided, should be placed separately from `src/original/` and should not be treated as the exact code used for the reported experiments.

## Reproducibility Scope

The repository is intended to support independent inspection and reproduction of the reported synthetic evaluation.

The reference oracle is researcher-defined and is provided separately from the tested decision implementations so that expected exchange actions, permitted information boundaries, and normalized downstream outcomes can be inspected independently.

The study evaluates a controlled synthetic workflow and does not claim general validity across unrelated enterprise processes, policy systems, or independently developed organizational settings.

## Software Environment

The downstream language-model experiment uses local models executed through Ollama.

The evaluated configuration includes:

- Ollama version 0.32.5
- temperature: 0.7
- prediction-token limit: 3072
- context window: 4096
- timeout: 180 seconds
- generation seeds: 101, 202, and 303

Exact model identifiers, model digests, run manifests, and execution records are included with the experimental artifacts.

## Data and Code Availability

The synthetic benchmark scenarios, reference oracle, evaluation code, downstream experiment records, response logs, run manifests, and analysis scripts supporting the findings of the study are made available in this repository.

A versioned archival release and persistent DOI will be provided for the publication version.

## Citation

Citation information will be added after publication.

## License

Source code is released under the MIT License.

Licensing information for research data and benchmark artifacts will be provided separately.
