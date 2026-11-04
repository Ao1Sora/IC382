"""Contact-only overlay for the CAD robot; source assets stay unchanged."""
from pxr import PhysxSchema, UsdPhysics, UsdShade


def configure_contacts(stage, root):
    wheel = UsdShade.Material.Define(stage, root + '/Materials/drive_wheels')
    material = UsdPhysics.MaterialAPI.Apply(wheel.GetPrim())
    material.CreateStaticFrictionAttr(1.2)
    material.CreateDynamicFrictionAttr(.9)
    material.CreateRestitutionAttr(0.)
    PhysxSchema.PhysxMaterialAPI.Apply(wheel.GetPrim()).CreateFrictionCombineModeAttr('max')
    for side in ('left', 'right'):
        collider = stage.GetPrimAtPath(root + '/' + side + '_wheel_link/collision')
        if not collider:
            raise ValueError('Missing drive-wheel collider: ' + side)
        UsdShade.MaterialBindingAPI.Apply(collider).Bind(wheel, materialPurpose='physics')
    # This sphere approximates a freely rolling caster. Averaging its small
    # friction with the floor's friction makes it act as a dragging fixed skid.
    caster = UsdShade.Material.Define(stage, root + '/Materials/caster')
    material = UsdPhysics.MaterialAPI.Apply(caster.GetPrim())
    material.CreateStaticFrictionAttr(0.)
    material.CreateDynamicFrictionAttr(0.)
    material.CreateRestitutionAttr(0.)
    PhysxSchema.PhysxMaterialAPI.Apply(caster.GetPrim()).CreateFrictionCombineModeAttr('min')
    collider = stage.GetPrimAtPath(root + '/base_link/collision_caster')
    if not collider:
        raise ValueError('Missing caster collider')
    UsdShade.MaterialBindingAPI.Apply(collider).Bind(caster, materialPurpose='physics')
    articulation = PhysxSchema.PhysxArticulationAPI.Apply(stage.GetPrimAtPath(root))
    articulation.CreateSolverPositionIterationCountAttr(64)
    articulation.CreateSolverVelocityIterationCountAttr(16)
    return {'wheel_static_friction': 1.2, 'wheel_dynamic_friction': .9,
            'wheel_combine': 'max', 'caster_friction': 0., 'caster_combine': 'min',
            'solver_position_iterations': 64, 'solver_velocity_iterations': 16}
