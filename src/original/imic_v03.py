
# imic_v03.py
# IMIC Prototype v0.3
# Extends imic_proto.py (v0.2)
# Python >= 3.10

import copy
import unittest
from datetime import timedelta

from imic_proto import (
    CONTRACT,
    POLICY,
    NOW,
    as_time,
    decide,
    valid_facts,
    oracle_task_result
)


def answer(code, reason, package=None):
    return {
        "decision": code,
        "reason": reason,
        "package": package
    }


def request(
    facts,
    source="customer_service",
    destination="inventory_management",
    task_id="TASK-001",
    purpose="replacement_inventory_check"
):
    return {
        "source": source,
        "destination": destination,
        "task_id": task_id,
        "purpose": purpose,
        "task_state": "open",
        "facts": copy.deepcopy(facts)
    }


def approved_source_package(contract=CONTRACT):
    result = decide(
        contract,
        POLICY,
        request(valid_facts()),
        NOW
    )
    if result["decision"] != "APPROVE":
        raise RuntimeError("Initial transfer not approved")
    return result["package"]


# ==================================================
# T07: Onward-transfer control
# ==================================================

def decide_onward(
    original_contract,
    original_package,
    next_contract,
    next_policy,
    next_request,
    now=NOW
):
    """
    The original contract constrains any subsequent
    transfer of information derived from its package.

    Contracts are assumed to come from a trusted registry.
    """

    if original_contract["status"] != "ACTIVE":
        return answer("SUSPEND", "ORIGINAL_NOT_ACTIVE")

    validity = original_contract["validity"]
    current = as_time(now)

    if not (
        as_time(validity["valid_from"])
        <= current
        < as_time(validity["valid_until"])
    ):
        return answer("SUSPEND", "ORIGINAL_EXPIRED")

    if (
        original_package["contract_id"]
        != original_contract["contract_id"]
        or original_package["version"]
        != original_contract["version"]
    ):
        return answer("REJECT", "ORIGINAL_BINDING_MISMATCH")

    intermediate = original_contract["destination"]["module_id"]
    final_destination = next_request["destination"]

    if (
        next_request["source"] != intermediate
        or next_contract["source"]["module_id"] != intermediate
        or next_contract["destination"]["module_id"]
            != final_destination
    ):
        return answer("REJECT", "INVALID_MODULE_CHAIN")

    # No onward-transfer permission is inherited
    # merely from the original A -> B approval.
    onward = original_contract["onward_transfer"]

    if final_destination not in onward["destinations"]:
        return answer("REJECT", "ONWARD_NOT_PERMITTED")

    # Only information from the approved source
    # package may be forwarded in this minimal model.
    previous = original_package["facts"]
    proposed = next_request["facts"]

    for field, value in proposed.items():
        if field not in previous or value != previous[field]:
            return answer("REJECT", "UNAUTHORIZED_SOURCE_CONTEXT")

    # A separate B -> C contract must also pass.
    return decide(
        next_contract,
        next_policy,
        next_request,
        now
    )


def logistics_contract():
    contract = copy.deepcopy(CONTRACT)

    contract["contract_id"] = "IMIC-INV-LOG-001"
    contract["source"]["module_id"] = "inventory_management"
    contract["destination"]["module_id"] = "logistics"
    contract["task"]["id"] = "TASK-LOG-001"
    contract["task"]["type"] = "fulfillment_quote"

    contract["purpose"] = {
        "id": "fulfillment_quote",
        "operation": "quote_fulfillment",
        "policy_ref": "POLICY-LOG-001"
    }

    contract["requirements"]["facts"] = [
        "product_id",
        "quantity",
        "fulfillment_region"
    ]
    contract["scope"]["allowed"] = [
        "product_id",
        "quantity",
        "fulfillment_region"
    ]
    contract["scope"]["denied"].append(
        "eligibility_status"
    )
    # contract["semantics"]["allowed_values"] = {}
    contract["return_conditions"]["return_to"] = (
        "inventory_management"
    )
    return contract


