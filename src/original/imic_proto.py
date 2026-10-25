
# imic_proto.py
# IMIC Minimum Executable Prototype v0.2
# Requires Python >= 3.10 and jsonschema >= 4

import argparse
import copy
import json
import unittest
from datetime import datetime
from pathlib import Path

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parent / "imic_demo"
NOW = "2026-10-11T10:00:00Z"

REQUIRED = [
    "product_id",
    "quantity",
    "fulfillment_region",
    "eligibility_status"
]

# ==================================================
# 1. IMIC contract
# ==================================================

CONTRACT = {
    "schema_version": "IMIC-0.2",
    "contract_id": "IMIC-CS-INV-001",
    "version": 1,
    "template": {
        "id": "replacement-inventory-check",
        "version": 1
    },
    "status": "ACTIVE",
    "source": {"module_id": "customer_service"},
    "destination": {"module_id": "inventory_management"},
    "task": {
        "id": "TASK-001",
        "type": "inventory_check"
    },
    "purpose": {
        "id": "replacement_inventory_check",
        "operation": "check_availability",
        "policy_ref": "POLICY-INV-001"
    },
    "requirements": {"facts": REQUIRED},
    "scope": {
        "allowed": REQUIRED,
        "denied": [
            "interaction_history",
            "payment_credentials",
            "unrelated_account_data"
        ],
        "allow_projection": True
    },
    "semantics": {
        "units": {"quantity": "piece"},
        "allowed_values": {
            "eligibility_status": ["eligible"]
        }
    },
    "provenance": {
        "required": [
            "source_id",
            "source_version",
            "observed_at"
        ]
    },
    "state": {
        "task_states": ["open"],
        "fact_states": ["confirmed"]
    },
    "validity": {
        "valid_from": "2026-10-01T00:00:00Z",
        "valid_until": "2026-12-31T23:59:59Z"
    },
    "memory": {
        "mode": "task_scoped",
        "ttl_seconds": 1800,
        "persistent_storage": False,
        "cross_task_reuse": False
    },
    "onward_transfer": {
        "default": "deny",
        "destinations": []
    },
    "return_conditions": {
        "fields": [
            "availability_status",
            "checked_at",
            "inventory_source_version"
        ],
        "return_to": "customer_service"
    },
    "change_rules": {
        "on_source_change": "invalidate_and_recheck",
        "revocation": "block_further_use"
    }
}

# ==================================================
# 2. JSON Schema for structural validation
# ==================================================

def schema_from_example(value):
    if isinstance(value, dict):
        return {
            "type": "object",
            "required": list(value),
            "properties": {
                k: schema_from_example(v)
                for k, v in value.items()
            },
            "additionalProperties": False
        }

    if isinstance(value, list):
        return {
            "type": "array",
            "items": (
                schema_from_example(value[0])
                if value else {}
            )
        }

    if isinstance(value, bool):
        return {"type": "boolean"}

    if isinstance(value, int):
        return {"type": "integer"}

    return {"type": "string"}


### --------
## SCHEMA = schema_from_example(CONTRACT)
## SCHEMA["$schema"] = (
##     "https://json-schema.org/draft/2020-12/schema"
## )
##
## Draft202012Validator.check_schema(SCHEMA)
## VALIDATOR = Draft202012Validator(SCHEMA)
#### --------

from imic_schema_v04 import (
    INSTANCE_SCHEMA,
    INSTANCE_VALIDATOR
)

SCHEMA = INSTANCE_SCHEMA
VALIDATOR = INSTANCE_VALIDATOR


# ==================================================
# 3. Independent enterprise policy
# ==================================================

POLICY = {
    "policy_id": "POLICY-INV-001",
    "status": "ACTIVE",
    "source": "customer_service",
    "destination": "inventory_management",
    "allowed_purposes": [
        "replacement_inventory_check"
    ],
    "allowed_operations": [
        "check_availability"
    ],
    "allowed_fields": REQUIRED
}

# ==================================================
# 4. Test information
# ==================================================

def fact(value, unit=None):
    record = {
        "value": value,
        "source_id": "CASE-001",
        "source_version": 1,
        "observed_at": "2026-10-11T09:00:00Z",
        "expires_at": "2026-10-12T00:00:00Z",
        "information_state": "confirmed"
    }
    if unit is not None:
        record["unit"] = unit
    return record


def valid_facts():
    return {
        "product_id": fact("SKU-0042"),
        "quantity": fact(2, "piece"),
        "fulfillment_region": fact("JP-13"),
        "eligibility_status": fact("eligible")
    }


