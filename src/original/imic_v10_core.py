
# imic_v06.py
# IMIC v0.6: Strong Baseline and Multi-hop Pilot
# Python >= 3.10

import argparse
import copy
import csv
import json
import unittest

from imic_proto import (
    NOW, ROOT, POLICY, valid_facts, fact,
    decide, as_time
)

from imic_v03 import (
    decide_onward, check_at_use, LOGISTICS_POLICY,
    request
)

from imic_v04 import (
    CUSTOMER_CONTRACT, LOGISTICS_CONTRACT,
    TEMPLATE_REGISTRY, make_template, contract_issues
)


AB_FIELDS = (
    "product_id", "quantity",
    "fulfillment_region", "eligibility_status"
)

BC_FIELDS = (
    "product_id", "quantity", "fulfillment_region"
)

META = {
    "source_id", "source_version", "observed_at",
    "expires_at", "information_state"
}

METHODS = ("B1", "B2", "B3", "B4")

# Simulated business service; independent of the
# contract validator and evaluation oracle.
INVENTORY = {
    "product_id": "SKU-0042",
    "region": "JP-13",
    "stock": 5
}


# -------------------------------------------------
# 1. Independently specified expected outcomes
# -------------------------------------------------

def expected(actions, result=None, allowed_bc=()):
    return {
        "allowed_actions": list(actions),
        "expected_result": result,
        "allowed_ab": list(AB_FIELDS),
        "allowed_bc": list(allowed_bc)
    }


ORACLE = {
    "C01": expected(["PROCEED"], "available"),
    "C02": expected(["PROCEED"], "unavailable"),
    "C03": expected(["PROCEED"], "available"),
    "C04": expected(["REQUEST_MORE"]),
    "C05": expected(["SUSPEND"]),
    "C06": expected(["REJECT", "RENEGOTIATE"]),
    "C07": expected(["REJECT"]),
    "C08": expected(["SUSPEND"]),
    "C09": expected(["SUSPEND"]),
    "C10": expected(["REJECT"]),
    "C11": expected(["PROCEED"], "quoted", BC_FIELDS),
    "C12": expected(["SUSPEND"])
}

# C07: independent enterprise policy prohibits
# transfer of eligibility_status.
ORACLE["C07"]["allowed_ab"] = list(BC_FIELDS)


# -------------------------------------------------
# 2. Reviewed multi-hop contract and template
# -------------------------------------------------

AB_DEFAULT = copy.deepcopy(CUSTOMER_CONTRACT)
BC_CONTRACT = copy.deepcopy(LOGISTICS_CONTRACT)

AB_ONWARD = copy.deepcopy(AB_DEFAULT)
AB_ONWARD["contract_id"] = "IMIC-CS-INV-ONWARD-002"
AB_ONWARD["version"] = 2
AB_ONWARD["template"] = {
    "id": "reviewed-inventory-onward",
    "version": 1
}
AB_ONWARD["onward_transfer"]["destinations"] = [
    "logistics"
]

# A newly approved template is required.
# Changing the instance alone is not sufficient.
REVIEWED_TEMPLATE = make_template(AB_ONWARD)

REGISTRY = dict(TEMPLATE_REGISTRY)
REGISTRY[(
    REVIEWED_TEMPLATE["template_id"],
    REVIEWED_TEMPLATE["template_version"]
)] = REVIEWED_TEMPLATE


# -------------------------------------------------
# 3. Synthetic source cases
# -------------------------------------------------

def make_cases():
    cases = {}

    for case_id in ORACLE:
        facts = valid_facts()
        policy = copy.deepcopy(POLICY)
        purpose = "replacement_inventory_check"

        if case_id == "C02":
            facts["quantity"]["value"] = 7

        elif case_id == "C03":
            facts["interaction_history"] = fact(
                "Unrelated synthetic conversation"
            )

        elif case_id == "C04":
            del facts["eligibility_status"]

        elif case_id == "C05":
            facts["eligibility_status"]["expires_at"] = (
                "2026-10-11T09:00:00Z"
            )

        elif case_id == "C06":
            purpose = "customer_analytics"

        elif case_id == "C07":
            policy["allowed_fields"].remove(
                "eligibility_status"
            )

        elif case_id == "C08":
            facts["quantity"]["unit"] = "six_pack"

        elif case_id == "C09":
            facts["eligibility_status"][
                "information_state"
            ] = "provisional"

        cases[case_id] = {
            "id": case_id,
            "workflow": (
                "two_hop" if case_id in
                ("C10", "C11", "C12")
                else "single_hop"
            ),
            "allow_onward": case_id == "C11",
            "update_after_hop1": case_id == "C12",
            "policy": policy,
            "request": request(facts, purpose=purpose)
        }

    return cases