LOGISTICS_POLICY = {
    "policy_id": "POLICY-LOG-001",
    "status": "ACTIVE",
    "source": "inventory_management",
    "destination": "logistics",
    "allowed_purposes": ["fulfillment_quote"],
    "allowed_operations": ["quote_fulfillment"],
    "allowed_fields": [
        "product_id",
        "quantity",
        "fulfillment_region"
    ]
}


# ==================================================
# T08: Validity-at-use and source updates
# ==================================================

def check_at_use(
    contract,
    policy,
    package,
    authoritative_state,
    now=NOW
):
    """
    Recheck delivered context against a trusted,
    current source-version registry.

    The registry is independent of the package.
    """

    revoked = authoritative_state.get(
        "revoked_contracts", []
    )

    if contract["contract_id"] in revoked:
        return answer("SUSPEND", "CONTRACT_REVOKED")

    if (
        package["contract_id"] != contract["contract_id"]
        or package["version"] != contract["version"]
    ):
        return answer("SUSPEND", "CONTRACT_VERSION_CHANGED")

    versions = authoritative_state["source_versions"]

    for name, item in package["facts"].items():
        source_id = item["source_id"]
        current_version = versions.get(source_id)

        if current_version is None:
            return answer(
                "SUSPEND", "SOURCE_NOT_VERIFIABLE_" + name
            )

        if current_version != item["source_version"]:
            return answer(
                "SUSPEND", "SOURCE_VERSION_CHANGED_" + name
            )

    # The normal decision engine also rechecks
    # current contract and fact expiry conditions.
    return decide(
        contract,
        policy,
        request(package["facts"]),
        now
    )


# ==================================================
# T09: Controlled semantic transformation
# ==================================================

# Trusted, domain-specific semantic conversion.
# One "six_pack" means exactly six pieces.
CONVERSIONS = {
    ("six_pack", "piece"): {
        "factor": 6,
        "rule_id": "SIX_PACK_TO_PIECE_V1"
    }
}


def propose_unit_transformation(
    contract,
    policy,
    incoming_request,
    now=NOW
):
    """
    Propose, but do not authorize, a semantic change.
    The transformed request must be checked again.
    """

    incoming = incoming_request["facts"]
    quantity = incoming.get("quantity")

    if not isinstance(quantity, dict):
        return answer("REQUEST_MORE", "QUANTITY_MISSING")

    target_unit = contract["semantics"]["units"]["quantity"]
    source_unit = quantity.get("unit")

    if source_unit == target_unit:
        return decide(
            contract, policy, incoming_request, now
        )

    rule = CONVERSIONS.get((source_unit, target_unit))

    if rule is None:
        return answer("SUSPEND", "NO_SEMANTIC_MAPPING")

    value = quantity.get("value")

    if type(value) is not int or value <= 0:
        return answer("SUSPEND", "INVALID_QUANTITY")

    transformed = copy.deepcopy(incoming_request)
    converted = transformed["facts"]["quantity"]

    converted["value"] = value * rule["factor"]
    converted["unit"] = target_unit
    converted["derivation"] = {
        "rule_id": rule["rule_id"],
        "original_value": value,
        "original_unit": source_unit
    }

    # Check that the proposed transformation does
    # not bypass the normal contract validation.
    preview = decide(
        contract, policy, transformed, now
    )

    if preview["decision"] != "APPROVE":
        return preview

    return answer(
        "TRANSFORM",
        "SEMANTIC_TRANSFORMATION_REVALIDATION_REQUIRED",
        {"transformed_request": transformed}
    )


# ==================================================
# T10: Trusted task-scoped memory reuse
# ==================================================