def make_cases():
    base = valid_facts()

    excess = copy.deepcopy(base)
    excess["interaction_history"] = fact(
        "Synthetic unrelated conversation"
    )

    missing = copy.deepcopy(base)
    del missing["eligibility_status"]

    expired = copy.deepcopy(base)
    expired["eligibility_status"]["expires_at"] = (
        "2026-10-11T09:00:00Z"
    )

    conflict = copy.deepcopy(POLICY)
    conflict["allowed_fields"] = [
        x for x in REQUIRED
        if x != "eligibility_status"
    ]

    def request(facts, purpose="replacement_inventory_check"):
        return {
            "source": "customer_service",
            "destination": "inventory_management",
            "task_id": "TASK-001",
            "purpose": purpose,
            "task_state": "open",
            "facts": facts
        }

    return {
        "T01": (request(base), POLICY),
        "T02": (request(excess), POLICY),
        "T03": (request(missing), POLICY),
        "T04": (request(expired), POLICY),
        "T05": (request(base, "customer_analytics"), POLICY),
        "T06": (request(base), conflict)
    }


# ==================================================
# 5. Independent ground truth
# ==================================================

GROUND_TRUTH = {
    "expected_decisions": {
        "T01": "APPROVE",
        "T02": "TRANSFORM",
        "T03": "REQUEST_MORE",
        "T04": "SUSPEND",
        "T05": "RENEGOTIATE",
        "T06": "REJECT"
    },
    "required_context": REQUIRED,
    "permitted_fields": REQUIRED,
    "prohibited_fields": [
        "interaction_history",
        "payment_credentials",
        "unrelated_account_data"
    ],
    "business_state": {
        "product_id": "SKU-0042",
        "region": "JP-13",
        "available_quantity": 5,
        "eligibility_status": "eligible"
    },
    "correct_task_result": "available"
}


def oracle_task_result(package):
    facts = package["facts"]
    truth = GROUND_TRUTH["business_state"]

    if not set(GROUND_TRUTH["required_context"]) <= set(facts):
        return "insufficient_context"

    if facts["product_id"]["value"] != truth["product_id"]:
        return "invalid_reference"

    if facts["fulfillment_region"]["value"] != truth["region"]:
        return "invalid_reference"

    if facts["eligibility_status"]["value"] != (
        truth["eligibility_status"]
    ):
        return "invalid_eligibility"

    quantity = facts["quantity"]["value"]

    if quantity <= truth["available_quantity"]:
        return "available"

    return "unavailable"


# ==================================================
# 6. IMIC decision engine
# ==================================================

def as_time(value):
    result = datetime.fromisoformat(
        value.replace("Z", "+00:00")
    )
    if result.tzinfo is None:
        raise ValueError("Timezone required")
    return result


def outcome(code, reason, package=None):
    return {
        "decision": code,
        "reason": reason,
        "package": package
    }


def decide(contract, policy, request, now=NOW):
    if not VALIDATOR.is_valid(contract):
        return outcome("REJECT", "INVALID_SCHEMA")

    now = as_time(now)

    if contract["status"] != "ACTIVE":
        return outcome("SUSPEND", "CONTRACT_NOT_ACTIVE")

    v = contract["validity"]

    if not (
        as_time(v["valid_from"]) <= now
        < as_time(v["valid_until"])
    ):
        return outcome("SUSPEND", "CONTRACT_EXPIRED")

    src = contract["source"]["module_id"]
    dst = contract["destination"]["module_id"]

    if (
        request["source"] != src
        or request["destination"] != dst
        or request["task_id"] != contract["task"]["id"]
    ):
        return outcome("REJECT", "IDENTITY_MISMATCH")

    if request["purpose"] != contract["purpose"]["id"]:
        return outcome("RENEGOTIATE", "PURPOSE_CHANGE")

    if (
        policy["status"] != "ACTIVE"
        or policy["policy_id"] != contract["purpose"]["policy_ref"]
        or policy["source"] != src
        or policy["destination"] != dst
    ):
        return outcome("REJECT", "POLICY_MISMATCH")

    if (
        request["purpose"] not in policy["allowed_purposes"]
        or contract["purpose"]["operation"]
        not in policy["allowed_operations"]
    ):
        return outcome("REJECT", "PURPOSE_NOT_AUTHORIZED")

    allowed = set(contract["scope"]["allowed"])
    denied = set(contract["scope"]["denied"])
    required = set(contract["requirements"]["facts"])

    if allowed & denied:
        return outcome("REJECT", "SCOPE_CONFLICT")

    if not allowed <= set(policy["allowed_fields"]):
        return outcome("REJECT", "CONTRACT_EXCEEDS_POLICY")

    if not required <= allowed:
        return outcome("REJECT", "REQUIRED_FIELD_DENIED")

    if request["task_state"] not in (
        contract["state"]["task_states"]
    ):
        return outcome("SUSPEND", "INVALID_TASK_STATE")

    incoming = request["facts"]
    selected = {}

    # Required context validation
    for name in sorted(required):
        if name not in incoming:
            return outcome(
                "REQUEST_MORE", "MISSING_" + name
            )

        record = incoming[name]

        if not isinstance(record, dict):
            return outcome(
                "REQUEST_MORE", "MALFORMED_" + name
            )

        mandatory = (
            {"value", "expires_at", "information_state"}
            | set(contract["provenance"]["required"])
        )

        if not mandatory <= set(record):
            return outcome(
                "REQUEST_MORE", "INCOMPLETE_" + name
            )

        try:
            observed = as_time(record["observed_at"])
            expires = as_time(record["expires_at"])
        except (ValueError, TypeError, AttributeError):
            return outcome(
                "REQUEST_MORE", "INVALID_TIMESTAMP_" + name
            )

        if not observed <= now < expires:
            return outcome(
                "SUSPEND", "STALE_" + name
            )

        if record["information_state"] not in (
            contract["state"]["fact_states"]
        ):
            return outcome(
                "SUSPEND", "INVALID_STATE_" + name
            )

        required_unit = (
            contract["semantics"]["units"].get(name)
        )

        if required_unit is not None:
            if record.get("unit") != required_unit:
                return outcome(
                    "SUSPEND", "INVALID_UNIT_" + name
                )

        valid_values = (
            contract["semantics"]["allowed_values"].get(name)
        )

        if valid_values is not None:
            if record["value"] not in valid_values:
                return outcome(
                    "SUSPEND", "INVALID_VALUE_" + name
                )

        selected[name] = copy.deepcopy(record)

    package = {
        "contract_id": contract["contract_id"],
        "version": contract["version"],
        "facts": selected
    }

    # Exclude unnecessary context.
    extra = set(incoming) - required

    if extra:
        if not contract["scope"]["allow_projection"]:
            return outcome(
                "REJECT", "PROJECTION_NOT_ALLOWED"
            )

        return outcome(
            "TRANSFORM",
            "REVALIDATION_REQUIRED",
            package
        )

    return outcome(
        "APPROVE",
        "ALL_CHECKS_PASSED",
        package
    )


