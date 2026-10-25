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

The repository is organized to preserve the original experimental implementation while separating frozen benchmark artifacts, audit utilities, results, and reproduction documentation.

```text
imic-context-exchange/
├── analysis/
│   ├── imic_v11_analyze_3seed.py
│   └── resume_v11.py
├── benchmark/
│   ├── hashes/
│   ├── inputs/
│   ├── lock/
│   ├── oracle/
│   └── source_definitions/
├── docs/
│   └── reproduction.md
├── results/
│   ├── deterministic/
│   └── downstream/
│       ├── excluded/
│       ├── final/
│       └── runs/
│           ├── manifests/
│           ├── response_logs/
│           └── results/
├── src/
│   └── original/
├── CITATION.cff
├── LICENSE
└── README.md
```

The original experimental source files are retained under `src/original/` without publication-driven refactoring.

The benchmark, archived run artifacts, and final analysis products are stored separately so that the provenance chain from frozen inputs to reported results can be independently inspected.

## Reproduction

A Linux-based reference procedure for reproducing the integrity checks and final publication audit is provided in [`docs/reproduction.md`](docs/reproduction.md).

The procedure starts from a fresh repository clone, reconstructs the execution layout expected by the original experimental code, validates the deterministic benchmark, verifies all manifest-linked downstream artifacts, selects the canonical runs, reconstructs the 672-record final dataset, and compares the reconstructed outputs with the archived publication results.

No new language-model generations are required for this audit procedure.

## Software Environment

The downstream language-model experiment used local models executed through Ollama.

The evaluated configuration includes:

- Python 3.10 or later
- Ollama version 0.32.5
- temperature: 0.7
- prediction-token limit: 3072
- context window: 4096
- timeout: 180 seconds
- generation seeds: 101, 202, and 303

The prototype implementation requires the Python `jsonschema` package.

Exact model identifiers, model digests, run manifests, generation settings, source hashes, and execution records are included with the archived experimental artifacts.

The final publication audit uses the archived run artifacts and does not require a running Ollama server.

## Data and Code Availability

The synthetic benchmark inputs, canonical reference oracle, benchmark lock metadata, original experimental source code, deterministic benchmark results, downstream experiment records, response logs, run manifests, final merged dataset, and analysis scripts supporting the findings of the study are openly available in this repository.

A versioned archival release and persistent DOI will be provided for the publication version.

## Citation

Citation metadata for this repository is provided in [`CITATION.cff`](CITATION.cff).

GitHub users may also use the **Cite this repository** function displayed on the repository page.

A persistent DOI will be added after the publication release is archived.

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

## Analysis and Audit

The `analysis/` directory contains the utilities used to verify run integrity, select canonical downstream runs, and reproduce the final reported aggregates.

### `analysis/resume_v11.py`

Run-completeness and duplicate-check utility used during execution of the downstream experiment.

The script validates available v1.1 manifests and their associated result and response-log checksums, identifies the earliest valid run for each seed--model--case-group combination, reports later duplicate valid runs, and identifies missing or invalid run blocks.

### `analysis/imic_v11_analyze_3seed.py`

Final publication audit and aggregation script.

The analyzer independently discovers and validates the downstream run manifests, verifies model identifiers and digests, Ollama version, generation options, result and response-log hashes, source-code consistency, record counts, prompt hashes, and scoring fields.

For each seed--model--case-group combination, the earliest valid run is selected as canonical and later valid duplicates are excluded from the canonical analysis but recorded in the audit summary.

The script verifies the complete experimental design of four models, three seeds, 14 selected conditions, and four exchange methods, yielding 168 case--model--seed blocks and 672 method-level records.

It produces the final publication artifacts:

- `imic_v11_3seed_merged.csv`
- `imic_v11_3seed_summary.json`

The summary also records incomplete blocks, originating-constraint results, B3--B4 differences, identical-prompt divergences, canonical manifests, duplicate valid manifests, and invalid or excluded manifests.

## Results

The `results/` directory contains the deterministic benchmark outputs, downstream language-model run artifacts, and the final audited downstream analysis products reported in the study.

### `results/deterministic/`

- `pilot_results_v10.csv`  
  Method-level results from the deterministic benchmark comprising 32 synthetic conditions evaluated across B1--B4.

- `pilot_summary_v10.json`  
  Aggregated deterministic benchmark summary generated from the publication benchmark run.

These files correspond to the frozen v1.0 benchmark and are the deterministic results used for the reported comparison.

### `results/downstream/final/`

- `imic_v11_3seed_merged.csv`  
  Final merged downstream dataset containing **672 method-level records**:

  - 14 selected benchmark conditions
  - 4 local language models
  - 3 generation seeds
  - 4 exchange methods

  These records correspond to **168 case--model--seed paired blocks**.

- `imic_v11_3seed_summary.json`  
  Final audit summary generated by `analysis/imic_v11_analyze_3seed.py`.

  The summary records the canonical manifests, duplicate valid manifests, run-status counts, complete and incomplete paired blocks, overall and method-level correctness summaries, originating-constraint analyses, B3--B4 differences, identical-prompt divergences, model digests, generation settings, and environment information.

### `results/downstream/runs/`

The `runs/` directory contains the manifest-linked downstream execution artifacts used by the final audit.

```text
runs/
├── manifests/
├── results/
└── response_logs/
```

#### `manifests/`

Contains **25 valid v1.1 run manifests**.

Each manifest records the model identifier and digest, seed, selected case group, generation options, run status, source hashes, result-file hash, and response-log hash.

The final analyzer groups runs by seed, model, and case group and selects the **earliest valid run** for each unique combination.

This produces:

- **24 canonical manifests**, corresponding to 4 models × 3 seeds × 2 case groups; and
- **1 later duplicate valid manifest**, retained for audit transparency but excluded from the canonical 672-record analysis.

#### `results/`

Contains the **25 result CSV files referenced by the valid manifests**.

Each CSV contains method-level execution and scoring records for its corresponding run.

#### `response_logs/`

Contains the **25 response-log JSONL files referenced by the valid manifests**.

These logs preserve the corresponding downstream requests and observed model-response metadata required for integrity and prompt-hash verification.

The response logs also preserve non-successful generations as observed outcomes rather than silently replacing them through reruns.

### `results/downstream/excluded/orphan/`

This directory contains one result/response pair that was not referenced by any valid v1.1 manifest:

- `llm_results_v11_ollama_20261022_132924_230632.csv`
- `llm_responses_v11_ollama_20261022_132924_230632.jsonl`

Because no valid manifest references these files, they are excluded from the manifest-based final audit and from the 672-record publication analysis.

They are retained separately for transparency and are not part of the canonical experimental dataset.

### Canonical Downstream Analysis

The publication analysis does not select downstream run files manually.

`analysis/imic_v11_analyze_3seed.py` discovers available v1.1 manifests, validates their associated artifacts and recorded hashes, verifies the experimental configuration and scoring fields, and selects the earliest valid run for each seed--model--case-group combination.

The resulting canonical dataset contains exactly:

- **24 canonical run manifests**
- **168 case--model--seed paired blocks**
- **672 method-level records**

Later duplicate valid runs and manifest-unreferenced artifacts are retained separately but are not included in the reported canonical analysis.

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
