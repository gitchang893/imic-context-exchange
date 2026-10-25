# Reproduction Guide

This document describes the reference procedure for validating the publication artifacts in the **IMIC Context Exchange** repository.

The procedure was verified on Linux using a fresh clone of the repository.

The goal is to reproduce the integrity checks and final analysis from the archived benchmark inputs, source code, manifests, result files, and response logs.

No new language-model generations are required for the final audit described here.

## 1. Scope

The repository contains two related evaluation layers:

1. a deterministic 32-condition benchmark evaluated across four exchange methods; and
2. a downstream language-model integration experiment using 14 selected conditions, four local language models, three seeds, and four exchange methods.

The downstream experiment contains:

- 168 case--model--seed paired blocks;
- 672 method-level records;
- 24 canonical seed--model--case-group runs;
- one later duplicate valid run retained for audit transparency; and
- three observed `TRUNCATED` generations retained as experimental outcomes.

The final audit does not rerun the language models.

Instead, it validates the archived run artifacts and reconstructs the reported merged dataset and summary.

## 2. Requirements

The reference procedure assumes:

- Linux
- Python 3.10 or later
- Git
- the Python `jsonschema` package required by the prototype implementation

A minimal environment can be prepared with:

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install --upgrade pip
python3 -m pip install jsonschema
```

The final audit itself uses only archived experiment artifacts and does not require a running Ollama server.

## 3. Obtain a Fresh Clone

Clone the publication repository into a new directory.

```bash
git clone https://github.com/gitchang893/imic-context-exchange.git
cd imic-context-exchange
```

The commands below assume that the current directory is the repository root.

Record the repository root before constructing the temporary execution workspace:

```bash
REPO_ROOT="$(pwd -P)"
```

## 4. Repository Artifacts Used by the Reproduction Procedure

The deterministic benchmark uses the frozen publication artifacts:

```text
benchmark/inputs/benchmark_inputs_v10.json
benchmark/oracle/benchmark_oracle_v10.json
benchmark/lock/benchmark_lock_v10.json
```

The original experimental implementation is preserved under:

```text
src/original/
```

The final run-audit and aggregation utilities are preserved under:

```text
analysis/
```

The archived downstream run artifacts are stored under:

```text
results/downstream/runs/manifests/
results/downstream/runs/results/
results/downstream/runs/response_logs/
```

The reported final downstream artifacts are stored under:

```text
results/downstream/final/imic_v11_3seed_merged.csv
results/downstream/final/imic_v11_3seed_summary.json
```

One manifest-unreferenced result/response pair is retained separately under:

```text
results/downstream/excluded/orphan/
```

The orphan pair is not included in the manifest-based publication audit.

## 5. Construct the Reference Execution Workspace

The original experimental code was developed using a flat source-code layout with benchmark and run artifacts under an `imic_demo/` directory.

To preserve the original source files while supporting the reorganized publication repository, construct a temporary workspace that recreates that layout.

From the repository root:

```bash
WORK_DIR="$(mktemp -d)"
mkdir -p "$WORK_DIR/imic_demo"
```

Copy the original experimental Python files:

```bash
cp src/original/*.py "$WORK_DIR/"
```

Copy the audit and analysis utilities:

```bash
cp analysis/resume_v11.py "$WORK_DIR/"
cp analysis/imic_v11_analyze_3seed.py "$WORK_DIR/"
```

Copy the frozen benchmark artifacts:

```bash
cp benchmark/inputs/benchmark_inputs_v10.json \
   "$WORK_DIR/imic_demo/"

cp benchmark/oracle/benchmark_oracle_v10.json \
   "$WORK_DIR/imic_demo/"

cp benchmark/lock/benchmark_lock_v10.json \
   "$WORK_DIR/imic_demo/"
```

Copy all manifest-linked downstream run artifacts:

```bash
cp results/downstream/runs/manifests/*.json \
   "$WORK_DIR/imic_demo/"

cp results/downstream/runs/results/*.csv \
   "$WORK_DIR/imic_demo/"

cp results/downstream/runs/response_logs/*.jsonl \
   "$WORK_DIR/imic_demo/"
```

Do not copy the files under `results/downstream/excluded/orphan/` into the audit workspace.

Enter the temporary workspace:

```bash
cd "$WORK_DIR"
```

## 6. Validate the Deterministic Benchmark

Run the deterministic benchmark test suite:

```bash
python3 imic_v10.py --test
```

A successful validation runs 10 tests and ends with:

```text
Ran 10 tests
OK
```

The tests include checks for:

- exactly 32 benchmark conditions;
- eight conditions per S1--S4 family;
- complete and missing context behavior;
- semantic-unit checks;
- source-update revalidation;
- the four originating-constraint classes;
- the intentional absence of originating-constraint enforcement in B3;
- the matched S4 negative/positive pairs; and
- all 128 deterministic case--method comparisons.

## 7. Validate Available Downstream Runs

Run the run-completeness and duplicate checker:

```bash
python3 resume_v11.py
```

The utility validates each v1.1 manifest and checks:

- experiment version;
- expected case group;
- expected comparison-record count;
- referenced result-file existence;
- referenced response-log existence;
- result-file SHA-256;
- response-log SHA-256; and
- coverage of all expected seed--model--group combinations.

The expected final counts are:

```text
Canonical: 24/24
Missing:   0/24
Duplicate: 1
```

The canonical selection rule is the **earliest valid run** for each unique combination of:

```text
seed × model × case group
```

A later valid run for the same combination is retained as a duplicate but excluded from the canonical analysis.

## 8. Run the Final Publication Audit

Before running the analyzer, confirm that the following files do not already exist in the temporary workspace:

```text
imic_demo/imic_v11_3seed_merged.csv
imic_demo/imic_v11_3seed_summary.json
```

The analyzer intentionally uses exclusive file creation to prevent accidental replacement of an audited result.

Run:

```bash
python3 imic_v11_analyze_3seed.py
```

The analyzer validates, among other checks:

- 24 canonical manifests;
- four expected model identifiers;
- recorded model digests;
- Ollama version;
- generation options;
- seeds 101, 202, and 303;
- the two expected case groups;
- result and response-log hashes;
- consistency of source-code hashes across canonical runs;
- exactly 672 canonical method-level records;
- exactly 168 case--model--seed paired blocks;
- result CSV and response-log correspondence;
- prompt hashes for invoked downstream calls;
- independent recomputation of action, boundary, task, and joint correctness;
- expected B4 rejection reasons for the four negative originating-constraint cases;
- 48 B3--B4 originating-action differences;
- 12 repeated observations for each of the four originating-constraint classes; and
- identical-prompt output divergence detection.

A successful run ends with:

```text
FINAL AUDIT COMPLETE
```

The expected experiment size is:

```text
Canonical manifests: 24 / 24
Comparison records: 672
```

The audit generates:

```text
imic_demo/imic_v11_3seed_merged.csv
imic_demo/imic_v11_3seed_summary.json
```

## 9. Verify the Reconstructed Final Artifacts

Compare the newly reconstructed merged CSV with the publication artifact:

```bash
cmp \
  imic_demo/imic_v11_3seed_merged.csv \
  "$REPO_ROOT/results/downstream/final/imic_v11_3seed_merged.csv"
```

Then compare the reconstructed audit summary:

```bash
cmp \
  imic_demo/imic_v11_3seed_summary.json \
  "$REPO_ROOT/results/downstream/final/imic_v11_3seed_summary.json"
```

If `cmp` produces no output, the files are byte-for-byte identical.

The exit status can be checked immediately after either comparison with:

```bash
echo $?
```

An exit status of `0` indicates equality.

## 10. Interpretation of Incomplete Runs

An `INCOMPLETE` run status does not automatically exclude a run from the publication analysis.

The downstream experiment retains observed non-successful generations rather than silently replacing them through reruns.

In particular, the publication dataset contains three `TRUNCATED` generations.

These outcomes remain part of the canonical archived observations and are reflected in the final 672-record dataset and audit summary.

The analyzer distinguishes run completeness from manifest validity.

A manifest can therefore remain valid and canonical even when its archived run contains a retained truncated generation.

## 11. Duplicate and Orphan Artifacts

The archived v1.1 run set contains one later duplicate valid run.

The final analyzer automatically identifies this run after validating its manifest and artifacts.

It is retained for transparency but excluded from the canonical analysis according to the earliest-valid-run rule.

The repository also retains one result/response pair under:

```text
results/downstream/excluded/orphan/
```

No valid v1.1 manifest references this pair.

It is therefore excluded from the manifest-based final audit and from the 672-record canonical publication dataset.

## 12. Deterministic and Downstream Results

The deterministic publication results are archived separately under:

```text
results/deterministic/pilot_results_v10.csv
results/deterministic/pilot_summary_v10.json
```

The downstream final publication results are:

```text
results/downstream/final/imic_v11_3seed_merged.csv
results/downstream/final/imic_v11_3seed_summary.json
```

These two result layers should remain analytically distinct.

The deterministic benchmark evaluates exchange-method behavior under fully controlled synthetic execution.

The downstream experiment additionally evaluates business-task outputs produced by local language models after the governed exchange decision.

## 13. Optional Cleanup

After completing the verification, leave the repository itself unchanged and remove only the temporary workspace.

For example:

```bash
cd "$REPO_ROOT"
rm -rf "$WORK_DIR"
```

## 14. Reproduction Criterion

The archived publication artifacts are considered successfully reproduced when all of the following conditions hold:

- `python3 imic_v10.py --test` completes with all 10 tests passing;
- `resume_v11.py` reports 24/24 canonical runs, zero missing runs, and one duplicate valid run;
- `imic_v11_analyze_3seed.py` completes with `FINAL AUDIT COMPLETE`;
- the audit contains exactly 672 method-level records and 168 case--model--seed blocks; and
- the reconstructed merged CSV and summary JSON are byte-for-byte identical to the corresponding files under `results/downstream/final/`.

This procedure verifies the archived publication artifacts and reported aggregation without generating new language-model responses.