# -------------------------------------------------
# 4. Common business functions
# -------------------------------------------------

def inventory_result(facts):
    try:
        if not set(AB_FIELDS) <= set(facts):
            return "missing_context"

        values = {
            name: facts[name]["value"]
            for name in AB_FIELDS
        }

        if (
            values["product_id"] != INVENTORY["product_id"]
            or values["fulfillment_region"]
                != INVENTORY["region"]
        ):
            return "invalid_reference"

        if values["eligibility_status"] != "eligible":
            return "ineligible"

        q = values["quantity"]

        if type(q) is not int or q <= 0:
            return "invalid_quantity"

        return (
            "available"
            if q <= INVENTORY["stock"]
            else "unavailable"
        )

    except (KeyError, TypeError):
        return "invalid_input"


def logistics_result(facts):
    try:
        if not set(BC_FIELDS) <= set(facts):
            return "missing_context"

        product = facts["product_id"]["value"]
        region = facts["fulfillment_region"]["value"]
        quantity = facts["quantity"]["value"]

        if (
            product != INVENTORY["product_id"]
            or region != INVENTORY["region"]
        ):
            return "invalid_reference"

        if type(quantity) is not int or quantity <= 0:
            return "invalid_quantity"

        return (
            "quoted"
            if quantity <= INVENTORY["stock"]
            else "out_of_stock"
        )

    except (KeyError, TypeError):
        return "invalid_input"


# -------------------------------------------------
# 5. Strong structured-handoff baseline
# -------------------------------------------------

def validate_b3(task_request, policy, fields):
    """
    B3 has meaningful local validation:
    scope, provenance, freshness, semantic units,
    and factual states.

    It intentionally has no originating-contract
    onward-transfer inheritance.
    """

    if (
        policy["status"] != "ACTIVE"
        or task_request["source"] != policy["source"]
        or task_request["destination"]
            != policy["destination"]
        or task_request["purpose"]
            not in policy["allowed_purposes"]
    ):
        return "REJECT", {}, "POLICY_OR_PURPOSE"

    if not set(fields) <= set(policy["allowed_fields"]):
        return "REJECT", {}, "FIELD_POLICY_DENIED"

    incoming = task_request["facts"]

    if not set(fields) <= set(incoming):
        return "REQUEST_MORE", {}, "MISSING_FIELD"

    selected = {}

    for name in fields:
        item = incoming[name]

        if not isinstance(item, dict):
            return "SUSPEND", {}, "INVALID_RECORD"

        if not META <= set(item) or "value" not in item:
            return "SUSPEND", {}, "INVALID_METADATA"

        try:
            observed = as_time(item["observed_at"])
            expires = as_time(item["expires_at"])
            current = as_time(NOW)
        except (ValueError, TypeError, AttributeError):
            return "SUSPEND", {}, "INVALID_TIME"

        if not observed <= current < expires:
            return "SUSPEND", {}, "STALE_RECORD"

        if (
            item["information_state"] != "confirmed"
            or type(item["source_version"]) is not int
            or item["source_version"] < 1
            or not isinstance(item["source_id"], str)
            or not item["source_id"]
        ):
            return "SUSPEND", {}, "INVALID_PROVENANCE_OR_STATE"

        if name == "quantity":
            if (
                item.get("unit") != "piece"
                or type(item["value"]) is not int
                or item["value"] <= 0
            ):
                return "SUSPEND", {}, "INVALID_QUANTITY_SEMANTICS"

        if (
            name == "eligibility_status"
            and item["value"] != "eligible"
        ):
            return "SUSPEND", {}, "INVALID_ELIGIBILITY"

        selected[name] = copy.deepcopy(item)

    return "APPROVE", selected, "STRUCTURED_VALIDATION"


def check_b3_at_use(facts, source_versions):
    """
    Fair positive control: B3 also has access to
    an authoritative source-version registry.
    """

    for item in facts.values():
        current = source_versions.get(item.get("source_id"))
        if current != item.get("source_version"):
            return False

    return True


# -------------------------------------------------
# 6. IMIC validation with template conformance
# -------------------------------------------------

