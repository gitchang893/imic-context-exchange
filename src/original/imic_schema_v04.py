# imic_schema_v04.py
# Generic IMIC Schema v0.4
# Python >= 3.10
# Dependency: jsonschema >= 4, < 5

from jsonschema import Draft202012Validator, FormatChecker


def obj(**properties):
    return {
        "type": "object",
        "properties": properties,
        "required": list(properties),
        "additionalProperties": False
    }


TEXT = {"type": "string", "minLength": 1}
POS_INT = {"type": "integer", "minimum": 1}
NONNEG_INT = {"type": "integer", "minimum": 0}
BOOL = {"type": "boolean"}
DATETIME = {"type": "string", "format": "date-time"}

TEXT_LIST = {
    "type": "array",
    "items": TEXT,
    "uniqueItems": True
}

TEXT_MAP = {
    "type": "object",
    "additionalProperties": TEXT
}

VALUE_MAP = {
    "type": "object",
    "additionalProperties": TEXT_LIST
}

# Shared structural definitions.
MODULE = obj(module_id=TEXT)

PURPOSE = obj(
    id=TEXT,
    operation=TEXT,
    policy_ref=TEXT
)

REQUIREMENTS = obj(facts=TEXT_LIST)

SCOPE = obj(
    allowed=TEXT_LIST,
    denied=TEXT_LIST,
    allow_projection=BOOL
)

SEMANTICS = obj(
    units=TEXT_MAP,
    allowed_values=VALUE_MAP
)

PROVENANCE = obj(required=TEXT_LIST)

STATE = obj(
    task_states=TEXT_LIST,
    fact_states=TEXT_LIST
)

MEMORY = obj(
    mode=TEXT,
    ttl_seconds=NONNEG_INT,
    persistent_storage=BOOL,
    cross_task_reuse=BOOL
)

ONWARD = obj(
    default={"enum": ["deny", "allow"]},
    destinations=TEXT_LIST
)

RETURN = obj(
    fields=TEXT_LIST,
    return_to=TEXT
)

CHANGE = obj(
    on_source_change=TEXT,
    revocation=TEXT
)

# --------------------------------------------------
# Contract Instance Schema
# --------------------------------------------------

INSTANCE_SCHEMA = obj(
    schema_version={
        "type": "string",
        "pattern": r"^IMIC-0\.[0-9]+$"
    },
    contract_id=TEXT,
    version=POS_INT,
    template=obj(
        id=TEXT,
        version=POS_INT
    ),
    status={
        "enum": [
            "DRAFT",
            "VALIDATED",
            "ACTIVE",
            "SUSPENDED",
            "EXPIRED",
            "REVOKED",
            "CLOSED"
        ]
    },
    source=MODULE,
    destination=MODULE,
    task=obj(
        id=TEXT,
        type=TEXT
    ),
    purpose=PURPOSE,
    requirements=REQUIREMENTS,
    scope=SCOPE,
    semantics=SEMANTICS,
    provenance=PROVENANCE,
    state=STATE,
    validity=obj(
        valid_from=DATETIME,
        valid_until=DATETIME
    ),
    memory=MEMORY,
    onward_transfer=ONWARD,
    return_conditions=RETURN,
    change_rules=CHANGE
)

INSTANCE_SCHEMA["$schema"] = (
    "https://json-schema.org/draft/2020-12/schema"
)

# --------------------------------------------------
# Reusable Contract Template Schema
# --------------------------------------------------

TEMPLATE_SCHEMA = obj(
    template_id=TEXT,
    template_version=POS_INT,
    source=MODULE,
    destination=MODULE,
    task_type=TEXT,
    purpose=PURPOSE,
    requirements=REQUIREMENTS,
    scope=SCOPE,
    semantics=SEMANTICS,
    provenance=PROVENANCE,
    state=STATE,
    memory=MEMORY,
    onward_transfer=ONWARD,
    return_conditions=RETURN,
    change_rules=CHANGE
)

TEMPLATE_SCHEMA["$schema"] = (
    "https://json-schema.org/draft/2020-12/schema"
)

# Verify both schemas.
Draft202012Validator.check_schema(INSTANCE_SCHEMA)
Draft202012Validator.check_schema(TEMPLATE_SCHEMA)

INSTANCE_VALIDATOR = Draft202012Validator(
    INSTANCE_SCHEMA,
    format_checker=FormatChecker()
)

TEMPLATE_VALIDATOR = Draft202012Validator(
    TEMPLATE_SCHEMA,
    format_checker=FormatChecker()
)
