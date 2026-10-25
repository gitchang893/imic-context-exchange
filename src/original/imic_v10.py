
# imic_v09.py
# IMIC v1.0: Expanded Originating-Constraint Benchmark
# Python >= 3.10; standard library only.
#
# Uses the v1.0 exchange simulator core.
# No Ollama calls are made.
#
# Usage:
#   python imic_v10.py --init
#   python imic_v10.py --test
#   python imic_v10.py --run

import argparse
import copy
import csv
import hashlib
import json
import unittest
from collections import Counter

from imic_proto import fact
from imic_v10_core import (
    ROOT,
    METHODS,
    make_cases as make_core_cases,
    simulate,
)


# ==================================================
# 1. Scenario definitions: 32 distinct conditions
# ==================================================

# id, group, mutation, quantity,
# two_hop, onward_permission, source_update

SCENARIOS = [
    # S1: Context sufficiency
    ("S101", "S1", "clean", 2, False, False, False),
    ("S102", "S1", "clean", 7, False, False, False),
    ("S103", "S1", "extra_history", 2, False, False, False),
    ("S104", "S1", "extra_account", 2, False, False, False),
    ("S105", "S1", "missing_product", 2, False, False, False),
    ("S106", "S1", "missing_quantity", 2, False, False, False),
    ("S107", "S1", "missing_region", 2, False, False, False),
    ("S108", "S1", "missing_eligibility", 2, False, False, False),

    # S2: Semantic continuity and provenance
    ("S201", "S2", "clean", 2, False, False, False),
    ("S202", "S2", "unit_six_pack", 2, False, False, False),
    ("S203", "S2", "ineligible", 2, False, False, False),
    ("S204", "S2", "missing_observed", 2, False, False, False),
    ("S205", "S2", "unit_carton", 2, False, False, False),
    ("S206", "S2", "provisional_eligibility", 2, False, False, False),
    ("S207", "S2", "future_observation", 2, False, False, False),
    ("S208", "S2", "extra_semantic_note", 2, False, False, False),

    # S3: Lifecycle and validity
    ("S301", "S3", "expired_product", 2, False, False, False),
    ("S302", "S3", "expired_quantity", 2, False, False, False),
    ("S303", "S3", "expired_region", 2, False, False, False),
    ("S304", "S3", "expired_eligibility", 2, False, False, False),
    ("S305", "S3", "provisional_product", 2, False, False, False),
    ("S306", "S3", "provisional_eligibility", 2, False, False, False),
    ("S307", "S3", "clean", 2, True, True, True),
    ("S308", "S3", "clean", 3, True, False, True),

    # S4: Multi-hop originating constraints,
    # four matched constraint-class pairs.
    #
    # Legacy allow_onward remains True for all S4
    # cases so that the reviewed A->B contract has
    # general logistics onward capability. The
    # experimental distinction is represented by
    # originating_restrictions below.
    ("S401", "S4", "clean", 2, True, True, False),
    ("S402", "S4", "clean", 2, True, True, False),
    ("S403", "S4", "clean", 3, True, True, False),
    ("S404", "S4", "clean", 3, True, True, False),
    ("S405", "S4", "clean", 4, True, True, False),
    ("S406", "S4", "clean", 4, True, True, False),
    ("S407", "S4", "clean", 5, True, True, False),
    ("S408", "S4", "clean", 5, True, True, False),
]


S4_DEFAULT = {
    "onward_allowed": True,
    "allowed_onward_recipients": [
        "logistics"
    ],
    "allowed_onward_purposes": [
        "fulfillment_quote"
    ],
    "allowed_onward_fields": [
        "product_id",
        "quantity",
        "fulfillment_region",
    ],
}


S4_RESTRICTIONS = {
    # Pair 1: general onward-transfer permission
    "S401": {
        **S4_DEFAULT,
        "onward_allowed": False,
    },
    "S402": {
        **S4_DEFAULT,
        "onward_allowed": True,
    },

    # Pair 2: permitted onward recipient
    "S403": {
        **S4_DEFAULT,
        "allowed_onward_recipients": [
            "other_service"
        ],
    },
    "S404": {
        **S4_DEFAULT,
        "allowed_onward_recipients": [
            "logistics"
        ],
    },

    # Pair 3: permitted onward purpose
    "S405": {
        **S4_DEFAULT,
        "allowed_onward_purposes": [
            "inventory_analysis"
        ],
    },
    "S406": {
        **S4_DEFAULT,
        "allowed_onward_purposes": [
            "fulfillment_quote"
        ],
    },

    # Pair 4: permitted onward field scope
    "S407": {
        **S4_DEFAULT,
        "allowed_onward_fields": [
            "product_id",
            "quantity",
        ],
    },
    "S408": {
        **S4_DEFAULT,
        "allowed_onward_fields": [
            "product_id",
            "quantity",
            "fulfillment_region",
        ],
    },
}