def validate_b4(contract, policy, task_request):
    issues = contract_issues(contract, REGISTRY)

    if issues:
        return "REJECT", {}, ";".join(issues)

    first = decide(contract, policy, task_request, NOW)

    if first["decision"] == "TRANSFORM":
        projected = copy.deepcopy(task_request)
        projected["facts"] = first["package"]["facts"]

        second = decide(contract, policy, projected, NOW)

        if second["decision"] != "APPROVE":
            return (
                second["decision"], {},
                second["reason"]
            )

        return (
            "APPROVE",
            second["package"],
            "PROJECTED_AND_REVALIDATED"
        )

    if first["decision"] == "APPROVE":
        return (
            "APPROVE",
            first["package"],
            first["reason"]
        )

    return first["decision"], {}, first["reason"]


def state_after_hop1(case):
    return {
        "source_versions": {
            "CASE-001": (
                2 if case["update_after_hop1"] else 1
            )
        },
        "revoked_contracts": []
    }

# -------------------------------------------------
# 6b. Explicit originating restrictions for v1.0
# -------------------------------------------------

ORIGINATING_KEYS = {
    "onward_allowed",
    "allowed_onward_recipients",
    "allowed_onward_purposes",
    "allowed_onward_fields",
}


def evaluate_originating_restrictions(
    restrictions,
    onward_request,
):
    """
    Evaluate explicitly represented restrictions
    originating from the A->B information provider.

    The v1.0 benchmark tests four constraint classes:
    general onward permission, recipient, purpose,
    and field scope.

    This is intentionally limited to explicit two-hop
    constraints and is not a general policy-composition
    or conflict-resolution engine.
    """

    if restrictions is None:
        # Legacy v0.6 behavior.
        return True, "NO_EXPLICIT_V10_RESTRICTIONS"

    if not isinstance(restrictions, dict):
        return False, "ORIGIN_CONSTRAINT_INVALID"

    if not ORIGINATING_KEYS <= set(restrictions):
        return False, "ORIGIN_CONSTRAINT_INVALID"

    if restrictions["onward_allowed"] is not True:
        return False, "ORIGIN_ONWARD_PROHIBITED"

    recipients = restrictions[
        "allowed_onward_recipients"
    ]

    if (
        not isinstance(recipients, list)
        or onward_request["destination"]
        not in recipients
    ):
        return False, "ORIGIN_RECIPIENT_PROHIBITED"

    purposes = restrictions[
        "allowed_onward_purposes"
    ]

    if (
        not isinstance(purposes, list)
        or onward_request["purpose"]
        not in purposes
    ):
        return False, "ORIGIN_PURPOSE_PROHIBITED"

    allowed_fields = restrictions[
        "allowed_onward_fields"
    ]

    if not isinstance(allowed_fields, list):
        return False, "ORIGIN_CONSTRAINT_INVALID"

    proposed_fields = set(
        onward_request["facts"]
    )

    if not proposed_fields <= set(allowed_fields):
        return False, "ORIGIN_FIELD_SCOPE_PROHIBITED"

    return True, "ORIGIN_CONDITIONS_SATISFIED"


# -------------------------------------------------
# 7. End-to-end simulator
# -------------------------------------------------

def result(action, reason, ab=None, bc=None, task=None):
    return {
        "action": action,
        "reason": reason,
        "ab": ab if ab is not None else {},
        "bc": bc if bc is not None else {},
        "task_result": task
    }


def simulate(method, case):
    req_ab = copy.deepcopy(case["request"])
    policy_ab = case["policy"]
    source = req_ab["facts"]

