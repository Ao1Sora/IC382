"""Map model class names to the team's internal five-class roles.

The pretrained COCO bootstrap checkpoint only supplies ``person``. A custom
checkpoint must supply all five names before tagging is enabled. Mapping is
always name-based so a model whose ids are reordered cannot silently mis-label.
"""
from dataclasses import dataclass
from typing import Mapping

from ic382_perception.class_map import (
    ROLE_A,
    ROLE_B,
    ROLE_C,
    ROLE_OUT_OF_SCOPE,
    ROLE_PERSON,
    ROLE_RESERVED_CARD,
    canonical_class_name,
)

BOOTSTRAP_PROFILE = "coco_bootstrap"
STEWARD_PROFILE = "steward_v1"

_STEWARD_ROLES = {
    "ic_material": ROLE_A,
    "personal": ROLE_B,
    "disposables": ROLE_C,
    "person": ROLE_PERSON,
    "reserved_card": ROLE_RESERVED_CARD,
}
_BOOTSTRAP_ROLES = {"person": ROLE_PERSON}


@dataclass(frozen=True)
class ModelProfile:
    name: str
    roles_by_name: Mapping
    expected_names: frozenset
    tagging_enabled: bool


@dataclass(frozen=True)
class ResolvedProfile:
    name: str
    class_id_to_role: Mapping
    class_id_to_name: Mapping
    tagging_enabled: bool
    degraded_reason: str = ""

    def role_for(self, class_id):
        return self.class_id_to_role.get(int(class_id), ROLE_OUT_OF_SCOPE)

    def name_for(self, class_id):
        return self.class_id_to_name.get(int(class_id), str(class_id))


def steward_profile():
    return ModelProfile(
        name=STEWARD_PROFILE,
        roles_by_name=dict(_STEWARD_ROLES),
        expected_names=frozenset(_STEWARD_ROLES),
        tagging_enabled=True,
    )


def bootstrap_profile():
    return ModelProfile(
        name=BOOTSTRAP_PROFILE,
        roles_by_name=dict(_BOOTSTRAP_ROLES),
        expected_names=frozenset(_BOOTSTRAP_ROLES),
        tagging_enabled=False,
    )


def _normalise_names(model_names):
    """Accept {id: name} or a sequence of names; return {int id: original name}."""
    if isinstance(model_names, Mapping):
        return {int(key): str(value) for key, value in model_names.items()}
    return {index: str(value) for index, value in enumerate(model_names)}


def _profile_for_name(name):
    key = str(name).strip().lower()
    if key == STEWARD_PROFILE:
        return steward_profile()
    if key == BOOTSTRAP_PROFILE:
        return bootstrap_profile()
    raise ValueError("Unknown model profile: " + str(name))


def resolve_profile(name, model_names):
    """Build the id -> role mapping for a loaded model.

    ``name='auto'`` selects steward_v1 only when all five names are present,
    otherwise coco_bootstrap when person is present. A missing expected class
    degrades the profile to observe-only instead of guessing.
    """
    names = _normalise_names(model_names)
    canonical = {class_id: canonical_class_name(value) for class_id, value in names.items()}

    if str(name).strip().lower() == "auto":
        present = set(canonical.values())
        profile = steward_profile() if set(_STEWARD_ROLES) <= present else bootstrap_profile()
    else:
        profile = _profile_for_name(name)

    missing = sorted(profile.expected_names - set(canonical.values()))
    tagging_enabled = profile.tagging_enabled and not missing
    if profile.tagging_enabled and missing:
        degraded_reason = "missing model classes: " + ", ".join(missing)
    elif not profile.expected_names <= set(canonical.values()):
        degraded_reason = "missing model classes: " + ", ".join(missing)
    else:
        degraded_reason = ""

    class_id_to_role = {}
    class_id_to_name = {}
    for class_id, original in names.items():
        class_id_to_name[class_id] = original
        class_id_to_role[class_id] = profile.roles_by_name.get(
            canonical[class_id], ROLE_OUT_OF_SCOPE
        )

    return ResolvedProfile(
        name=profile.name,
        class_id_to_role=class_id_to_role,
        class_id_to_name=class_id_to_name,
        tagging_enabled=tagging_enabled,
        degraded_reason=degraded_reason,
    )