S4_CLASS = {
    "S401": "onward_permission",
    "S402": "onward_permission",
    "S403": "recipient",
    "S404": "recipient",
    "S405": "purpose",
    "S406": "purpose",
    "S407": "field_scope",
    "S408": "field_scope",
}


# ==================================================
# 2. Independently specified reference oracle
# ==================================================

# These are authored reference expectations.
# They are NOT calculated by simulate() or decide().
#
# Each row:
# id, acceptable actions, expected business outcome,
# whether a B->C field transfer is permitted.
#
# An empty expected business result means execution
# should be deferred or prohibited.

REFERENCE_ROWS = [
    ("S101", "PROCEED", "available", False),
    ("S102", "PROCEED", "unavailable", False),
    ("S103", "PROCEED", "available", False),
    ("S104", "PROCEED", "available", False),
    ("S105", "REQUEST_MORE", None, False),
    ("S106", "REQUEST_MORE", None, False),
    ("S107", "REQUEST_MORE", None, False),
    ("S108", "REQUEST_MORE", None, False),

    ("S201", "PROCEED", "available", False),
    ("S202", "SUSPEND", None, False),
    ("S203", "SUSPEND", None, False),
    ("S204", "SUSPEND|REQUEST_MORE", None, False),
    ("S205", "SUSPEND", None, False),
    ("S206", "SUSPEND", None, False),
    ("S207", "SUSPEND", None, False),
    ("S208", "PROCEED", "available", False),

    ("S301", "SUSPEND", None, False),
    ("S302", "SUSPEND", None, False),
    ("S303", "SUSPEND", None, False),
    ("S304", "SUSPEND", None, False),
    ("S305", "SUSPEND", None, False),
    ("S306", "SUSPEND", None, False),
    ("S307", "SUSPEND", None, False),
    ("S308", "SUSPEND", None, False),

    ("S401", "REJECT", None, False),
    ("S402", "PROCEED", "quoted", True),
    ("S403", "REJECT", None, False),
    ("S404", "PROCEED", "quoted", True),
    ("S405", "REJECT", None, False),
    ("S406", "PROCEED", "quoted", True),
    ("S407", "REJECT", None, False),
    ("S408", "PROCEED", "quoted", True),
]

# Independent reference field permissions.
REF_ALLOWED_AB = [
    "product_id",
    "quantity",
    "fulfillment_region",
    "eligibility_status",
]

REF_ALLOWED_BC = [
    "product_id",
    "quantity",
    "fulfillment_region",
]


def make_oracle():
    oracle = {}

    for cid, actions, outcome, allow_bc in REFERENCE_ROWS:
        oracle[cid] = {
            "acceptable_actions": actions.split("|"),
            "expected_result": outcome,
            "allowed_ab": list(REF_ALLOWED_AB),
            "allowed_bc": (
                list(REF_ALLOWED_BC) if allow_bc else []
            ),
            "originating_constraint_class": (
                S4_CLASS.get(cid)
            ),
        }

    return oracle


# ==================================================
# 3. Construct synthetic benchmark inputs
# ==================================================

EXPIRED_AT = "2026-10-11T09:00:00Z"


def mutate_facts(facts, mutation):
    if mutation == "clean":
        return

    if mutation == "extra_history":
        facts["interaction_history"] = fact(
            "Unrelated synthetic customer conversation"
        )

    elif mutation == "extra_account":
        facts["unrelated_account_data"] = fact(
            "Unrelated synthetic account record"
        )

    elif mutation in (
            "missing_product",
            "missing_quantity",
            "missing_region",
            "missing_eligibility",
    ):