# ==================================================
# 7. Export contract, schema and test data
# ==================================================

def save_json(name, data):
    path = ROOT / name
    path.write_text(
        json.dumps(data, indent=2) + "\n",
        encoding="utf-8"
    )


def export_files():
    ROOT.mkdir(parents=True, exist_ok=True)

    save_json("imic_contract.json", CONTRACT)
    save_json("imic_contract.schema.json", SCHEMA)
    save_json("enterprise_policy.json", POLICY)
    save_json("ground_truth.json", GROUND_TRUTH)

    cases = {
        key: {"request": req, "policy": pol}
        for key, (req, pol) in make_cases().items()
    }

    save_json("test_cases.json", cases)

    print("Files created in:", ROOT)


# ==================================================
# 8. Automated tests
# ==================================================

class IMICTests(unittest.TestCase):

    def check_case(self, test_id):
        request, policy = make_cases()[test_id]
        result = decide(CONTRACT, policy, request)

        self.assertEqual(
            result["decision"],
            GROUND_TRUTH["expected_decisions"][test_id]
        )
        return result

    def test_T01(self):
        result = self.check_case("T01")
        self.assertEqual(
            oracle_task_result(result["package"]),
            "available"
        )

    def test_T02(self):
        result = self.check_case("T02")

        projected = result["package"]["facts"]

        self.assertEqual(
            set(projected),
            set(GROUND_TRUTH["permitted_fields"])
        )

        request, policy = make_cases()["T02"]
        request["facts"] = projected

        second = decide(CONTRACT, policy, request)

        self.assertEqual(
            second["decision"], "APPROVE"
        )

    def test_T03(self):
        self.check_case("T03")

    def test_T04(self):
        self.check_case("T04")

    def test_T05(self):
        self.check_case("T05")

    def test_T06(self):
        self.check_case("T06")

    def test_schema_valid(self):
        VALIDATOR.validate(CONTRACT)

    def test_schema_missing_purpose(self):
        invalid = copy.deepcopy(CONTRACT)
        del invalid["purpose"]

        self.assertFalse(
            VALIDATOR.is_valid(invalid)
        )


# ==================================================
# 9. Main
# ==================================================

def main():
    parser = argparse.ArgumentParser()

    parser.add_argument("--init", action="store_true")
    parser.add_argument("--test", action="store_true")

    args = parser.parse_args()

    if args.init:
        export_files()

    if args.test:
        suite = unittest.defaultTestLoader.loadTestsFromTestCase(
            IMICTests
        )

        result = unittest.TextTestRunner(
            verbosity=2
        ).run(suite)

        if not result.wasSuccessful():
            raise SystemExit(1)

    if not (args.init or args.test):
        parser.print_help()


if __name__ == "__main__":
    main()
    
