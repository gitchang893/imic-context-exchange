from pathlib import Path
import hashlib
import json

ROOT = Path("imic_demo")

GROUPS = {
    "A": [
        "S101", "S105", "S202", "S206",
        "S301", "S307", "S401", "S402",
    ],
    "B": [
        "S403", "S404", "S405",
        "S406", "S407", "S408",
    ],
}

MODELS = (
    "qwen3.5:9b-q4_K_M",
    "gemma4:12b",
    "llama3.1:8b",
    "phi4:14b",
)

SEEDS = (101, 202, 303)


def digest(path):
    return hashlib.sha256(
        path.read_bytes()
    ).hexdigest()


def group_of(cases):
    for name, expected in GROUPS.items():
        if cases == expected:
            return name
    return None


valid = []
invalid = []

for mp in sorted(
    ROOT.glob("llm_manifest_v11_ollama_*.json")
):
    try:
        m = json.loads(
            mp.read_text(encoding="utf-8")
        )

        if m.get("version") != "IMIC-OLLAMA-1.1.0":
            invalid.append(
                (mp.name, "wrong version")
            )
            continue

        model = m["model"]
        seed = int(
            m["generation_options"]["seed"]
        )
        cases = m["cases"]
        group = group_of(cases)

        if group is None:
            invalid.append(
                (mp.name, "unexpected cases")
            )
            continue

        expected_records = (
            32 if group == "A" else 24
        )

        if m.get("comparison_records") != expected_records:
            invalid.append(
                (
                    mp.name,
                    "unexpected comparison_records",
                )
            )
            continue

        csv_path = ROOT / m["results_file"]
        log_path = ROOT / m["response_log_file"]

        if not csv_path.is_file():
            invalid.append(
                (mp.name, "results CSV missing")
            )
            continue

        if not log_path.is_file():
            invalid.append(
                (mp.name, "response log missing")
            )
            continue

        if (
            digest(csv_path)
            != m["results_sha256"]
        ):
            invalid.append(
                (mp.name, "results checksum mismatch")
            )
            continue

        if (
            digest(log_path)
            != m["response_log_sha256"]
        ):
            invalid.append(
                (mp.name, "response checksum mismatch")
            )
            continue

        valid.append({
            "manifest": mp.name,
            "model": model,
            "seed": seed,
            "group": group,
            "status": m["run_status"],
            "statuses": m["status_counts"],
        })

    except Exception as exc:
        invalid.append(
            (mp.name, f"{type(exc).__name__}: {exc}")
        )


# Earliest valid run is canonical.
canonical = {}
duplicates = []

for r in valid:
    key = (
        r["seed"],
        r["model"],
        r["group"],
    )

    if key not in canonical:
        canonical[key] = r
    else:
        duplicates.append(r)


print("=== CANONICAL VALID RUNS ===")

for key in sorted(canonical):
    r = canonical[key]
    print(
        f"seed={r['seed']} "
        f"model={r['model']} "
        f"group={r['group']} "
        f"status={r['status']} "
        f"{r['manifest']}"
    )


print("\n=== DUPLICATE VALID RUNS (ignored) ===")

if duplicates:
    for r in duplicates:
        print(
            f"seed={r['seed']} "
            f"model={r['model']} "
            f"group={r['group']} "
            f"{r['manifest']}"
        )
else:
    print("none")


print("\n=== INVALID / PARTIAL MANIFESTS ===")

if invalid:
    for name, reason in invalid:
        print(name, ":", reason)
else:
    print("none")


print("\n=== MISSING RUNS ===")

missing = []

for seed in SEEDS:
    for model in MODELS:
        for group in ("A", "B"):
            key = (seed, model, group)

            if key not in canonical:
                missing.append(key)
                print(
                    f"seed={seed} "
                    f"model={model} "
                    f"group={group}"
                )

print(
    f"\nCanonical: {len(canonical)}/24"
)
print(
    f"Missing:   {len(missing)}/24"
)
print(
    f"Duplicate: {len(duplicates)}"
)
