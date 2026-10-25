
#!/usr/bin/env python3
# imic_v11_ollama.py
#
# IMIC v1.1: Ollama integration with the frozen v1.0 benchmark.
#
# Python >= 3.10; standard library only.
# Does not modify v1.0 inputs, oracle, or source code.
#
# Examples:
#   python imic_v11_ollama.py --self-test
#   python imic_v11_ollama.py --dry-run
#   python imic_v11_ollama.py --models --url URL
#   python imic_v11_ollama.py --run --model MODEL --url URL
#
# Contract decisions and model task outcomes are scored separately.

import argparse
import copy
import csv
import hashlib
import json
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from imic_v10_core import simulate
from imic_v10 import ROOT, METHODS, load_frozen, evaluate


VERSION = "IMIC-OLLAMA-1.1.0"

DEFAULT_CASES = (
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

RESULT_LABELS = (
    "available",
    "unavailable",
    "out_of_stock",
    "quoted",
    "invalid_context",
)

RESULT_SCHEMA = {
    "type": "object",
    "properties": {
        "result": {
            "type": "string",
            "enum": list(RESULT_LABELS),
        }
    },
    "required": ["result"],
    "additionalProperties": False,
}

# Common authoritative business reference.
# This reference is held constant across B1--B4.
# It is NOT the benchmark oracle.
BUSINESS_REFERENCE = {
    "inventory": [
        {
            "product_id": "SKU-0042",
            "fulfillment_region": "JP-13",
            "available_pieces": 5,
        }
    ]
}

SYSTEM_PROMPT = (
    "You are the downstream business-task component of a "
    "synthetic enterprise workflow. "
    "Use the provided transferred context and common business "
    "reference to perform the requested task. "
    "Do not assume missing task fields or invent facts. "
    "If required context is insufficient or semantically invalid, "
    "return invalid_context. "
    "For inventory_availability, return available when the "
    "requested quantity of individual pieces is in stock, "
    "or unavailable when there is insufficient stock. "
    "For logistics_quotation, return quoted when the request "
    "is valid and the requested product quantity is available; "
    "otherwise return unavailable. "
    "The requesting context may use structured fact metadata. "
    "Interpret its value, unit, state and source qualifications "
    "when present. "
    "Return only a JSON object with one field named result. "
    "Allowed result labels: available, unavailable, "
    "out_of_stock, quoted, invalid_context."
)


def canonical_json(obj):
    return json.dumps(
        obj,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


def object_hash(obj):
    return sha256_bytes(
        canonical_json(obj).encode("utf-8")
    )


def file_hash(path):
    path = Path(path)
    if not path.is_file():
        return None
    return sha256_bytes(path.read_bytes())


def save_json(path, obj):
    Path(path).write_text(
        json.dumps(
            obj,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        ) + "\n",
        encoding="utf-8",
    )


def api_json(url, path, payload=None, timeout=180):
    endpoint = url.rstrip("/") + path

    if payload is None:
        request = urllib.request.Request(
            endpoint,
            method="GET",
        )
    else:
        request = urllib.request.Request(
            endpoint,
            data=json.dumps(
                payload,
                ensure_ascii=False,
            ).encode("utf-8"),
            headers={
                "Content-Type": "application/json"
            },
            method="POST",
        )

    try:
        with urllib.request.urlopen(
            request, timeout=timeout
        ) as response:
            return json.loads(
                response.read().decode("utf-8")
            )
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode(
            "utf-8", errors="replace"
        )[:1000]
        raise RuntimeError(
            f"HTTP {exc.code} at {endpoint}: {detail}"
        ) from exc


def ollama_metadata(url, model, timeout):
    version = api_json(
        url, "/api/version", timeout=timeout
    )
    tags = api_json(
        url, "/api/tags", timeout=timeout
    )

    models = tags.get("models", [])
    found = next(
        (
            entry for entry in models
            if entry.get("name") == model
            or entry.get("model") == model
        ),
        None,
    )

    if found is None:
        available = [
            entry.get("name", "")
            for entry in models
        ]
        raise ValueError(
            f"Model not found: {model}\n"
            f"Installed models: {available}"
        )

    return {
        "ollama_version": version.get("version"),
        "model": model,
        "model_digest": found.get("digest"),
        "model_details": found.get("details", {}),
    }


def parse_case_ids(text, inputs):
    if text.strip().upper() == "ALL":
        selected = sorted(inputs)
    else:
        selected = [
            part.strip()
            for part in text.split(",")
            if part.strip()
        ]

    if not selected:
        raise ValueError("No cases were selected")

    if len(set(selected)) != len(selected):
        raise ValueError("Duplicate case IDs")

    unknown = sorted(set(selected) - set(inputs))
    if unknown:
        raise ValueError(
            f"Unknown case IDs: {unknown}"
        )

    return selected


def prepare_jobs(inputs, oracle, selected):
    jobs = []

    for cid in selected:
        reference = oracle[cid]

        for method in METHODS:
            case = copy.deepcopy(inputs[cid])

            observed = simulate(
                method,
                copy.deepcopy(case),
            )

            # Independently check consistency with v0.9.
            deterministic = evaluate(
                method,
                copy.deepcopy(case),
                reference,
            )

            if (
                observed["action"]
                != deterministic["action"]
            ):
                raise RuntimeError(
                    "v1.0 action mismatch: "
                    f"{cid} {method}"
                )

            ab = observed["ab"]
            bc = observed["bc"]

            if not isinstance(ab, dict):
                raise TypeError(
                    f"{cid} {method}: AB must be a dict"
                )

            if not isinstance(bc, dict):
                raise TypeError(
                    f"{cid} {method}: BC must be a dict"
                )

            excess_ab = len(
                set(ab) - set(reference["allowed_ab"])
            )
            excess_bc = len(
                set(bc) - set(reference["allowed_bc"])
            )

            if (
                excess_ab != deterministic["excess_ab"]
                or excess_bc
                != deterministic["excess_bc"]
            ):
                raise RuntimeError(
                    "v1.0 exposure mismatch: "
                    f"{cid} {method}"
                )

            two_hop = (
                case.get("workflow") == "two_hop"
            )

            # Only the final delivered package is passed
            # to the downstream business model.
            package = bc if two_hop else ab

            task = (
                "logistics_quotation"
                if two_hop
                else "inventory_availability"
            )

            action = observed["action"]

            jobs.append({
                "case": cid,
                "family": case.get("family", ""),
                "method": method,
                "task": task,
                "action": action,
                "reason": str(
                    observed.get("reason", "")
                ),
                "package": copy.deepcopy(package),
                "ab_field_count": len(ab),
                "bc_field_count": len(bc),
                "excess_ab": excess_ab,
                "excess_bc": excess_bc,
                "acceptable_actions": list(
                    reference["acceptable_actions"]
                ),
                "expected_result": reference[
                    "expected_result"
                ],
            })

    return jobs


def make_messages(job):
    # Do not expose expected_result, the oracle,
    # baseline name, or correctness labels.
    user_payload = {
        "task": job["task"],
        "business_reference": BUSINESS_REFERENCE,
        "transferred_context": job["package"],
    }

    return [
        {
            "role": "system",
            "content": SYSTEM_PROMPT,
        },
        {
            "role": "user",
            "content": json.dumps(
                user_payload,
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            ),
        },
    ]


def make_request(job, args):
    return {
        "model": args.model,
        "messages": make_messages(job),
        "stream": False,
        "format": RESULT_SCHEMA,
        "options": {
            "temperature": args.temperature,
            "seed": args.seed,
            "num_predict": args.num_predict,
            "num_ctx": args.num_ctx,
        },
        # Deliberately omit "think".
        # The model uses its default Thinking behavior.
    }


def normalize_result(result, task):
    # Accept the conventional synonymous label
    # for an inventory shortage while preserving
    # the raw model output in the result file.
    if (
        task == "inventory_availability"
        and result == "out_of_stock"
    ):
        return "unavailable"

    return result


def classify_response(response, task):
    message = response.get("message") or {}
    content = message.get("content", "")
    done_reason = response.get("done_reason", "")

    basic = {
        "raw_content": content,
        "thinking_chars": len(
            message.get("thinking") or ""
        ),
        "done_reason": done_reason,
        "input_tokens": response.get(
            "prompt_eval_count"
        ),
        "output_tokens": response.get(
            "eval_count"
        ),
        "duration_ns": response.get(
            "total_duration"
        ),
    }

    if done_reason == "length":
        return {
            **basic,
            "status": "TRUNCATED",
            "raw_result": None,
            "normalized_result": None,
        }

    if not content or not content.strip():
        return {
            **basic,
            "status": "EMPTY_OUTPUT",
            "raw_result": None,
            "normalized_result": None,
        }

    try:
        parsed = json.loads(content)
    except (TypeError, ValueError):
        return {
            **basic,
            "status": "INVALID_JSON",
            "raw_result": None,
            "normalized_result": None,
        }

    if (
        not isinstance(parsed, dict)
        or set(parsed) != {"result"}
        or parsed["result"] not in RESULT_LABELS
    ):
        return {
            **basic,
            "status": "INVALID_SCHEMA",
            "raw_result": None,
            "normalized_result": None,
        }

    raw = parsed["result"]

    return {
        **basic,
        "status": "OK",
        "raw_result": raw,
        "normalized_result": normalize_result(
            raw, task
        ),
    }


def call_model(job, args):
    request = make_request(job, args)
    started = time.monotonic()

    try:
        response = api_json(
            args.url,
            "/api/chat",
            payload=request,
            timeout=args.timeout,
        )

        result = classify_response(
            response,
            job["task"],
        )
        result["error"] = ""

    except Exception as exc:
        result = {
            "status": "API_ERROR",
            "raw_result": None,
            "normalized_result": None,
            "raw_content": "",
            "thinking_chars": 0,
            "done_reason": "",
            "input_tokens": None,
            "output_tokens": None,
            "duration_ns": None,
            "error": (
                f"{type(exc).__name__}: {exc}"
            )[:1000],
        }

    result["elapsed_ms"] = round(
        (time.monotonic() - started) * 1000, 1
    )

    return result


def not_called():
    return {
        "status": "NOT_CALLED",
        "raw_result": None,
        "normalized_result": None,
        "raw_content": "",
        "thinking_chars": 0,
        "done_reason": "",
        "input_tokens": None,
        "output_tokens": None,
        "duration_ns": None,
        "elapsed_ms": 0,
        "error": "",
    }


def score(job, result):
    action = job["action"]
    expected = job["expected_result"]

    action_correct = (
        action in job["acceptable_actions"]
    )

    boundary_correct = (
        job["excess_ab"] == 0
        and job["excess_bc"] == 0
    )

    valid_model_output = (
        result["status"] == "OK"
    )

    # Business result is scored only when the
    # reference expects execution and the method
    # actually executes a downstream call.
    if expected is not None and action == "PROCEED":
        task_correct = (
            valid_model_output
            and result["normalized_result"] == expected
        )
    else:
        task_correct = None

    if expected is None:
        joint_correct = (
            action_correct
            and action != "PROCEED"
            and boundary_correct
            and result["status"] == "NOT_CALLED"
        )
    else:
        joint_correct = (
            action_correct
            and action == "PROCEED"
            and boundary_correct
            and task_correct is True
        )

    return {
        "action_correct": int(action_correct),
        "boundary_correct": int(boundary_correct),
        "task_correct": (
            ""
            if task_correct is None
            else int(task_correct)
        ),
        "joint_correct": int(joint_correct),
    }


FIELDNAMES = [
    "case",
    "family",
    "method",
    "model",
    "seed",
    "task",
    "action",
    "reason",
    "expected_result",
    "status",
    "raw_result",
    "normalized_result",
    "action_correct",
    "boundary_correct",
    "task_correct",
    "joint_correct",
    "ab_field_count",
    "bc_field_count",
    "excess_ab",
    "excess_bc",
    "input_tokens",
    "output_tokens",
    "thinking_chars",
    "done_reason",
    "duration_ns",
    "elapsed_ms",
    "prompt_sha256",
    "error",
]


def create_row(job, result, args, prompt_hash):
    graded = score(job, result)

    return {
        "case": job["case"],
        "family": job["family"],
        "method": job["method"],
        "model": args.model,
        "seed": args.seed,
        "task": job["task"],
        "action": job["action"],
        "reason": job["reason"],
        "expected_result": (
            job["expected_result"]
            if job["expected_result"] is not None
            else "NO_EXECUTION"
        ),
        "status": result["status"],
        "raw_result": result["raw_result"] or "",
        "normalized_result": (
            result["normalized_result"] or ""
        ),
        **graded,
        "ab_field_count": job["ab_field_count"],
        "bc_field_count": job["bc_field_count"],
        "excess_ab": job["excess_ab"],
        "excess_bc": job["excess_bc"],
        "input_tokens": (
            result["input_tokens"]
            if result["input_tokens"] is not None
            else ""
        ),
        "output_tokens": (
            result["output_tokens"]
            if result["output_tokens"] is not None
            else ""
        ),
        "thinking_chars": result["thinking_chars"],
        "done_reason": result["done_reason"],
        "duration_ns": (
            result["duration_ns"]
            if result["duration_ns"] is not None
            else ""
        ),
        "elapsed_ms": result["elapsed_ms"],
        "prompt_sha256": prompt_hash,
        "error": result["error"],
    }


def summarize(rows, selected):
    print("\nRESULTS")
    print("Comparison records:", len(rows))

    statuses = sorted({
        row["status"] for row in rows
    })

    for status in statuses:
        count = sum(
            row["status"] == status
            for row in rows
        )
        print(f"  {status}: {count}")

    print()
    print(
        f"{'Method':<8}"
        f"{'Joint':>9}"
        f"{'Action':>10}"
        f"{'Boundary':>11}"
        f"{'Model OK':>11}"
    )

    for method in METHODS:
        subset = [
            row for row in rows
            if row["method"] == method
        ]

        joint = sum(
            row["joint_correct"]
            for row in subset
        )
        action = sum(
            row["action_correct"]
            for row in subset
        )
        boundary = sum(
            row["boundary_correct"]
            for row in subset
        )
        completed = sum(
            row["status"] == "OK"
            for row in subset
        )

        print(
            f"{method:<8}"
            f"{joint:>5}/{len(subset):<3}"
            f"{action:>6}/{len(subset):<3}"
            f"{boundary:>7}/{len(subset):<3}"
            f"{completed:>7}"
        )

    incomplete = []

    for cid in selected:
        block = [
            row for row in rows
            if row["case"] == cid
        ]

        if (
            len(block) != len(METHODS)
            or any(
                row["status"]
                not in ("OK", "NOT_CALLED")
                for row in block
            )
        ):
            incomplete.append(cid)

    print("\nComplete paired cases:",
          len(selected) - len(incomplete),
          "/", len(selected))

    if incomplete:
        print("Incomplete cases:", incomplete)
        print(
            "Do not use these cases for a "
            "complete paired comparison."
        )

    return incomplete


def print_plan(jobs):
    calls = sum(
        job["action"] == "PROCEED"
        for job in jobs
    )

    print("IMIC v1.1 dry-run")
    print("Cases:", len(jobs) // len(METHODS))
    print("Comparison records:", len(jobs))
    print("Planned Ollama calls:", calls)
    print()

    print(
        f"{'Case':<7}"
        f"{'Method':<8}"
        f"{'Action':<15}"
        f"{'Task':<25}"
        f"{'Fields':>7}"
    )

    for job in jobs:
        print(
            f"{job['case']:<7}"
            f"{job['method']:<8}"
            f"{job['action']:<15}"
            f"{job['task']:<25}"
            f"{len(job['package']):>7}"
        )

    print(
        "\nNo model was called. "
        "No experimental result was created."
    )


def source_hashes():
    here = Path(__file__).resolve().parent

    names = (
        "imic_v11_ollama.py",
        "imic_v10.py",
        "imic_v10_core.py",
        "imic_proto.py",
        "imic_v03.py",
        "imic_v04.py",
        "imic_schema_v04.py",
        "imic_demo/benchmark_inputs_v10.json",
        "imic_demo/benchmark_oracle_v10.json",
        "imic_demo/benchmark_lock_v10.json",
    )

    return {
        name: file_hash(here / name)
        for name in names
    }


def run_experiment(args, jobs, selected):
    planned_calls = sum(
        job["action"] == "PROCEED"
        for job in jobs
    )

    if planned_calls > args.max_calls:
        raise ValueError(
            f"Planned calls: {planned_calls}. "
            f"Max calls: {args.max_calls}. "
            "Increase --max-calls deliberately."
        )

    metadata = ollama_metadata(
        args.url,
        args.model,
        args.timeout,
    )

    output_dir = Path(args.output_dir)
    output_dir.mkdir(
        parents=True, exist_ok=True
    )

    stamp = datetime.now(
        timezone.utc
    ).strftime("%Y%m%d_%H%M%S_%f")

    prefix = f"v11_ollama_{stamp}"

    csv_path = output_dir / (
        f"llm_results_{prefix}.csv"
    )
    log_path = output_dir / (
        f"llm_responses_{prefix}.jsonl"
    )
    manifest_path = output_dir / (
        f"llm_manifest_{prefix}.json"
    )

    rows = []
    api_attempts = 0

    with (
        csv_path.open(
            "w", encoding="utf-8", newline=""
        ) as csv_file,
        log_path.open(
            "w", encoding="utf-8"
        ) as log_file,
    ):
        writer = csv.DictWriter(
            csv_file,
            fieldnames=FIELDNAMES,
        )
        writer.writeheader()

        for job in jobs:
            request = make_request(job, args)
            prompt_hash = object_hash(
                request["messages"]
            )

            if job["action"] == "PROCEED":
                api_attempts += 1
                result = call_model(job, args)
            else:
                result = not_called()

            row = create_row(
                job, result, args, prompt_hash
            )
            writer.writerow(row)
            csv_file.flush()
            rows.append(row)

            # Store the transmitted prompt and raw response
            # for reproducibility and error analysis.
            log_file.write(
                json.dumps(
                    {
                        "case": job["case"],
                        "method": job["method"],
                        "request": (
                            request
                            if job["action"] == "PROCEED"
                            else None
                        ),
                        "status": result["status"],
                        "raw_content": result[
                            "raw_content"
                        ],
                        "thinking_chars": result[
                            "thinking_chars"
                        ],
                        "done_reason": result[
                            "done_reason"
                        ],
                        "error": result["error"],
                    },
                    ensure_ascii=False,
                ) + "\n"
            )
            log_file.flush()

            label = (
                row["normalized_result"]
                if row["status"] == "OK"
                else row["status"]
            )

            print(
                job["case"],
                job["method"],
                job["action"],
                label,
                "Joint=" + str(
                    row["joint_correct"]
                ),
                flush=True,
            )

    incomplete = summarize(rows, selected)

    manifest = {
        "version": VERSION,
        "created_at_utc": datetime.now(
            timezone.utc
        ).isoformat(),
        "run_status": (
            "COMPLETE"
            if not incomplete
            else "INCOMPLETE"
        ),
        "model": args.model,
        "model_digest": metadata[
            "model_digest"
        ],
        "model_details": metadata[
            "model_details"
        ],
        "ollama_version": metadata[
            "ollama_version"
        ],
        "url": args.url,
        "cases": selected,
        "methods": list(METHODS),
        "generation_options": {
            "temperature": args.temperature,
            "seed": args.seed,
            "num_predict": args.num_predict,
            "num_ctx": args.num_ctx,
            "think": "omitted_model_default",
        },
        "response_schema": RESULT_SCHEMA,
        "business_reference": BUSINESS_REFERENCE,
        "planned_calls": planned_calls,
        "api_attempts": api_attempts,
        "comparison_records": len(rows),
        "incomplete_cases": incomplete,
        "status_counts": {
            status: sum(
                row["status"] == status
                for row in rows
            )
            for status in sorted({
                row["status"] for row in rows
            })
        },
        "source_sha256": source_hashes(),
        "results_file": csv_path.name,
        "results_sha256": file_hash(csv_path),
        "response_log_file": log_path.name,
        "response_log_sha256": file_hash(log_path),
    }

    save_json(manifest_path, manifest)

    print("\nCSV:", csv_path)
    print("Responses:", log_path)
    print("Manifest:", manifest_path)

    if incomplete:
        raise SystemExit(
            "Run completed with incomplete paired blocks"
        )


def self_test(inputs, oracle):
    cases = (
        "S101",
        "S105",
        "S401",
        "S402",
        "S403",
        "S404",
        "S405",
        "S406",
        "S407",
        "S408",
    )

    jobs = prepare_jobs(
        inputs, oracle, cases
    )

    assert len(jobs) == 40

    lookup = {
        (j["case"], j["method"]): j
        for j in jobs
    }

    expected_reasons = {
        "S401": "ORIGIN_ONWARD_PROHIBITED",
        "S403": "ORIGIN_RECIPIENT_PROHIBITED",
        "S405": "ORIGIN_PURPOSE_PROHIBITED",
        "S407": "ORIGIN_FIELD_SCOPE_PROHIBITED",
    }

    for cid, expected_reason in (
        expected_reasons.items()
    ):
        assert lookup[
            (cid, "B4")
        ]["action"] == "REJECT"

        assert lookup[
            (cid, "B4")
        ]["reason"] == expected_reason

        # B3 deliberately does not enforce the
        # originating restrictions.
        assert lookup[
            (cid, "B3")
        ]["action"] == "PROCEED"

    for cid in (
        "S402",
        "S404",
        "S406",
        "S408",
    ):
        assert lookup[
            (cid, "B4")
        ]["action"] == "PROCEED"

    assert lookup[
        ("S101", "B4")
    ]["action"] == "PROCEED"

    for job in jobs:
        messages = make_messages(job)
        payload = messages[1]["content"]

        assert "expected_result" not in payload
        assert "acceptable_actions" not in payload
        assert '"method"' not in payload

    # Test scoring without any model call.
    for cid in expected_reasons:
        denied = lookup[(cid, "B4")]
        result = score(
            denied,
            not_called(),
        )

        assert result["action_correct"] == 1
        assert result["joint_correct"] == 1

    # An executed task requires a valid model response.
    normal = lookup[("S101", "B4")]
    valid = {
        **not_called(),
        "status": "OK",
        "normalized_result": "available",
    }

    assert score(
        normal, valid
    )["joint_correct"] == 1

    print(
        "v1.1 self-test OK:",
        "40 planned comparisons;",
        "four originating-constraint classes;",
        "no Ollama calls."
    )


def main():
    parser = argparse.ArgumentParser()

    mode = parser.add_mutually_exclusive_group(
        required=True
    )
    mode.add_argument(
        "--self-test", action="store_true"
    )
    mode.add_argument(
        "--dry-run", action="store_true"
    )
    mode.add_argument(
        "--run", action="store_true"
    )
    mode.add_argument(
        "--models", action="store_true"
    )

    parser.add_argument(
        "--cases",
        default=",".join(DEFAULT_CASES),
    )
    parser.add_argument(
        "--model",
        default="qwen3.5:9b-q4_K_M",
    )
    parser.add_argument(
        "--url",
        default="http://127.0.0.1:11434",
    )
    parser.add_argument(
        "--seed", type=int, default=101
    )
    parser.add_argument(
        "--temperature",
        type=float, default=0.7
    )
    parser.add_argument(
        "--num-predict",
        type=int, default=3072
    )
    parser.add_argument(
        "--num-ctx",
        type=int, default=4096
    )
    parser.add_argument(
        "--timeout",
        type=int, default=180
    )
    parser.add_argument(
        "--max-calls",
        type=int, default=64
    )
    parser.add_argument(
        "--output-dir",
        default=str(ROOT),
    )

    args = parser.parse_args()

    if args.models:
        version = api_json(
            args.url, "/api/version",
            timeout=args.timeout
        )
        tags = api_json(
            args.url, "/api/tags",
            timeout=args.timeout
        )
        print("Ollama:", version.get("version"))
        for model in tags.get("models", []):
            print(
                model.get("name"),
                model.get("digest")
            )
        return

    inputs, oracle = load_frozen()

    if args.self_test:
        self_test(inputs, oracle)
        return

    selected = parse_case_ids(
        args.cases, inputs
    )
    jobs = prepare_jobs(
        inputs, oracle, selected
    )

    if args.dry_run:
        print_plan(jobs)
        return

    run_experiment(
        args, jobs, selected
    )


if __name__ == "__main__":
    main()
    
