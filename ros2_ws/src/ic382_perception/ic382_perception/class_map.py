"""Internal class schema shared by detection, classification and logging.

The team schema has five classes. Only A/B/C may ever be tagged; person and
reserved_card are used for safety and desk eligibility.
"""

CONF_THRESHOLD = 0.5

ROLE_A = "A"
ROLE_B = "B"
ROLE_C = "C"
ROLE_PERSON = "PERSON"
ROLE_RESERVED_CARD = "RESERVED_CARD"
ROLE_OUT_OF_SCOPE = "OUT_OF_SCOPE"

TAGGABLE_ROLES = frozenset({ROLE_A, ROLE_B, ROLE_C})
ELIGIBILITY_ROLES = frozenset({ROLE_PERSON, ROLE_RESERVED_CARD})

CLASS_ID_TO_ROLE = {
    0: ROLE_A,
    1: ROLE_B,
    2: ROLE_C,
    3: ROLE_PERSON,
    4: ROLE_RESERVED_CARD,
}

ROLE_TO_CLASS_ID = {role: class_id for class_id, role in CLASS_ID_TO_ROLE.items()}

CLASS_ID_TO_CODE = {0: "A", 1: "B", 2: "C"}
ROLE_TO_CODE = {ROLE_A: "A", ROLE_B: "B", ROLE_C: "C"}

CLASS_CODE_TO_LABEL = {
    "A": "Class_A_IC_Material",
    "B": "Class_B_Personal",
    "C": "Class_C_Disposables",
}

CLASS_ID_TO_NAME = {
    0: "ic_material",
    1: "personal",
    2: "disposables",
    3: "person",
    4: "reserved_card",
}

CLASS_NAME_TO_ID = {name: class_id for class_id, name in CLASS_ID_TO_NAME.items()}

VALID_CLASS_IDS = {0, 1, 2}
ALL_CLASS_IDS = set(CLASS_ID_TO_ROLE)
TAGGABLE_IDS = {class_id for class_id, role in CLASS_ID_TO_ROLE.items() if role in TAGGABLE_ROLES}
SAFETY_IDS = {ROLE_TO_CLASS_ID[ROLE_PERSON]}
ELIGIBILITY_IDS = {
    class_id for class_id, role in CLASS_ID_TO_ROLE.items() if role in ELIGIBILITY_ROLES
}

# Model class labels are matched by name, never by numeric id. These aliases
# cover the Roboflow labels, the older three-class names, and common spellings.
_NAME_ALIASES = {
    "ic_material": ROLE_A,
    "icmaterial": ROLE_A,
    "ic_material_class_a": ROLE_A,
    "class_a_ic_material": ROLE_A,
    "class_a": ROLE_A,
    "a": ROLE_A,
    "personal": ROLE_B,
    "personal_property": ROLE_B,
    "class_b_personal": ROLE_B,
    "class_b": ROLE_B,
    "b": ROLE_B,
    "disposables": ROLE_C,
    "disposable": ROLE_C,
    "garbage": ROLE_C,
    "class_c_disposables": ROLE_C,
    "class_c": ROLE_C,
    "c": ROLE_C,
    "person": ROLE_PERSON,
    "people": ROLE_PERSON,
    "class_person": ROLE_PERSON,
    "reserved_card": ROLE_RESERVED_CARD,
    "reserved": ROLE_RESERVED_CARD,
    "reservedcard": ROLE_RESERVED_CARD,
    "reserved_stand": ROLE_RESERVED_CARD,
    "class_reserved_card": ROLE_RESERVED_CARD,
}


def canonical_class_name(name):
    """Normalise a model label to lower snake_case for alias lookup."""
    text = str(name).strip().lower().replace("-", "_").replace(" ", "_")
    while "__" in text:
        text = text.replace("__", "_")
    return text.strip("_")


def role_for_class_name(name):
    """Return the internal role for a model label, or OUT_OF_SCOPE."""
    return _NAME_ALIASES.get(canonical_class_name(name), ROLE_OUT_OF_SCOPE)


def role_for_class_id(class_id):
    return CLASS_ID_TO_ROLE.get(int(class_id), ROLE_OUT_OF_SCOPE)


def class_code(class_id):
    return CLASS_ID_TO_CODE.get(int(class_id))


def class_code_for_role(role):
    return ROLE_TO_CODE.get(role)
