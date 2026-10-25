#!/usr/bin/env python3
# imic_v11_analyze_3seed.py
#
# Final audit:
# 4 models x 3 seeds x 14 cases x 4 methods
# = 672 method-level records
# = 168 case-model-seed paired blocks.
#
# This analyzer automatically discovers v1.1
# manifests, validates their associated result
# files, and selects the earliest valid run for
# each seed/model/group as canonical.
#
# Later duplicate valid runs are retained on disk
# but excluded from the canonical analysis.
#
# Standard library only.

import csv
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path

from imic_v10 import (
    ROOT,
    METHODS,
    load_frozen,
)


# ==================================================
# 1. Experiment definition
# ==================================================

ANALYZER_VERSION = "IMIC-ANALYZE-1.1.0"
EXPERIMENT_VERSION = "IMIC-OLLAMA-1.1.0"

SEEDS = (
    101,
    202,
    303,
)

MODELS = (
    "qwen3.5:9b-q4_K_M",
    "gemma4:12b",
    "llama3.1:8b",
    "phi4:14b",
)

CASES = (
    "S101",
    "S105",
    "S202",
    "S206",
    "S301",
    "S307",
    "S401",
    "S402",
    "S403",
    "S404",
    "S405",
    "S406",
    "S407",
    "S408",
)

GROUPS = {
    "A": (
        "S101",
        "S105",
        "S202",
        "S206",
        "S301",
        "S307",
        "S401",
        "S402",
    ),
    "B": (
        "S403",
        "S404",
        "S405",
        "S406",
        "S407",
        "S408",
    ),
}

EXPECTED_DIGESTS = {
    "qwen3.5:9b-q4_K_M":
        "6488c96fa5faab64bb65cbd30d4289e20e6130ef535a93ef9a49f42eda893ea7",
    "gemma4:12b":
        "4eb23ef187e2c5462566d6a1d3bbbc2f1346d0b4327cbb66d58fffbcc9b2b05c",
    "llama3.1:8b":
        "46e0c10c039e019119339687c3c1757cc81b9da49709a3b3924863ba87ca666e",
    "phi4:14b":
        "ac896e5b8b34a1f4efa7b14d7520725140d5512484457fab45d2a4ea14c69dba",
}

EXPECTED_OLLAMA_VERSION = "0.32.5"

EXPECTED_GENERATION_OPTIONS = {
    "temperature": 0.7,
    "num_predict": 3072,
    "num_ctx": 4096,
    "think": "omitted_model_default",
}

VALID_STATUSES = {
    "OK",
    "NOT_CALLED",
    "TRUNCATED",
    "EMPTY_OUTPUT",
    "INVALID_JSON",
    "INVALID_SCHEMA",
    "API_ERROR",
}

EXPECTED_ORIGIN_REASONS = {
    "S401": "ORIGIN_ONWARD_PROHIBITED",
    "S403": "ORIGIN_RECIPIENT_PROHIBITED",
    "S405": "ORIGIN_PURPOSE_PROHIBITED",
    "S407": "ORIGIN_FIELD_SCOPE_PROHIBITED",
}

ORIGINATING_CLASSES = {
    "S401": "onward_permission",
    "S402": "onward_permission",
    "S403": "recipient",
    "S404": "recipient",
    "S405": "purpose",
    "S406": "purpose",
    "S407": "field_scope",
    "S408": "field_scope",
}

EXPECTED_CANONICAL_MANIFESTS = (
    len(SEEDS)
    * len(MODELS)
    * len(GROUPS)
)

EXPECTED_RECORDS = (
    len(SEEDS)
    * len(MODELS)
    * len(CASES)
    * len(METHODS)
)

EXPECTED_PAIRED_BLOCKS = (
    len(SEEDS)
    * len(MODELS)
    * len(CASES)
)


# ==================================================
# 2. Basic utilities
# ==================================================

def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest(path):
    path = Path(path)

    return hashlib.sha256(
        path.read_bytes()
    ).hexdigest()


