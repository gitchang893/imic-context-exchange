
# imic_v04.py
# IMIC Generic Schema and Template Validation v0.4

import copy
import json
import sys
import unittest

from imic_proto import (
    CONTRACT,
    POLICY,
    NOW,
    ROOT,
    as_time,
    decide,
    valid_facts
)

from imic_v03 import (
    logistics_contract,
    LOGISTICS_POLICY,
    request
)

from imic_schema_v04 import (
    INSTANCE_SCHEMA,
    TEMPLATE_SCHEMA,
    INSTANCE_VALIDATOR,
    TEMPLATE_VALIDATOR
)


# --------------------------------------------------
# 1. Bootstrap reusable templates
# --------------------------------------------------

def make_template(instance):
    """
    Bootstrap a template from a reviewed canonical
    contract definition.

    Do not call this on a candidate instance
    during evaluation.
    """

    return {
        "template_id": instance["template"]["id"],
        "template_version": instance["template"]["version"],
        "source": copy.deepcopy(instance["source"]),
        "destination": copy.deepcopy(instance["destination"]),
        "task_type": instance["task"]["type"],
        "purpose": copy.deepcopy(instance["purpose"]),
        "requirements": copy.deepcopy(instance["requirements"]),
        "scope": copy.deepcopy(instance["scope"]),
        "semantics": copy.deepcopy(instance["semantics"]),
        "provenance": copy.deepcopy(instance["provenance"]),
        "state": copy.deepcopy(instance["state"]),
        "memory": copy.deepcopy(instance["memory"]),
        "onward_transfer": copy.deepcopy(
            instance["onward_transfer"]
        ),
        "return_conditions": copy.deepcopy(
            instance["return_conditions"]
        ),
        "change_rules": copy.deepcopy(
            instance["change_rules"]
        )
    }


# Reviewed canonical A -> B contract.
CUSTOMER_CONTRACT = copy.deepcopy(CONTRACT)

CUSTOMER_TEMPLATE = make_template(
    CUSTOMER_CONTRACT
)

# Reviewed canonical B -> C contract.
LOGISTICS_CONTRACT = logistics_contract()

LOGISTICS_CONTRACT["template"] = {
    "id": "logistics-fulfillment-quote",
    "version": 1
}

# Logistics does not require an eligibility predicate.
LOGISTICS_CONTRACT["semantics"]["allowed_values"] = {}

LOGISTICS_TEMPLATE = make_template(
    LOGISTICS_CONTRACT
)

# Templates are fixed before candidate validation.
TEMPLATE_REGISTRY = {
    (
        CUSTOMER_TEMPLATE["template_id"],
        CUSTOMER_TEMPLATE["template_version"]
    ): CUSTOMER_TEMPLATE,

    (
        LOGISTICS_TEMPLATE["template_id"],
        LOGISTICS_TEMPLATE["template_version"]
    ): LOGISTICS_TEMPLATE
}


# --------------------------------------------------
# 2. Structural and template compatibility checks
# --------------------------------------------------