#
#     elif mutation.startswith("missing_"):
        field = {
            "missing_product": "product_id",
            "missing_quantity": "quantity",
            "missing_region": "fulfillment_region",
            "missing_eligibility": "eligibility_status",
        }[mutation]
        del facts[field]

    elif mutation in ("unit_six_pack", "unit_carton"):
        facts["quantity"]["unit"] = (
            "six_pack"
            if mutation == "unit_six_pack"
            else "carton"
        )

    elif mutation == "ineligible":
        facts["eligibility_status"]["value"] = "ineligible"

    elif mutation == "missing_observed":
        del facts["eligibility_status"]["observed_at"]

    elif mutation == "provisional_eligibility":
        facts["eligibility_status"][
            "information_state"
        ] = "provisional"

    elif mutation == "provisional_product":
        facts["product_id"][
            "information_state"
        ] = "provisional"

    elif mutation == "future_observation":
        facts["product_id"]["observed_at"] = (
            "2026-10-12T09:00:00Z"
        )
        facts["product_id"]["expires_at"] = (
            "2026-10-13T09:00:00Z"
        )

    elif mutation == "extra_semantic_note":
        facts["unrelated_semantic_note"] = fact(
            "Not required for inventory checking"
        )

    elif mutation.startswith("expired_"):
        field = {
            "expired_product": "product_id",
            "expired_quantity": "quantity",
            "expired_region": "fulfillment_region",
            "expired_eligibility": "eligibility_status",
        }[mutation]
        facts[field]["expires_at"] = EXPIRED_AT

    else:
        raise ValueError("Unknown mutation: " + mutation)


def make_inputs():
    baseline = make_core_cases()["C01"]
    cases = {}

    for (
        cid, group, mutation, quantity,
        two_hop, onward, source_update
    ) in SCENARIOS:
        case = copy.deepcopy(baseline)

        case["id"] = cid
        case["family"] = group
        case["mutation"] = mutation

        case["workflow"] = (
            "two_hop" if two_hop else "single_hop"
        )
        case["allow_onward"] = onward
        case["update_after_hop1"] = source_update

        if cid in S4_RESTRICTIONS:
            case["originating_restrictions"] = (
                copy.deepcopy(
                    S4_RESTRICTIONS[cid]
                )
            )

        facts = case["request"]["facts"]
        facts["quantity"]["value"] = quantity
        mutate_facts(facts, mutation)

        cases[cid] = case

    return cases


# ==================================================
# 4. Freeze inputs and reference oracle
# ==================================================

INPUT_FILE = ROOT / "benchmark_inputs_v10.json"
ORACLE_FILE = ROOT / "benchmark_oracle_v10.json"
LOCK_FILE = ROOT / "benchmark_lock_v10.json"


def digest(document):
    canonical = json.dumps(
        document,
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return hashlib.sha256(
        canonical.encode("utf-8")
    ).hexdigest()


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path, document):
    path.write_text(
        json.dumps(
            document,
            indent=2,
            sort_keys=True,
            ensure_ascii=False,
        ) + "\n",
        encoding="utf-8",
    )


def write_frozen(path, document):
    if path.exists():
        existing = read_json(path)
        if existing != document:
            raise RuntimeError(
                f"Frozen file differs: {path}\n"
                "Do not overwrite an existing benchmark. "
                "Create a new benchmark version instead."
            )
        return

    save_json(path, document)


def initialize():
    ROOT.mkdir(parents=True, exist_ok=True)

    inputs = make_inputs()
    oracle = make_oracle()

    lock = {
        "benchmark_version": "IMIC-BENCH-1.0",
        "reference_clock": "2026-10-11T10:00:00Z",
        "case_count": 32,
        "inputs_sha256": digest(inputs),
        "oracle_sha256": digest(oracle),
        "notes": (
            "Synthetic 32-condition benchmark with four "
            "explicit originating-constraint classes in "
            "the S4 two-hop family."
        ),
    }

    write_frozen(INPUT_FILE, inputs)
    write_frozen(ORACLE_FILE, oracle)
    write_frozen(LOCK_FILE, lock)

    print("Frozen inputs:", INPUT_FILE)
    print("Frozen oracle:", ORACLE_FILE)
    print("Benchmark lock:", LOCK_FILE)
    print("Cases:", len(inputs))


def load_frozen():
    for path in (INPUT_FILE, ORACLE_FILE, LOCK_FILE):
        if not path.is_file():
            raise FileNotFoundError(
                f"{path} is missing. Run --init first."
            )

    inputs = read_json(INPUT_FILE)
    oracle = read_json(ORACLE_FILE)
    lock = read_json(LOCK_FILE)

    if digest(inputs) != lock["inputs_sha256"]:
        raise ValueError("Benchmark input checksum mismatch")

    if digest(oracle) != lock["oracle_sha256"]:
        raise ValueError("Benchmark oracle checksum mismatch")

    expected_ids = {
        row[0] for row in SCENARIOS
    }

    if (
        len(inputs) != 32
        or set(inputs) != expected_ids
        or set(oracle) != expected_ids
    ):
        raise ValueError("Benchmark cases do not match")

    return inputs, oracle


# ==================================================
# 5. Evaluate a single method and case
# ==================================================