def canonical_json(obj):
    return json.dumps(
        obj,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def object_hash(obj):
    return hashlib.sha256(
        canonical_json(obj).encode("utf-8")
    ).hexdigest()


def read_json(path):
    return json.loads(
        Path(path).read_text(
            encoding="utf-8"
        )
    )


def read_csv(path):
    with Path(path).open(
        "r",
        encoding="utf-8",
        newline="",
    ) as handle:
        return list(
            csv.DictReader(handle)
        )


def group_of(cases):
    values = tuple(cases)

    for name, expected in GROUPS.items():
        if values == expected:
            return name

    return None


def expected_record_count(group):
    return (
        len(GROUPS[group])
        * len(METHODS)
    )


def score_count(rows, field):
    return sum(
        int(row[field])
        for row in rows
    )


def score_summary(rows):
    return {
        "n": len(rows),
        "joint": score_count(
            rows,
            "joint_correct",
        ),
        "action": score_count(
            rows,
            "action_correct",
        ),
        "boundary": score_count(
            rows,
            "boundary_correct",
        ),
    }


# ==================================================
# 3. Independent scoring re-check
# ==================================================

def verify_scoring(row, reference):
    action = row["action"]
    status = row["status"]

    action_correct = (
        action
        in reference[
            "acceptable_actions"
        ]
    )

    boundary_correct = (
        int(row["excess_ab"]) == 0
        and int(row["excess_bc"]) == 0
    )

    expected = reference[
        "expected_result"
    ]

    if (
        expected is not None
        and action == "PROCEED"
    ):
        task_correct = (
            status == "OK"
            and row[
                "normalized_result"
            ] == expected
        )
    else:
        task_correct = None

    if expected is None:
        joint_correct = (
            action_correct
            and action != "PROCEED"
            and boundary_correct
            and status == "NOT_CALLED"
        )
    else:
        joint_correct = (
            action_correct
            and action == "PROCEED"
            and boundary_correct
            and task_correct is True
        )

    require(
        int(row["action_correct"])
        == int(action_correct),
        "action_correct mismatch"
    )

    require(
        int(row["boundary_correct"])
        == int(boundary_correct),
        "boundary_correct mismatch"
    )

    if task_correct is None:
        require(
            row["task_correct"] == "",
            "task_correct should be blank"
        )
    else:
        require(
            int(row["task_correct"])
            == int(task_correct),
            "task_correct mismatch"
        )

    require(
        int(row["joint_correct"])
        == int(joint_correct),
        "joint_correct mismatch"
    )

    expected_text = (
        expected
        if expected is not None
        else "NO_EXECUTION"
    )

    require(
        row["expected_result"]
        == expected_text,
        "expected_result mismatch"
    )


# ==================================================
# 4. Validate one manifest and its artifacts
# ==================================================

def validate_manifest(mp):
    mp = Path(mp)
    manifest = read_json(mp)

    require(
        manifest.get("version")
        == EXPERIMENT_VERSION,
        f"Wrong experiment version: "
        f"{mp.name}"
    )

    model = manifest.get("model")

    require(
        model in MODELS,
        f"Unknown model: {mp.name}"
    )

    require(
        manifest.get("model_digest")
        == EXPECTED_DIGESTS[model],
        f"Model digest mismatch: "
        f"{mp.name}"
    )

    require(
        manifest.get("ollama_version")
        == EXPECTED_OLLAMA_VERSION,
        f"Ollama version mismatch: "
        f"{mp.name}"
    )

    options = manifest.get(
        "generation_options",
        {},
    )

    require(
        "seed" in options,
        f"Seed missing: {mp.name}"
    )

    seed = int(options["seed"])

    require(
        seed in SEEDS,
        f"Unexpected seed: {mp.name}"
    )

    expected_options = {
        **EXPECTED_GENERATION_OPTIONS,
        "seed": seed,
    }

    require(
        options == expected_options,
        f"Generation options mismatch: "
        f"{mp.name}"
    )

    require(
        manifest.get("methods")
        == list(METHODS),
        f"Method list mismatch: "
        f"{mp.name}"
    )

    cases = manifest.get(
        "cases",
        [],
    )

    group = group_of(cases)

    require(
        group is not None,
        f"Unexpected case set: "
        f"{mp.name}"
    )

    require(
        manifest.get(
            "comparison_records"
        )
        == expected_record_count(group),
        f"Comparison-record count mismatch: "
        f"{mp.name}"
    )

    require(
        manifest.get("run_status")
        in ("COMPLETE", "INCOMPLETE"),
        f"Unexpected run status: "
        f"{mp.name}"
    )

    csv_path = (
        ROOT
        / manifest["results_file"]
    )

    log_path = (
        ROOT
        / manifest[
            "response_log_file"
        ]
    )

    require(
        csv_path.is_file(),
        f"Missing result CSV: "
        f"{mp.name}"
    )

    require(
        log_path.is_file(),
        f"Missing response log: "
        f"{mp.name}"
    )

    require(
        digest(csv_path)
        == manifest[
            "results_sha256"
        ],
        f"CSV checksum mismatch: "
        f"{mp.name}"
    )

    require(
        digest(log_path)
        == manifest[
            "response_log_sha256"
        ],
        f"Response-log checksum mismatch: "
        f"{mp.name}"
    )

    rows = read_csv(
        csv_path
    )

    logs = [
        json.loads(line)
        for line in log_path.read_text(
            encoding="utf-8"
        ).splitlines()
        if line.strip()
    ]

    expected_n = (
        expected_record_count(group)
    )

    require(
        len(rows) == expected_n,
        f"Unexpected CSV length: "
        f"{mp.name}"
    )

    require(
        len(logs) == expected_n,
        f"Unexpected response-log length: "
        f"{mp.name}"
    )

    status_counts = Counter(
        row["status"]
        for row in rows
    )

    require(
        dict(status_counts)
        == manifest.get(
            "status_counts"
        ),
        f"Status-count mismatch: "
        f"{mp.name}"
    )

    return {
        "manifest_path": mp,
        "manifest": manifest,
        "model": model,
        "seed": seed,
        "group": group,
        "rows": rows,
        "logs": logs,
        "csv_path": csv_path,
        "log_path": log_path,
    }

# ==================================================
# 5. Discover and select canonical manifests
# ==================================================

def discover_manifests():
    paths = sorted(
        ROOT.glob(
            "llm_manifest_v11_ollama_*.json"
        )
    )

    require(
        paths,
        "No v1.1 manifest files found"
    )

    valid = []
    invalid = []

    for mp in paths:
        try:
            item = validate_manifest(mp)
            valid.append(item)

        except Exception as exc:
            invalid.append({
                "manifest": mp.name,
                "error": (
                    f"{type(exc).__name__}: "
                    f"{exc}"
                ),
            })

    return valid, invalid


def select_canonical(valid):
    canonical = {}
    duplicates = []

    for item in sorted(
        valid,
        key=lambda x: x[
            "manifest_path"
        ].name,
    ):
        key = (
            item["seed"],
            item["model"],
            item["group"],
        )

        if key not in canonical:
            canonical[key] = item
        else:
            duplicates.append(item)

    expected_keys = {
        (
            seed,
            model,
            group,
        )
        for seed in SEEDS
        for model in MODELS
        for group in GROUPS
    }

    missing = sorted(
        expected_keys
        - set(canonical)
    )

    require(
        len(canonical)
        == EXPECTED_CANONICAL_MANIFESTS,
        "Canonical manifest count mismatch: "
        f"{len(canonical)} != "
        f"{EXPECTED_CANONICAL_MANIFESTS}; "
        f"missing={missing}"
    )

    return canonical, duplicates


# ==================================================
# 6. Validate canonical records and logs
# ==================================================

def validate_canonical_records(
    canonical,
    oracle,
):
    records = {}
    manifests = []

    source_lock = None
    source_reference = None
    csv_schema = None

    for seed in SEEDS:
        for model in MODELS:
            for group in ("A", "B"):
                key = (
                    seed,
                    model,
                    group,
                )

                item = canonical[key]
                manifest = item[
                    "manifest"
                ]
                rows = item["rows"]
                logs = item["logs"]

                source_hashes = manifest.get(
                    "source_sha256"
                )

                require(
                    isinstance(
                        source_hashes,
                        dict,
                    ),
                    "source_sha256 must "
                    "be a dictionary: "
                    f"{item['manifest_path'].name}"
                )

                if source_lock is None:
                    source_lock = (
                        source_hashes
                    )
                    source_reference = (
                        item[
                            "manifest_path"
                        ].name
                    )
                else:
                    require(
                        source_hashes
                        == source_lock,
                        "Frozen source mismatch: "
                        f"{item['manifest_path'].name} "
                        f"vs {source_reference}"
                    )

                expected_cases = (
                    GROUPS[group]
                )

                require(
                    tuple(
                        manifest["cases"]
                    )
                    == expected_cases,
                    "Canonical case-set "
                    "mismatch: "
                    f"{item['manifest_path'].name}"
                )

                manifest_status = (
                    manifest[
                        "run_status"
                    ]
                )

                incomplete_cases = (
                    manifest.get(
                        "incomplete_cases",
                        [],
                    )
                )

                if (
                    manifest_status
                    == "COMPLETE"
                ):
                    require(
                        incomplete_cases == [],
                        "COMPLETE manifest has "
                        "incomplete cases: "
                        f"{item['manifest_path'].name}"
                    )

                if (
                    manifest_status
                    == "INCOMPLETE"
                ):
                    require(
                        len(
                            incomplete_cases
                        ) > 0,
                        "INCOMPLETE manifest "
                        "has no incomplete cases: "
                        f"{item['manifest_path'].name}"
                    )

                if csv_schema is None:
                    require(
                        len(rows) > 0,
                        "Empty canonical CSV"
                    )
                    csv_schema = set(
                        rows[0]
                    )

                for row, log in zip(
                    rows,
                    logs,
                ):
                    require(
                        set(row)
                        == csv_schema,
                        "CSV schema mismatch: "
                        f"{item['manifest_path'].name}"
                    )

                    case = row["case"]
                    method = row["method"]

                    record_key = (
                        seed,
                        model,
                        case,
                        method,
                    )

                    require(
                        record_key
                        not in records,
                        "Duplicate canonical "
                        f"record: {record_key}"
                    )

                    require(
                        case
                        in expected_cases,
                        "Unexpected case in "
                        f"canonical run: "
                        f"{record_key}"
                    )

                    require(
                        method in METHODS,
                        "Unexpected method: "
                        f"{record_key}"
                    )

                    require(
                        row["model"]
                        == model,
                        "CSV model mismatch: "
                        f"{record_key}"
                    )

                    require(
                        int(row["seed"])
                        == seed,
                        "CSV seed mismatch: "
                        f"{record_key}"
                    )

                    require(
                        row["status"]
                        in VALID_STATUSES,
                        "Unknown status: "
                        f"{record_key}"
                    )

                    require(
                        log["case"]
                        == case,
                        "Response-log case "
                        "mismatch: "
                        f"{record_key}"
                    )

                    require(
                        log["method"]
                        == method,
                        "Response-log method "
                        "mismatch: "
                        f"{record_key}"
                    )

                    require(
                        log["status"]
                        == row["status"],
                        "Response-log status "
                        "mismatch: "
                        f"{record_key}"
                    )

                    action = row[
                        "action"
                    ]

                    if action == "PROCEED":
                        require(
                            row["status"]
                            != "NOT_CALLED",
                            "Missing model "
                            "invocation: "
                            f"{record_key}"
                        )

                        require(
                            log[
                                "request"
                            ] is not None,
                            "Missing request "
                            "log: "
                            f"{record_key}"
                        )

                        request = log[
                            "request"
                        ]

                        require(
                            isinstance(
                                request,
                                dict,
                            ),
                            "Logged request "
                            "must be a dict: "
                            f"{record_key}"
                        )

                        require(
                            "messages"
                            in request,
                            "Logged request has "
                            "no messages: "
                            f"{record_key}"
                        )

                        prompt_hash = (
                            object_hash(
                                request[
                                    "messages"
                                ]
                            )
                        )

                        require(
                            prompt_hash
                            == row[
                                "prompt_sha256"
                            ],
                            "Prompt hash "
                            "mismatch: "
                            f"{record_key}"
                        )

                    else:
                        require(
                            row["status"]
                            == "NOT_CALLED",
                            "Non-PROCEED action "
                            "invoked model: "
                            f"{record_key}"
                        )

                        require(
                            log[
                                "request"
                            ] is None,
                            "Non-PROCEED action "
                            "has request log: "
                            f"{record_key}"
                        )

                    try:
                        verify_scoring(
                            row,
                            oracle[case],
                        )

                    except Exception as exc:
                        raise ValueError(
                            "Scoring mismatch "
                            f"for {record_key}: "
                            f"{exc}"
                        ) from exc

                    if (
                        case
                        in EXPECTED_ORIGIN_REASONS
                        and method == "B4"
                    ):
                        require(
                            row["action"]
                            == "REJECT",
                            "Originating "
                            "restriction did "
                            "not reject: "
                            f"{record_key}"
                        )

                        require(
                            row["reason"]
                            == EXPECTED_ORIGIN_REASONS[
                                case
                            ],
                            "Originating "
                            "restriction reason "
                            "mismatch: "
                            f"{record_key}"
                        )

                        require(
                            row["status"]
                            == "NOT_CALLED",
                            "Rejected originating "
                            "restriction invoked "
                            "the model: "
                            f"{record_key}"
                        )

                    records[
                        record_key
                    ] = row

                manifests.append({
                    "seed": seed,
                    "model": model,
                    "group": group,
                    "manifest": item[
                        "manifest_path"
                    ].name,
                    "manifest_sha256": digest(
                        item[
                            "manifest_path"
                        ]
                    ),
                    "run_status": manifest[
                        "run_status"
                    ],
                    "status_counts": manifest[
                        "status_counts"
                    ],
                })

    expected_record_keys = {
        (
            seed,
            model,
            case,
            method,
        )
        for seed in SEEDS
        for model in MODELS
        for case in CASES
        for method in METHODS
    }

    actual_record_keys = set(
        records
    )

    missing_records = (
        expected_record_keys
        - actual_record_keys
    )

    unexpected_records = (
        actual_record_keys
        - expected_record_keys
    )

    require(
        not missing_records,
        "Missing canonical records: "
        f"{sorted(missing_records)}"
    )

    require(
        not unexpected_records,
        "Unexpected canonical records: "
        f"{sorted(unexpected_records)}"
    )

    require(
        len(records)
        == EXPECTED_RECORDS,
        "Expected exactly "
        f"{EXPECTED_RECORDS} records, "
        f"got {len(records)}"
    )

    require(
        len(manifests)
        == EXPECTED_CANONICAL_MANIFESTS,
        "Expected exactly "
        f"{EXPECTED_CANONICAL_MANIFESTS} "
        "canonical manifests"
    )

    ordered = [
        records[
            (
                seed,
                model,
                case,
                method,
            )
        ]
        for seed in SEEDS
        for model in MODELS
        for case in CASES
        for method in METHODS
    ]

    require(
        len(ordered)
        == EXPECTED_RECORDS,
        "Ordered record count mismatch"
    )

    environment = {
        "ollama_version":
            EXPECTED_OLLAMA_VERSION,
        "source_sha256":
            source_lock,
        "generation_options_excluding_seed":
            EXPECTED_GENERATION_OPTIONS,
    }

    return (
        ordered,
        records,
        manifests,
        environment,
    )


# ==================================================
# 7. Analyze complete and incomplete blocks
# ==================================================

def analyze_blocks(
    rows,
    records,
):
    status_counts = dict(
        Counter(
            row["status"]
            for row in rows
        )
    )

    incomplete = []
    complete_keys = set()

    for seed in SEEDS:
        for model in MODELS:
            for case in CASES:
                block = [
                    records[
                        (
                            seed,
                            model,
                            case,
                            method,
                        )
                    ]
                    for method in METHODS
                ]

                block_key = (
                    seed,
                    model,
                    case,
                )

                if all(
                    row["status"]
                    in (
                        "OK",
                        "NOT_CALLED",
                    )
                    for row in block
                ):
                    complete_keys.add(
                        block_key
                    )

                else:
                    incomplete.append({
                        "seed": seed,
                        "model": model,
                        "case": case,
                        "statuses": {
                            row["method"]:
                                row["status"]
                            for row in block
                        },
                    })

    require(
        (
            len(complete_keys)
            + len(incomplete)
        )
        == EXPECTED_PAIRED_BLOCKS,
        "Paired-block count mismatch"
    )

    overall = {
        method: score_summary([
            row
            for row in rows
            if row["method"]
            == method
        ])
        for method in METHODS
    }

    complete_only = {
        method: score_summary([
            row
            for row in rows
            if (
                row["method"]
                == method
                and (
                    int(row["seed"]),
                    row["model"],
                    row["case"],
                )
                in complete_keys
            )
        ])
        for method in METHODS
    }

    return {
        "status_counts":
            status_counts,
        "complete_keys":
            complete_keys,
        "incomplete_blocks":
            incomplete,
        "overall":
            overall,
        "complete_only":
            complete_only,
    }

# ==================================================
# 8. Per-model, per-seed, and per-case summaries
# ==================================================

def analyze_model_seed(records):
    result = {}

    for seed in SEEDS:
        result[str(seed)] = {}

        for model in MODELS:
            result[str(seed)][model] = {
                method: score_summary([
                    records[
                        (
                            seed,
                            model,
                            case,
                            method,
                        )
                    ]
                    for case in CASES
                ])
                for method in METHODS
            }

    return result


def analyze_by_case(records):
    result = {}

    for case in CASES:
        result[case] = {
            method: score_summary([
                records[
                    (
                        seed,
                        model,
                        case,
                        method,
                    )
                ]
                for seed in SEEDS
                for model in MODELS
            ])
            for method in METHODS
        }

    return result


# ==================================================
# 9. Originating-constraint class analysis
# ==================================================

def analyze_originating_constraints(
    records,
):
    pairs = {
        "onward_permission": (
            "S401",
            "S402",
        ),
        "recipient": (
            "S403",
            "S404",
        ),
        "purpose": (
            "S405",
            "S406",
        ),
        "field_scope": (
            "S407",
            "S408",
        ),
    }

    summary = {}
    action_differences = []

    for constraint_class, (
        negative_case,
        positive_case,
    ) in pairs.items():

        negative_b3_joint = 0
        negative_b4_joint = 0
        positive_b3_joint = 0
        positive_b4_joint = 0

        negative_blocks = 0
        positive_blocks = 0

        for seed in SEEDS:
            for model in MODELS:
                b3_negative = records[
                    (
                        seed,
                        model,
                        negative_case,
                        "B3",
                    )
                ]

                b4_negative = records[
                    (
                        seed,
                        model,
                        negative_case,
                        "B4",
                    )
                ]

                b3_positive = records[
                    (
                        seed,
                        model,
                        positive_case,
                        "B3",
                    )
                ]

                b4_positive = records[
                    (
                        seed,
                        model,
                        positive_case,
                        "B4",
                    )
                ]

                # Negative member of each pair:
                # B3 intentionally lacks originating
                # restriction enforcement, whereas
                # B4 must reject before model use.
                require(
                    b3_negative["action"]
                    == "PROCEED",
                    "B3 unexpectedly enforced "
                    "originating restriction: "
                    f"{seed} {model} "
                    f"{negative_case}"
                )

                require(
                    b4_negative["action"]
                    == "REJECT",
                    "B4 failed to reject "
                    "originating restriction: "
                    f"{seed} {model} "
                    f"{negative_case}"
                )

                require(
                    b4_negative["reason"]
                    == EXPECTED_ORIGIN_REASONS[
                        negative_case
                    ],
                    "B4 originating-restriction "
                    "reason mismatch: "
                    f"{seed} {model} "
                    f"{negative_case}"
                )

                require(
                    b4_negative["status"]
                    == "NOT_CALLED",
                    "Rejected B4 case called "
                    "the downstream model: "
                    f"{seed} {model} "
                    f"{negative_case}"
                )

                action_differences.append({
                    "seed": seed,
                    "model": model,
                    "constraint_class":
                        constraint_class,
                    "case": negative_case,
                    "b3_action":
                        b3_negative[
                            "action"
                        ],
                    "b4_action":
                        b4_negative[
                            "action"
                        ],
                    "b4_reason":
                        b4_negative[
                            "reason"
                        ],
                })

                # Positive member of each pair:
                # both B3 and B4 should permit
                # downstream execution.
                require(
                    b3_positive["action"]
                    == "PROCEED",
                    "B3 positive paired case "
                    "did not proceed: "
                    f"{seed} {model} "
                    f"{positive_case}"
                )

                require(
                    b4_positive["action"]
                    == "PROCEED",
                    "B4 positive paired case "
                    "did not proceed: "
                    f"{seed} {model} "
                    f"{positive_case}"
                )

                negative_b3_joint += int(
                    b3_negative[
                        "joint_correct"
                    ]
                )

                negative_b4_joint += int(
                    b4_negative[
                        "joint_correct"
                    ]
                )

                positive_b3_joint += int(
                    b3_positive[
                        "joint_correct"
                    ]
                )

                positive_b4_joint += int(
                    b4_positive[
                        "joint_correct"
                    ]
                )

                negative_blocks += 1
                positive_blocks += 1

        require(
            negative_blocks == 12,
            "Expected 12 negative blocks "
            f"for {constraint_class}"
        )

        require(
            positive_blocks == 12,
            "Expected 12 positive blocks "
            f"for {constraint_class}"
        )

        summary[
            constraint_class
        ] = {
            "negative_case":
                negative_case,
            "positive_case":
                positive_case,
            "negative_blocks":
                negative_blocks,
            "positive_blocks":
                positive_blocks,
            "negative_b3_joint":
                negative_b3_joint,
            "negative_b4_joint":
                negative_b4_joint,
            "positive_b3_joint":
                positive_b3_joint,
            "positive_b4_joint":
                positive_b4_joint,
        }

    require(
        len(action_differences) == 48,
        "Expected exactly 48 B3/B4 "
        "originating-action differences, "
        f"got {len(action_differences)}"
    )

    class_counts = Counter(
        item["constraint_class"]
        for item in action_differences
    )

    require(
        dict(class_counts)
        == {
            "onward_permission": 12,
            "recipient": 12,
            "purpose": 12,
            "field_scope": 12,
        },
        "Originating-action differences "
        "are not balanced across the "
        "four constraint classes"
    )

    return (
        summary,
        action_differences,
    )


# ==================================================
# 10. General B3/B4 joint-score differences
# ==================================================

def analyze_b3_b4_joint_differences(
    records,
):
    differences = []

    for seed in SEEDS:
        for model in MODELS:
            for case in CASES:
                b3 = records[
                    (
                        seed,
                        model,
                        case,
                        "B3",
                    )
                ]

                b4 = records[
                    (
                        seed,
                        model,
                        case,
                        "B4",
                    )
                ]

                if (
                    int(
                        b3[
                            "joint_correct"
                        ]
                    )
                    != int(
                        b4[
                            "joint_correct"
                        ]
                    )
                ):
                    differences.append({
                        "seed": seed,
                        "model": model,
                        "case": case,
                        "originating_constraint_class":
                            ORIGINATING_CLASSES.get(
                                case,
                                "",
                            ),
                        "b3_joint": int(
                            b3[
                                "joint_correct"
                            ]
                        ),
                        "b4_joint": int(
                            b4[
                                "joint_correct"
                            ]
                        ),
                        "b3_action":
                            b3["action"],
                        "b4_action":
                            b4["action"],
                        "b3_status":
                            b3["status"],
                        "b4_status":
                            b4["status"],
                    })

    return differences


# ==================================================
# 11. Identical-prompt divergence analysis
# ==================================================

def analyze_identical_prompt_divergences(
    records,
):
    divergences = []

    for seed in SEEDS:
        for model in MODELS:
            for case in CASES:
                groups = defaultdict(
                    list
                )

                for method in METHODS:
                    row = records[
                        (
                            seed,
                            model,
                            case,
                            method,
                        )
                    ]

                    if (
                        row["status"]
                        == "OK"
                    ):
                        groups[
                            row[
                                "prompt_sha256"
                            ]
                        ].append(row)

                for (
                    prompt_hash,
                    group,
                ) in groups.items():

                    if len(group) < 2:
                        continue

                    answers = {
                        row[
                            "normalized_result"
                        ]
                        for row in group
                    }

                    if len(answers) > 1:
                        divergences.append({
                            "seed": seed,
                            "model": model,
                            "case": case,
                            "prompt_sha256":
                                prompt_hash,
                            "methods": [
                                row["method"]
                                for row
                                in group
                            ],
                            "answers": [
                                row[
                                    "normalized_result"
                                ]
                                for row
                                in group
                            ],
                        })

    return divergences


# ==================================================
# 12. Main final audit
# ==================================================

def main():
    inputs, oracle = load_frozen()

    require(
        set(CASES)
        <= set(inputs),
        "Selected cases missing from "
        "frozen benchmark inputs"
    )

    require(
        set(CASES)
        <= set(oracle),
        "Selected cases missing from "
        "frozen benchmark oracle"
    )

    valid, invalid = (
        discover_manifests()
    )

    canonical, duplicates = (
        select_canonical(valid)
    )

    (
        rows,
        records,
        manifests,
        environment,
    ) = validate_canonical_records(
        canonical,
        oracle,
    )

    block_analysis = analyze_blocks(
        rows,
        records,
    )

    model_seed = analyze_model_seed(
        records
    )

    by_case = analyze_by_case(
        records
    )

    (
        originating_summary,
        originating_action_differences,
    ) = analyze_originating_constraints(
        records
    )

    b3_b4_joint_differences = (
        analyze_b3_b4_joint_differences(
            records
        )
    )

    identical_prompt_divergences = (
        analyze_identical_prompt_divergences(
            records
        )
    )

    duplicate_summary = [
        {
            "seed": item["seed"],
            "model": item["model"],
            "group": item["group"],
            "manifest":
                item[
                    "manifest_path"
                ].name,
        }
        for item in duplicates
    ]

    result = {
        "analyzer_version":
            ANALYZER_VERSION,
        "experiment_version":
            EXPERIMENT_VERSION,
        "seeds":
            list(SEEDS),
        "models":
            list(MODELS),
        "cases":
            list(CASES),
        "methods":
            list(METHODS),
        "model_digests":
            EXPECTED_DIGESTS,
        "comparison_records":
            len(rows),
        "total_paired_blocks":
            EXPECTED_PAIRED_BLOCKS,
        "complete_paired_blocks":
            len(
                block_analysis[
                    "complete_keys"
                ]
            ),
        "incomplete_blocks":
            block_analysis[
                "incomplete_blocks"
            ],
        "status_counts":
            block_analysis[
                "status_counts"
            ],
        "overall":
            block_analysis[
                "overall"
            ],
        "complete_only":
            block_analysis[
                "complete_only"
            ],
        "model_seed":
            model_seed,
        "by_case":
            by_case,
        "originating_constraint_summary":
            originating_summary,
        "originating_action_differences":
            originating_action_differences,
        "b3_b4_joint_differences":
            b3_b4_joint_differences,
        "identical_prompt_divergences":
            identical_prompt_divergences,
        "environment":
            environment,
        "canonical_manifests":
            manifests,
        "duplicate_valid_manifests":
            duplicate_summary,
        "invalid_or_excluded_manifests":
            invalid,
    }

    print(
        "IMIC v1.1 FINAL / "
        "Seeds 101, 202, 303"
    )

    print(
        "Analyzer:",
        ANALYZER_VERSION,
    )

    print(
        "Canonical manifests:",
        len(manifests),
        "/",
        EXPECTED_CANONICAL_MANIFESTS,
    )

    print(
        "Duplicate valid manifests:",
        len(duplicates),
    )

    print(
        "Invalid/excluded manifests:",
        len(invalid),
    )

    print(
        "Comparison records:",
        len(rows),
    )

    print(
        "Ollama:",
        environment[
            "ollama_version"
        ],
    )

    print(
        "Statuses:",
        block_analysis[
            "status_counts"
        ],
    )

    print(
        "Complete paired blocks:",
        len(
            block_analysis[
                "complete_keys"
            ]
        ),
        "/",
        EXPECTED_PAIRED_BLOCKS,
    )

    print(
        "Incomplete blocks:",
        block_analysis[
            "incomplete_blocks"
        ],
    )

    print(
        "\nJOINT CORRECTNESS "
        "BY SEED AND MODEL"
    )

    for seed in SEEDS:
        print(
            "Seed",
            seed,
        )

        for model in MODELS:
            values = [
                (
                    f"{method}="
                    f"{model_seed[str(seed)][model][method]['joint']}"
                    f"/{model_seed[str(seed)][model][method]['n']}"
                )
                for method in METHODS
            ]

            print(
                " ",
                model,
                " ".join(values),
            )

    print(
        "\nOVERALL"
    )

    for (
        method,
        stats,
    ) in block_analysis[
        "overall"
    ].items():

        print(
            method,
            stats,
        )

    print(
        "\nCOMPLETE BLOCKS ONLY"
    )

    for (
        method,
        stats,
    ) in block_analysis[
        "complete_only"
    ].items():

        print(
            method,
            stats,
        )

    print(
        "\nORIGINATING CONSTRAINT "
        "CLASSES"
    )

    for (
        constraint_class,
        stats,
    ) in originating_summary.items():

        print(
            constraint_class,
            stats,
        )

    print(
        "\nORIGINATING B3/B4 "
        "ACTION DIFFERENCES:",
        len(
            originating_action_differences
        ),
    )

    counts = Counter(
        item[
            "constraint_class"
        ]
        for item
        in originating_action_differences
    )

    print(
        "By class:",
        dict(counts),
    )

    print(
        "\nALL B3/B4 "
        "JOINT DIFFERENCES:",
        len(
            b3_b4_joint_differences
        ),
    )

    for item in (
        b3_b4_joint_differences
    ):
        print(item)

    print(
        "\nIDENTICAL-PROMPT "
        "DIVERGENCES:",
        len(
            identical_prompt_divergences
        ),
    )

    for item in (
        identical_prompt_divergences
    ):
        print(item)

    print(
        "\nDUPLICATE VALID "
        "MANIFESTS"
    )

    if duplicate_summary:
        for item in (
            duplicate_summary
        ):
            print(item)
    else:
        print("none")

    print(
        "\nINVALID / EXCLUDED "
        "MANIFESTS"
    )

    if invalid:
        for item in invalid:
            print(item)
    else:
        print("none")

    merged_path = (
        ROOT
        / "imic_v11_3seed_merged.csv"
    )

    summary_path = (
        ROOT
        / "imic_v11_3seed_summary.json"
    )

    # Exclusive creation prevents accidental
    # replacement of an audited final result.
    with merged_path.open(
        "x",
        encoding="utf-8",
        newline="",
    ) as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=list(
                rows[0]
            ),
        )
        writer.writeheader()
        writer.writerows(rows)

    with summary_path.open(
        "x",
        encoding="utf-8",
    ) as handle:
        json.dump(
            result,
            handle,
            ensure_ascii=False,
            indent=2,
        )
        handle.write("\n")

    print(
        "\nMerged CSV:",
        merged_path,
    )

    print(
        "Summary JSON:",
        summary_path,
    )

    print(
        "FINAL AUDIT COMPLETE"
    )


if __name__ == "__main__":
    main()
    