def contract_issues(instance, registry=None):
    """
    Return a list of structural or compatibility
    violations.

    The registry is assumed to be authoritative.
    """

    if registry is None:
        registry = TEMPLATE_REGISTRY

    issues = []

    schema_errors = sorted(
        INSTANCE_VALIDATOR.iter_errors(instance),
        key=lambda e: str(e.json_path)
    )

    if schema_errors:
        return [
            "INSTANCE_SCHEMA: " + error.message
            for error in schema_errors
        ]

    key = (
        instance["template"]["id"],
        instance["template"]["version"]
    )

    template = registry.get(key)

    if template is None:
        return ["TEMPLATE_NOT_FOUND"]

    if not TEMPLATE_VALIDATOR.is_valid(template):
        return ["TEMPLATE_SCHEMA_INVALID"]

    def check(condition, code):
        if not condition:
            issues.append(code)

    # Binding and identity
    check(
        instance["source"] == template["source"],
        "SOURCE_MISMATCH"
    )

    check(
        instance["destination"] == template["destination"],
        "DESTINATION_MISMATCH"
    )

    check(
        instance["task"]["type"] == template["task_type"],
        "TASK_TYPE_MISMATCH"
    )

    check(
        instance["purpose"] == template["purpose"],
        "PURPOSE_OR_POLICY_MISMATCH"
    )

    # Required information cannot be silently omitted.
    i_required = set(instance["requirements"]["facts"])
    t_required = set(template["requirements"]["facts"])

    check(
        t_required <= i_required,
        "TEMPLATE_REQUIREMENT_REMOVED"
    )

    # Permitted information cannot be broadened.
    i_allowed = set(instance["scope"]["allowed"])
    t_allowed = set(template["scope"]["allowed"])
    i_denied = set(instance["scope"]["denied"])
    t_denied = set(template["scope"]["denied"])

    check(
        i_allowed <= t_allowed,
        "ALLOWED_SCOPE_WIDENED"
    )

    check(
        t_denied <= i_denied,
        "TEMPLATE_DENIAL_REMOVED"
    )

    check(
        not (i_allowed & i_denied),
        "SCOPE_CONFLICT"
    )

    check(
        i_required <= i_allowed,
        "REQUIRED_INFORMATION_NOT_ALLOWED"
    )

    check(
        not (
            instance["scope"]["allow_projection"]
            and not template["scope"]["allow_projection"]
        ),
        "PROJECTION_PERMISSION_EXPANDED"
    )

    # Semantic meaning must not silently change.
    t_sem = template["semantics"]
    i_sem = instance["semantics"]

    for field, unit in t_sem["units"].items():
        check(
            i_sem["units"].get(field) == unit,
            "UNIT_DEFINITION_CHANGED_" + field
        )

    for field, values in t_sem["allowed_values"].items():
        actual = i_sem["allowed_values"].get(field)

        check(
            actual is not None
            and set(actual) <= set(values),
            "SEMANTIC_VALUES_WIDENED_" + field
        )

    # Provenance requirements cannot be weakened.
    check(
        set(template["provenance"]["required"])
        <= set(instance["provenance"]["required"]),
        "PROVENANCE_REQUIREMENT_REMOVED"
    )

    # State conditions may be narrowed.
    check(
        set(instance["state"]["task_states"])
        <= set(template["state"]["task_states"]),
        "TASK_STATES_WIDENED"
    )

    check(
        set(instance["state"]["fact_states"])
        <= set(template["state"]["fact_states"]),
        "FACT_STATES_WIDENED"
    )

    # Memory conditions may not become more permissive.
    im = instance["memory"]
    tm = template["memory"]

    check(
        im["mode"] == tm["mode"],
        "MEMORY_MODE_CHANGED"
    )

    check(
        im["ttl_seconds"] <= tm["ttl_seconds"],
        "MEMORY_TTL_EXTENDED"
    )

    check(
        not (
            im["persistent_storage"]
            and not tm["persistent_storage"]
        ),
        "PERSISTENT_STORAGE_EXPANDED"
    )

    check(
        not (
            im["cross_task_reuse"]
            and not tm["cross_task_reuse"]
        ),
        "CROSS_TASK_REUSE_EXPANDED"
    )

    # Onward transfer must respect the template.
    io = instance["onward_transfer"]
    to = template["onward_transfer"]

    check(
        not (
            io["default"] == "allow"
            and to["default"] == "deny"
        ),
        "ONWARD_DEFAULT_WIDENED"
    )

    check(
        set(io["destinations"])
        <= set(to["destinations"]),
        "ONWARD_DESTINATIONS_WIDENED"
    )

    # Return and lifecycle obligations are preserved.
    check(
        set(template["return_conditions"]["fields"])
        <= set(instance["return_conditions"]["fields"]),
        "RETURN_REQUIREMENT_REMOVED"
    )

    check(
        instance["return_conditions"]["return_to"]
        == template["return_conditions"]["return_to"],
        "RETURN_DESTINATION_CHANGED"
    )

    check(
        instance["change_rules"] == template["change_rules"],
        "CHANGE_RULES_MODIFIED"
    )

    # Contract validity window must be well formed.
    try:
        start = as_time(instance["validity"]["valid_from"])
        end = as_time(instance["validity"]["valid_until"])

        check(
            start < end,
            "INVALID_VALIDITY_INTERVAL"
        )
    except (TypeError, ValueError, AttributeError):
        issues.append("INVALID_VALIDITY_TIMESTAMP")

    return issues


# --------------------------------------------------
# 3. Integrated v0.4 decision entry point
# --------------------------------------------------

def decide_v04(contract, policy, task_request, now=NOW):
    """
    Validate schema and template before delegating
    to the original transfer decision engine.
    """

    issues = contract_issues(contract)

    if issues:
        return {
            "decision": "REJECT",
            "reason": "CONTRACT_VALIDATION_FAILED",
            "issues": issues,
            "package": None
        }

    return decide(contract, policy, task_request, now)


# --------------------------------------------------
# 4. Test requests
# --------------------------------------------------

def customer_request():
    return request(valid_facts())


