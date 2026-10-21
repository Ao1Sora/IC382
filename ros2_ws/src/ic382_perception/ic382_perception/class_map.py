"""Class id <-> code mapping and defaults for object classification."""

CONF_THRESHOLD = 0.5
VALID_CLASS_IDS = {0, 1, 2}

CLASS_ID_TO_CODE = {0: "A", 1: "B", 2: "C"}

CLASS_ID_TO_NAME = {
    0: "Class_A_IC_Material",
    1: "Class_B_Personal",
    2: "Class_C_Disposables",
}


def class_code(class_id):
    return CLASS_ID_TO_CODE.get(class_id)