#    contract_ab = (
#        AB_ONWARD if case["allow_onward"]
#        else AB_DEFAULT
#    )
    
    explicit_originating = case.get(
        "originating_restrictions"
    )

    contract_ab = (
        AB_ONWARD
        if explicit_originating is not None
        else (
                AB_ONWARD if case["allow_onward"]
                else AB_DEFAULT
        )
    )

    # ------------------------------------------------
    # Stage A -> B
    # ------------------------------------------------

    if method == "B4":
        code, package_ab, reason = validate_b4(
            contract_ab, policy_ab, req_ab
        )

        if code != "APPROVE":
            return result(code, reason)

        ab = package_ab["facts"]

    else:
        # B1 and B2 retain a basic enterprise
        # purpose gate; B3 has a stronger gate.
        if method in ("B1", "B2"):
            if (
                policy_ab["status"] != "ACTIVE"
                or req_ab["purpose"]
                    not in policy_ab["allowed_purposes"]
            ):
                return result(
                    "REJECT", "BASIC_PURPOSE_GATE"
                )

        if method == "B1":
            ab = copy.deepcopy(source)

        elif method == "B2":
            ab = {
                name: {"value": source[name]["value"]}
                for name in AB_FIELDS
                if name in source
                and isinstance(source[name], dict)
                and "value" in source[name]
            }

        elif method == "B3":
            code, ab, reason = validate_b3(
                req_ab, policy_ab, AB_FIELDS
            )

            if code != "APPROVE":
                return result(code, reason)

        else:
            raise ValueError("Unknown method: " + method)

    inventory_outcome = inventory_result(ab)

    if case["workflow"] == "single_hop":
        return result(
            "PROCEED", "SINGLE_HOP", ab,
            task=inventory_outcome
        )

    # ------------------------------------------------
    # Between hops: source state can change.
    # ------------------------------------------------

    state = state_after_hop1(case)

    if method == "B3":
        if not check_b3_at_use(
            ab, state["source_versions"]
        ):
            return result(
                "SUSPEND", "SOURCE_VERSION_CHANGED", ab
            )

    elif method == "B4":
        at_use = check_at_use(
            contract_ab, policy_ab,
            package_ab, state, NOW
        )

        if at_use["decision"] != "APPROVE":
            return result(
                at_use["decision"],
                at_use["reason"], ab
            )

    if inventory_outcome != "available":
        return result(
            "PROCEED", "INVENTORY_NOT_READY", ab,
            task=inventory_outcome
        )

    # ------------------------------------------------
    # Stage B -> C
    # ------------------------------------------------

    if method == "B1":
        bc = copy.deepcopy(ab)

    elif method == "B2":
        bc = {
            name: copy.deepcopy(ab[name])
            for name in BC_FIELDS
            if name in ab
        }

    else:
        bc = {
            name: copy.deepcopy(ab[name])
            for name in BC_FIELDS
            if name in ab
        }

    req_bc = request(
        bc,
        source="inventory_management",
        destination="logistics",
        task_id="TASK-LOG-001",
        purpose="fulfillment_quote"
    )

    if method == "B3":
        code, bc, reason = validate_b3(
            req_bc, LOGISTICS_POLICY, BC_FIELDS
        )

        if code != "APPROVE":
            return result(code, reason, ab)

    ### Added
    elif method == "B4":
        originating_ok, originating_reason = (
            evaluate_originating_restrictions(
                case.get("originating_restrictions"),
                req_bc,
            )
        )
            
        if not originating_ok:
            return result(
                "REJECT",
                originating_reason,
                ab,
            )
        
        issues = contract_issues(
            BC_CONTRACT, REGISTRY
        )

        transfer = decide_onward(
            contract_ab,
            package_ab,
            BC_CONTRACT,
            LOGISTICS_POLICY,
            req_bc,
            NOW
        )
####
    elif method == "B4":
        issues = contract_issues(
            BC_CONTRACT, REGISTRY
        )

        if issues:
            return result(
                "REJECT",
                "BC_TEMPLATE_INVALID", ab
            )

        transfer = decide_onward(
            contract_ab,
            package_ab,
            BC_CONTRACT,
            LOGISTICS_POLICY,
            req_bc,
            NOW
        )

        if transfer["decision"] != "APPROVE":
            return result(
                transfer["decision"],
                transfer["reason"], ab
            )

        bc = transfer["package"]["facts"]

    return result(
        "PROCEED", "TWO_HOP_COMPLETED",
        ab, bc, logistics_result(bc)
    )


# -------------------------------------------------
# 8. Oracle-based measurements
# -------------------------------------------------

def evaluate(method, case, oracle):
    observed = simulate(method, case)

    ab = observed["ab"]
    bc = observed["bc"]

    excess_ab = len(
        set(ab) - set(oracle["allowed_ab"])
    )
    excess_bc = len(
        set(bc) - set(oracle["allowed_bc"])
    )
    excess = excess_ab + excess_bc

    action_ok = (
        observed["action"]
        in oracle["allowed_actions"]
    )

    task_ok = (
        observed["task_result"]
        == oracle["expected_result"]
    )

    def rich_fields(payload):
        return sum(
            1
            for item in payload.values()
            if isinstance(item, dict)
            and META <= set(item)
        )

    return {
        "case": case["id"],
        "workflow": case["workflow"],
        "method": method,
        "action": observed["action"],
        "reason": observed["reason"],
        "task_result": (
            observed["task_result"] or "NOT_EXECUTED"
        ),
        "action_correct": int(action_ok),
        #"task_correct": int(task_ok),
        "task_correct": (
            "" if oracle["expected_result"] is None
            else int(task_ok)
        ),
        "joint_correct": int(
            action_ok and task_ok and excess == 0
        ),
        "ab_fields": len(ab),
        "bc_fields": len(bc),
        "excess_ab": excess_ab,
        "excess_bc": excess_bc,
        "excess_total": excess,
        "rich_metadata_fields": (
            rich_fields(ab) + rich_fields(bc)
        )
    }