def logistics_request():
    fields = valid_facts()

    return request(
        {
            name: fields[name]
            for name in [
                "product_id",
                "quantity",
                "fulfillment_region"
            ]
        },
        source="inventory_management",
        destination="logistics",
        task_id="TASK-LOG-001",
        purpose="fulfillment_quote"
    )


# --------------------------------------------------
# 5. Automated tests T11 - T18
# --------------------------------------------------

class IMICV04Tests(unittest.TestCase):

    def test_T11_two_module_types(self):
        self.assertTrue(
            INSTANCE_VALIDATOR.is_valid(CUSTOMER_CONTRACT)
        )

        self.assertTrue(
            INSTANCE_VALIDATOR.is_valid(LOGISTICS_CONTRACT)
        )

        self.assertEqual(
            contract_issues(CUSTOMER_CONTRACT), []
        )

        self.assertEqual(
            contract_issues(LOGISTICS_CONTRACT), []
        )

        first = decide_v04(
            CUSTOMER_CONTRACT,
            POLICY,
            customer_request()
        )

        second = decide_v04(
            LOGISTICS_CONTRACT,
            LOGISTICS_POLICY,
            logistics_request()
        )

        self.assertEqual(first["decision"], "APPROVE")
        self.assertEqual(second["decision"], "APPROVE")

    def test_T12_no_sample_specific_semantic_field(self):
        candidate = copy.deepcopy(LOGISTICS_CONTRACT)

        candidate["semantics"]["allowed_values"] = {}

        self.assertTrue(
            INSTANCE_VALIDATOR.is_valid(candidate)
        )

        self.assertEqual(
            contract_issues(candidate), []
        )

    def test_T13_template_version_mismatch(self):
        candidate = copy.deepcopy(CUSTOMER_CONTRACT)

        candidate["template"]["version"] = 99

        self.assertIn(
            "TEMPLATE_NOT_FOUND",
            contract_issues(candidate)
        )

    def test_T14_scope_expansion(self):
        candidate = copy.deepcopy(CUSTOMER_CONTRACT)

        candidate["scope"]["allowed"].append(
            "unrelated_internal_metadata"
        )

        self.assertIn(
            "ALLOWED_SCOPE_WIDENED",
            contract_issues(candidate)
        )

        result = decide_v04(
            candidate,
            POLICY,
            customer_request()
        )

        self.assertEqual(result["decision"], "REJECT")

    def test_T15_removed_required_information(self):
        candidate = copy.deepcopy(CUSTOMER_CONTRACT)

        candidate["requirements"]["facts"].remove(
            "eligibility_status"
        )

        self.assertIn(
            "TEMPLATE_REQUIREMENT_REMOVED",
            contract_issues(candidate)
        )

    def test_T16_onward_permission_expansion(self):
        candidate = copy.deepcopy(CUSTOMER_CONTRACT)

        candidate["onward_transfer"]["destinations"] = [
            "logistics"
        ]

        self.assertIn(
            "ONWARD_DESTINATIONS_WIDENED",
            contract_issues(candidate)
        )

    def test_T17_memory_ttl_expansion(self):
        candidate = copy.deepcopy(CUSTOMER_CONTRACT)

        candidate["memory"]["ttl_seconds"] = 7200

        self.assertIn(
            "MEMORY_TTL_EXTENDED",
            contract_issues(candidate)
        )

    def test_T18_permitted_narrowing(self):
        candidate = copy.deepcopy(CUSTOMER_CONTRACT)

        candidate["memory"]["ttl_seconds"] = 600

        self.assertEqual(
            contract_issues(candidate), []
        )

        result = decide_v04(
            candidate,
            POLICY,
            customer_request()
        )

        self.assertEqual(result["decision"], "APPROVE")


# --------------------------------------------------
# 6. Export schemas, templates and instances
# --------------------------------------------------

def export_v04():
    ROOT.mkdir(parents=True, exist_ok=True)

    documents = {
        "imic_contract.schema.json": INSTANCE_SCHEMA,
        "imic_template.schema.json": TEMPLATE_SCHEMA,
        "template_customer_inventory.json": CUSTOMER_TEMPLATE,
        "template_inventory_logistics.json": LOGISTICS_TEMPLATE,
        "instance_customer_inventory.json": CUSTOMER_CONTRACT,
        "instance_inventory_logistics.json": LOGISTICS_CONTRACT
    }

    for filename, document in documents.items():
        path = ROOT / filename

        path.write_text(
            json.dumps(document, indent=2) + "\n",
            encoding="utf-8"
        )

    print("Exported", len(documents), "files to", ROOT)


if __name__ == "__main__":

    if len(sys.argv) == 2 and sys.argv[1] == "--export":
        export_v04()

    else:
        unittest.main(verbosity=2)
        
