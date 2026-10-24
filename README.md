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