# -------------------------------------------------
# 9. Export and summary
# -------------------------------------------------

def run_pilot():
    cases = make_cases()
    rows = [
        evaluate(method, case, ORACLE[case_id])
        for case_id, case in cases.items()
        for method in METHODS
    ]

    ROOT.mkdir(parents=True, exist_ok=True)

    csv_path = ROOT / "pilot_results_v06.csv"

    with csv_path.open(
        "w", newline="", encoding="utf-8"
    ) as f:
        writer = csv.DictWriter(
            f, fieldnames=list(rows[0])
        )
        writer.writeheader()
        writer.writerows(rows)

    for filename, payload in (
        ("benchmark_inputs_v06.json", cases),
        ("benchmark_oracle_v06.json", ORACLE)
    ):
        (ROOT / filename).write_text(
            json.dumps(payload, indent=2) + "\n",
            encoding="utf-8"
        )

    print("Cases:", len(cases))
    print("Methods:", len(METHODS))
    print("Comparisons:", len(rows))
    print()
    print(
        f"{'Method':<8}"
        f"{'Joint':>9}"
        f"{'Action OK':>13}"
        f"{'Excess':>10}"
    )

    for method in METHODS:
        selected = [
            row for row in rows
            if row["method"] == method
        ]

        joint = sum(
            row["joint_correct"] for row in selected
        )
        actions = sum(
            row["action_correct"] for row in selected
        )
        excess = sum(
            row["excess_total"] for row in selected
        )

        print(
            f"{method:<8}"
            f"{joint:>6}/{len(selected):<2}"
            f"{actions:>10}/{len(selected):<2}"
            f"{excess:>10}"
        )

    print()
    print("CSV:", csv_path)
    return rows


# -------------------------------------------------
# 10. Regression and integration tests
# -------------------------------------------------

class IMICV06Tests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.cases = make_cases()

    def test_T24_forty_eight_evaluations(self):
        rows = [
            evaluate(m, c, ORACLE[cid])
            for cid, c in self.cases.items()
            for m in METHODS
        ]
        self.assertEqual(len(rows), 48)

    def test_T25_b3_b4_both_check_expiry(self):
        for method in ("B3", "B4"):
            observed = simulate(
                method, self.cases["C05"]
            )
            self.assertEqual(
                observed["action"], "SUSPEND"
            )

    def test_T26_b3_b4_both_check_policy(self):
        for method in ("B3", "B4"):
            observed = simulate(
                method, self.cases["C07"]
            )
            self.assertEqual(
                observed["action"], "REJECT"
            )

    def test_T27_onward_denied(self):
        case = self.cases["C10"]

        self.assertEqual(
            simulate("B3", case)["action"],
            "PROCEED"
        )
        self.assertEqual(
            simulate("B4", case)["action"],
            "REJECT"
        )

    def test_T28_approved_onward_transfer(self):
        case = self.cases["C11"]
        observed = simulate("B4", case)

        self.assertEqual(
            observed["action"], "PROCEED"
        )
        self.assertEqual(
            observed["task_result"], "quoted"
        )
        self.assertNotIn(
            "eligibility_status", observed["bc"]
        )

    def test_T29_source_version_change(self):
        case = self.cases["C12"]

        for method in ("B3", "B4"):
            observed = simulate(method, case)
            self.assertEqual(
                observed["action"], "SUSPEND"
            )

    def test_T30_excess_context_projection(self):
        case = self.cases["C03"]
        observed = simulate("B4", case)

        self.assertEqual(
            observed["action"], "PROCEED"
        )
        self.assertNotIn(
            "interaction_history", observed["ab"]
        )

    def test_T31_onward_requires_new_template(self):
        # The default registry must not silently
        # authorize the expanded onward permission.
        self.assertIn(
            "TEMPLATE_NOT_FOUND",
            contract_issues(
                AB_ONWARD, TEMPLATE_REGISTRY
            )
        )

        self.assertEqual(
            contract_issues(AB_ONWARD, REGISTRY),
            []
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--test", action="store_true")
    parser.add_argument("--run", action="store_true")
    args = parser.parse_args()

    if args.test:
        suite = unittest.defaultTestLoader.loadTestsFromTestCase(
            IMICV06Tests
        )
        outcome = unittest.TextTestRunner(
            verbosity=2
        ).run(suite)

        if not outcome.wasSuccessful():
            raise SystemExit(1)

    if args.run:
        run_pilot()

    if not (args.test or args.run):
        parser.print_help()
        