def evaluate(method, case, reference):
    observed = simulate(method, case)

    ab = observed["ab"]
    bc = observed["bc"]

    permitted_ab = set(reference["allowed_ab"])
    permitted_bc = set(reference["allowed_bc"])

    excess_ab = len(set(ab) - permitted_ab)
    excess_bc = len(set(bc) - permitted_bc)

    action = observed["action"]

    action_ok = (
        action in reference["acceptable_actions"]
    )

    expected = reference["expected_result"]
    actual = observed["task_result"]

    if expected is None:
        # Correct outcome requires no business task result.
        task_ok = None
        joint = (
            action_ok
            and actual is None
            and excess_ab == 0
            and excess_bc == 0
        )
    else:
        task_ok = (
            action == "PROCEED"
            and actual == expected
        )
        joint = (
            action_ok
            and task_ok
            and excess_ab == 0
            and excess_bc == 0
        )

    return {
        "case": case["id"],
        "family": case["family"],
        "mutation": case["mutation"],
        "originating_constraint_class": (
            reference.get(
                "originating_constraint_class"
            ) or ""
        ),
        "method": method,
        "action": action,
        "reason": observed["reason"],
        "expected_result": (
            expected if expected is not None else "NO_EXECUTION"
        ),
        "observed_result": (
            actual if actual is not None else "NOT_EXECUTED"
        ),
        "action_correct": int(action_ok),
        "task_correct": (
            "" if task_ok is None else int(task_ok)
        ),
        "joint_correct": int(joint),
        "ab_field_count": len(ab),
        "bc_field_count": len(bc),
        "excess_ab": excess_ab,
        "excess_bc": excess_bc,
        "excess_total": excess_ab + excess_bc,
    }


# ==================================================
# 6. Run all deterministic comparisons
# ==================================================

def run_benchmark():
    cases, oracle = load_frozen()

    rows = [
        evaluate(method, cases[cid], oracle[cid])
        for cid in sorted(cases)
        for method in METHODS
    ]

    if len(rows) != 128:
        raise AssertionError("Expected 128 comparisons")

    results_path = ROOT / "pilot_results_v10.csv"
    summary_path = ROOT / "pilot_summary_v10.json"

    with results_path.open(
        "w", newline="", encoding="utf-8"
    ) as handle:
        writer = csv.DictWriter(
            handle, fieldnames=list(rows[0])
        )
        writer.writeheader()
        writer.writerows(rows)

    summary = {
        "benchmark_version": "IMIC-BENCH-1.0",
        "cases": len(cases),
        "comparisons": len(rows),
        "overall": {},
        "by_family": {},
    }

    def metrics(items):
        return {
            "records": len(items),
            "joint_correct": sum(
                r["joint_correct"] for r in items
            ),
            "action_correct": sum(
                r["action_correct"] for r in items
            ),
            "excess_ab": sum(
                r["excess_ab"] for r in items
            ),
            "excess_bc": sum(
                r["excess_bc"] for r in items
            ),
        }

    for method in METHODS:
        summary["overall"][method] = metrics([
            r for r in rows if r["method"] == method
        ])

    for family in ("S1", "S2", "S3", "S4"):
        summary["by_family"][family] = {}

        for method in METHODS:
            subset = [
                r for r in rows
                if r["family"] == family
                and r["method"] == method
            ]
            summary["by_family"][family][method] = (
                metrics(subset)
            )

    save_json(summary_path, summary)

    print("Cases:", len(cases))
    print("Methods:", len(METHODS))
    print("Comparisons:", len(rows))
    print()

    print(
        f"{'Method':<8}"
        f"{'Joint':>10}"
        f"{'Action OK':>13}"
        f"{'Excess AB':>12}"
        f"{'Excess BC':>12}"
    )

    for method in METHODS:
        m = summary["overall"][method]

        print(
            f"{method:<8}"
            f"{m['joint_correct']:>6}/32"
            f"{m['action_correct']:>9}/32"
            f"{m['excess_ab']:>12}"
            f"{m['excess_bc']:>12}"
        )

    print("\nBY SCENARIO FAMILY")
    for family in ("S1", "S2", "S3", "S4"):
        print(f"\n{family}")
        for method in METHODS:
            m = summary["by_family"][family][method]
            print(
                f"  {method}: "
                f"Joint {m['joint_correct']}/8, "
                f"Action {m['action_correct']}/8, "
                f"Excess AB {m['excess_ab']}, "
                f"Excess BC {m['excess_bc']}"
            )

    print("\nCSV:", results_path)
    print("Summary:", summary_path)

    return rows


# ==================================================
# 7. Automated integrity and regression tests
# ==================================================