def decide_with_cache(
    contract,
    policy,
    incoming_request,
    cache,
    source_versions,
    now=NOW
):
    """
    Use local, trusted task memory to satisfy missing
    dependencies without retransmitting cached facts.

    The effective context is kept separate from
    the newly transferred payload.
    """

    # Reject changed identities or purposes before
    # consulting task-scoped cached information.
    if (
        incoming_request["source"]
        != contract["source"]["module_id"]
        or incoming_request["destination"]
        != contract["destination"]["module_id"]
        or incoming_request["task_id"]
        != contract["task"]["id"]
        or incoming_request["purpose"]
        != contract["purpose"]["id"]
    ):
        return decide(
            contract, policy, incoming_request, now
        )

    current = as_time(now)
    memory = contract["memory"]

    if memory["mode"] != "task_scoped":
        return answer("REQUEST_MORE", "MEMORY_MODE_UNSUPPORTED")

    expected_binding = {
        "destination": contract["destination"]["module_id"],
        "task_id": contract["task"]["id"],
        "purpose": contract["purpose"]["id"],
        "contract_id": contract["contract_id"],
        "contract_version": contract["version"]
    }

    for key, expected in expected_binding.items():
        if cache.get(key) != expected:
            return answer(
                "REQUEST_MORE", "CACHE_SCOPE_MISMATCH"
            )

    stored = as_time(cache["stored_at"])
    expiry = as_time(cache["expires_at"])
    ttl_expiry = stored + timedelta(
        seconds=memory["ttl_seconds"]
    )

    if not (stored <= current < min(expiry, ttl_expiry)):
        return answer("REQUEST_MORE", "CACHE_NOT_CURRENT")

    fresh = copy.deepcopy(incoming_request["facts"])
    effective = copy.deepcopy(fresh)
    cached_keys = []

    required = set(contract["requirements"]["facts"])

    for field in sorted(required - set(fresh)):
        item = cache["facts"].get(field)

        if item is None:
            return answer(
                "REQUEST_MORE", "CACHE_MISSING_" + field
            )

        # Verify cached provenance against the
        # current authoritative source version.
        source_id = item["source_id"]

        if source_versions.get(source_id) is None:
            return answer(
                "SUSPEND", "CACHE_SOURCE_UNKNOWN"
            )

        if (
            source_versions[source_id]
            != item["source_version"]
        ):
            return answer(
                "SUSPEND", "CACHE_SOURCE_SUPERSEDED"
            )

        effective[field] = copy.deepcopy(item)
        cached_keys.append(field)

    combined_request = copy.deepcopy(incoming_request)
    combined_request["facts"] = effective

    validated = decide(
        contract, policy, combined_request, now
    )

    if validated["decision"] != "APPROVE":
        return validated

    # The delivered payload contains NEW information
    # and references to already available memory.
    # It does not retransmit cached fact values.
    delivered = {
        "contract_id": contract["contract_id"],
        "version": contract["version"],
        "facts": fresh,
        "cached_references": sorted(cached_keys)
    }

    return {
        "decision": "APPROVE",
        "reason": "TRUSTED_CONTEXT_REUSE",
        "package": delivered,
        "effective_context": validated["package"]
    }


# ==================================================
# Automated tests: T07 - T10
# ==================================================