class IMICV10Tests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.cases, cls.oracle = load_frozen()

    def test_T32_thirty_two_cases(self):
        self.assertEqual(len(self.cases), 32)
        self.assertEqual(len(self.oracle), 32)

    def test_T33_eight_per_family(self):
        counts = Counter(
            c["family"] for c in self.cases.values()
        )
        self.assertEqual(
            dict(counts),
            {"S1": 8, "S2": 8, "S3": 8, "S4": 8}
        )

    def test_T34_complete_context(self):
        for method in METHODS:
            result = evaluate(
                method,
                self.cases["S101"],
                self.oracle["S101"]
            )
            self.assertEqual(result["joint_correct"], 1)

    def test_T35_missing_context(self):
        for method in ("B3", "B4"):
            for cid in ("S105", "S106", "S107", "S108"):
                result = evaluate(
                    method,
                    self.cases[cid],
                    self.oracle[cid]
                )
                self.assertEqual(result["action"], "REQUEST_MORE")

    def test_T36_semantic_unit_checks(self):
        for method in ("B3", "B4"):
            result = evaluate(
                method,
                self.cases["S202"],
                self.oracle["S202"]
            )
            self.assertEqual(result["action"], "SUSPEND")

    def test_T37_source_update_revalidation(self):
        for cid in ("S307", "S308"):
            for method in ("B3", "B4"):
                result = evaluate(
                    method,
                    self.cases[cid],
                    self.oracle[cid]
                )
                self.assertEqual(result["action"], "SUSPEND")

    def test_T38_originating_constraint_classes(self):
        expected_reasons = {
            "S401": "ORIGIN_ONWARD_PROHIBITED",
            "S403": "ORIGIN_RECIPIENT_PROHIBITED",
            "S405": "ORIGIN_PURPOSE_PROHIBITED",
            "S407": "ORIGIN_FIELD_SCOPE_PROHIBITED",
        }

        for cid, expected_reason in (
            expected_reasons.items()
        ):
            result = evaluate(
                "B4",
                self.cases[cid],
                self.oracle[cid]
            )

            self.assertEqual(
                result["action"], "REJECT"
            )
            self.assertEqual(
                result["reason"], expected_reason
            )
            self.assertEqual(
                result["joint_correct"], 1
            )

        for cid in (
            "S402", "S404", "S406", "S408"
        ):
            result = evaluate(
                "B4",
                self.cases[cid],
                self.oracle[cid]
            )

            self.assertEqual(
                result["action"], "PROCEED"
            )
            self.assertEqual(
                result["observed_result"], "quoted"
            )
            self.assertEqual(
                result["joint_correct"], 1
            )

    def test_T39_b3_does_not_enforce_originating_constraints(self):
        for cid in (
            "S401", "S403", "S405", "S407"
        ):
            result = evaluate(
                "B3",
                self.cases[cid],
                self.oracle[cid]
            )

            self.assertEqual(
                result["action"], "PROCEED"
            )

    def test_T40_s4_matched_pairs(self):
        for negative, positive in (
            ("S401", "S402"),
            ("S403", "S404"),
            ("S405", "S406"),
            ("S407", "S408"),
        ):
            a = self.cases[negative]
            b = self.cases[positive]

            self.assertEqual(
                a["request"], b["request"]
            )
            self.assertEqual(
                a["workflow"], b["workflow"]
            )
            self.assertEqual(
                a["update_after_hop1"],
                b["update_after_hop1"]
            )

    def test_T41_all_128_comparisons(self):
        rows = [
            evaluate(m, c, self.oracle[cid])
            for cid, c in self.cases.items()
            for m in METHODS
        ]

        self.assertEqual(len(rows), 128)
        self.assertEqual(
            len({
                (r["case"], r["method"])
                for r in rows
            }),
            128
        )


# ==================================================
# 8. Command-line interface
# ==================================================

def main():
    parser = argparse.ArgumentParser()

    mode = parser.add_mutually_exclusive_group(
        required=True
    )
    mode.add_argument("--init", action="store_true")
    mode.add_argument("--test", action="store_true")
    mode.add_argument("--run", action="store_true")

    args = parser.parse_args()

    if args.init:
        initialize()

    elif args.test:
        suite = unittest.defaultTestLoader.loadTestsFromTestCase(
            IMICV10Tests
        )
        outcome = unittest.TextTestRunner(
            verbosity=2
        ).run(suite)

        if not outcome.wasSuccessful():
            raise SystemExit(1)

    elif args.run:
        run_benchmark()


if __name__ == "__main__":
    main()
    