class IMICV03Tests(unittest.TestCase):

    def test_T07_onward_transfer(self):
        original = approved_source_package()
        bc = logistics_contract()

        fields = {
            k: v for k, v in original["facts"].items()
            if k in bc["requirements"]["facts"]
        }

        next_request = request(
            fields,
            source="inventory_management",
            destination="logistics",
            task_id="TASK-LOG-001",
            purpose="fulfillment_quote"
        )

        denied = decide_onward(
            CONTRACT,
            original,
            bc,
            LOGISTICS_POLICY,
            next_request
        )
        self.assertEqual(denied["decision"], "REJECT")

        # Positive control: a separately authorized
        # original contract expressly permits logistics.
        permitted_contract = copy.deepcopy(CONTRACT)
        permitted_contract["version"] = 2
        permitted_contract["onward_transfer"]["destinations"] = [
            "logistics"
        ]

        permitted_package = approved_source_package(
            permitted_contract
        )

        allowed = decide_onward(
            permitted_contract,
            permitted_package,
            bc,
            LOGISTICS_POLICY,
            next_request
        )
        self.assertEqual(allowed["decision"], "APPROVE")

    def test_T08_source_update(self):
        facts = valid_facts()
        facts["eligibility_status"]["source_id"] = (
            "ELIGIBILITY-001"
        )

        first = decide(
            CONTRACT, POLICY, request(facts), NOW
        )
        self.assertEqual(first["decision"], "APPROVE")

        state = {
            "source_versions": {
                "CASE-001": 1,
                "ELIGIBILITY-001": 1
            },
            "revoked_contracts": []
        }

        initial = check_at_use(
            CONTRACT, POLICY, first["package"], state
        )
        self.assertEqual(initial["decision"], "APPROVE")

        # The authoritative source has changed.
        state["source_versions"]["ELIGIBILITY-001"] = 2

        updated = check_at_use(
            CONTRACT, POLICY, first["package"], state
        )
        self.assertEqual(updated["decision"], "SUSPEND")

    def test_T08_revocation(self):
        package = approved_source_package()

        state = {
            "source_versions": {"CASE-001": 1},
            "revoked_contracts": [
                CONTRACT["contract_id"]
            ]
        }

        result = check_at_use(
            CONTRACT, POLICY, package, state
        )
        self.assertEqual(result["decision"], "SUSPEND")

    def test_T09_semantic_conversion(self):
        facts = valid_facts()

        facts["quantity"]["value"] = 2
        facts["quantity"]["unit"] = "six_pack"

        first = propose_unit_transformation(
            CONTRACT, POLICY, request(facts)
        )
        self.assertEqual(first["decision"], "TRANSFORM")

        transformed = first["package"]["transformed_request"]

        second = decide(
            CONTRACT, POLICY, transformed, NOW
        )
        self.assertEqual(second["decision"], "APPROVE")

        self.assertEqual(
            second["package"]["facts"]["quantity"]["value"],
            12
        )

        # Twelve pieces exceed the available stock
        # of five pieces in the independent oracle.
        self.assertEqual(
            oracle_task_result(second["package"]),
            "unavailable"
        )

    def test_T10_valid_cache(self):
        facts = valid_facts()
        cached_quantity = facts.pop("quantity")

        cache = {
            "destination": "inventory_management",
            "task_id": "TASK-001",
            "purpose": "replacement_inventory_check",
            "contract_id": CONTRACT["contract_id"],
            "contract_version": CONTRACT["version"],
            "stored_at": "2026-10-11T09:55:00Z",
            "expires_at": "2026-10-11T10:20:00Z",
            "facts": {"quantity": cached_quantity}
        }

        result = decide_with_cache(
            CONTRACT,
            POLICY,
            request(facts),
            cache,
            {"CASE-001": 1},
            NOW
        )

        self.assertEqual(result["decision"], "APPROVE")

        # Cached information is used locally and
        # is not retransmitted as a new field.
        self.assertNotIn(
            "quantity", result["package"]["facts"]
        )

        self.assertEqual(
            result["package"]["cached_references"],
            ["quantity"]
        )

        self.assertEqual(
            oracle_task_result(result["effective_context"]),
            "available"
        )

    def test_T10_expired_cache(self):
        facts = valid_facts()
        cached_quantity = facts.pop("quantity")

        cache = {
            "destination": "inventory_management",
            "task_id": "TASK-001",
            "purpose": "replacement_inventory_check",
            "contract_id": CONTRACT["contract_id"],
            "contract_version": CONTRACT["version"],
            "stored_at": "2026-10-11T09:00:00Z",
            "expires_at": "2026-10-11T11:00:00Z",
            "facts": {"quantity": cached_quantity}
        }

        result = decide_with_cache(
            CONTRACT,
            POLICY,
            request(facts),
            cache,
            {"CASE-001": 1},
            NOW
        )

        self.assertEqual(
            result["decision"], "REQUEST_MORE"
        )

    def test_T10_wrong_task_cache(self):
        facts = valid_facts()
        cached_quantity = facts.pop("quantity")

        cache = {
            "destination": "inventory_management",
            "task_id": "UNRELATED-TASK",
            "purpose": "replacement_inventory_check",
            "contract_id": CONTRACT["contract_id"],
            "contract_version": CONTRACT["version"],
            "stored_at": "2026-10-11T09:55:00Z",
            "expires_at": "2026-10-11T10:20:00Z",
            "facts": {"quantity": cached_quantity}
        }

        result = decide_with_cache(
            CONTRACT,
            POLICY,
            request(facts),
            cache,
            {"CASE-001": 1},
            NOW
        )

        self.assertEqual(
            result["decision"], "REQUEST_MORE"
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
    
