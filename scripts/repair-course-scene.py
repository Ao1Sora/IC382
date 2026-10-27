"""Build a reversible material/static-collision overlay; never edit teacher assets."""
from collections import defaultdict
from pathlib import Path
from urllib.parse import unquote, urlparse
import json, zipfile, re
from functools import lru_cache
from pxr import Gf, Sdf, Usd, UsdPhysics, UsdShade


def repair_scene(source, destination, asset_root):
    source, destination, asset_root = map(Path, (source, destination, asset_root))
    layer = Sdf.Layer.CreateAnonymous('course-material-physics-repair.usda')
    layer.subLayerPaths = [str(source)]
    stage = Usd.Stage.Open(layer)
    index = defaultdict(list)
    for base in [asset_root.parent, Path('/workspace/tools/isaacsim-6.0.1/kit/mdl')]:
        for p in base.rglob('*'):
            if p.is_file():
                index[p.name.lower()].append(p)
    archive_path = Path('/workspace/downloads/week06-canvas-assets.zip')
    archive = zipfile.ZipFile(archive_path) if archive_path.exists() else None
    archive_index = defaultdict(list)
    if archive:
        for name in archive.namelist():
            if not name.endswith('/'):
                archive_index[Path(name).name.lower()].append(name)
    report = {'source': str(source), 'resolved': [], 'unavailable': [], 'fallback_materials': []}

    @lru_cache(maxsize=None)
    def missing_mdl_images(path):
        path = Path(path)
        if path.suffix.lower() != '.mdl':
            return ()
        text = path.read_text(errors='replace')
        images = re.findall(r'texture_2d\(\s*"([^"]+)"', text)
        return tuple(v for v in images if v and '://' not in v and not (path.parent / unquote(v)).is_file())

    @lru_cache(maxsize=None)
    def resolve(raw):
        raw = unquote(unquote(raw))
        if raw.startswith('file:'):
            raw = urlparse(raw).path
        p = Path(raw)
        if not p.is_absolute():
            p = source.parent / p
        if p.is_file():
            if p.suffix.lower() == '.mdl' and missing_mdl_images(str(p)):
                complete = [c for c in index.get(p.name.lower(), []) if not missing_mdl_images(str(c))]
                if complete:
                    return sorted(complete, key=lambda c: str(c))[0]
            return p
        choices = index.get(p.name.lower(), [])
        def score(candidate):
            result = 0
            for a, b in zip(reversed(p.parts), reversed(candidate.parts)):
                if a.lower() != b.lower():
                    break
                result += 1
            return result
        scores = [(score(c), c) for c in choices]
        if not scores and archive:
            matches = archive_index.get(p.name.lower(), [])
            ranked = [(score(Path(n)), n) for n in matches]
            if ranked:
                best = max(v[0] for v in ranked)
                winners = [n for v, n in ranked if v == best]
                if len(winners) == 1:
                    target = destination.parent / 'course-material-assets' / winners[0]
                    target = target.resolve()
                    if not target.is_relative_to(destination.parent.resolve()):
                        raise ValueError('Unsafe archive member')
                    target.parent.mkdir(parents=True, exist_ok=True)
                    if not target.exists():
                        target.write_bytes(archive.read(winners[0]))
                    index[p.name.lower()].append(target)
                    return target
        if not scores:
            return None
        best = max(v[0] for v in scores)
        winners = [c for v, c in scores if v == best]
        return winners[0] if len(winners) == 1 else None

    # An explicit empty target list masks the stronger inherited grey binding.
    stage.GetPrimAtPath('/World').GetRelationship('material:binding').SetTargets([])
    grey = stage.GetPrimAtPath('/World/IC382_HPC_Material')
    if grey:
        grey.SetActive(False)
    bad_materials = {}
    for prim in list(stage.Traverse()):
        for attr in prim.GetAttributes():
            if attr.GetTypeName() != Sdf.ValueTypeNames.Asset:
                continue
            value = attr.Get()
            if not value or not value.path:
                continue
            # Only fix file assets. Named built-in MDL modules are left to Kit.
            raw = value.path
            if '://' in raw and not raw.startswith('file:'):
                continue
            # These names are resolved by the renderer's built-in MDL search path.
            if Path(raw).name == raw and raw.startswith('Omni') and raw.endswith('.mdl'):
                continue
            target = resolve(raw)
            if target and not missing_mdl_images(str(target)):
                if str(target) != raw:
                    attr.Set(Sdf.AssetPath(str(target)))
                    report['resolved'].append({'attribute': str(attr.GetPath()), 'file': str(target)})
            else:
                parent = prim
                while parent and not parent.IsA(UsdShade.Material):
                    parent = parent.GetParent()
                if parent:
                    bad_materials[str(parent.GetPath())] = parent
                report['unavailable'].append({'attribute': str(attr.GetPath()), 'asset': raw})

    for path, prim in bad_materials.items():
        material = UsdShade.Material(prim)
        # Existing portable PreviewSurface networks are preferable to a new fallback.
        portable = None
        for child in Usd.PrimRange(prim):
            if child.IsA(UsdShade.Shader) and UsdShade.Shader(child).GetIdAttr().Get() == 'UsdPreviewSurface':
                portable = UsdShade.Shader(child)
                break
        color, roughness, metallic, opacity = Gf.Vec3f(.5), .5, 0., 1.
        aliases = {'diffuse_reflection_color': 'color', 'diffuse_color': 'color', 'diffuse_color_constant': 'color', 'diffuse_tint': 'color', 'base_color': 'color', 'diffuseColor': 'color', 'reflection_roughness': 'roughness', 'reflection_roughness_constant': 'roughness', 'roughness': 'roughness', 'metallic': 'metallic', 'metallic_constant': 'metallic', 'opacity': 'opacity'}
        for child in Usd.PrimRange(prim):
            if not child.IsA(UsdShade.Shader):
                continue
            for inp in UsdShade.Shader(child).GetInputs():
                value = inp.Get()
                name = aliases.get(inp.GetBaseName())
                if name == 'color' and value is not None and hasattr(value, '__len__') and len(value) >= 3:
                    color = Gf.Vec3f(*[float(v) for v in value[:3]])
                elif name in ('roughness', 'metallic', 'opacity') and isinstance(value, (float, int)):
                    if name == 'roughness': roughness = float(value)
                    elif name == 'metallic': metallic = float(value)
                    else: opacity = float(value)
        if portable is None:
            portable = UsdShade.Shader.Define(stage, path + '/IC382PortableSurface')
            portable.CreateIdAttr('UsdPreviewSurface')
            for name, typ, value in [('diffuseColor', Sdf.ValueTypeNames.Color3f, color), ('roughness', Sdf.ValueTypeNames.Float, roughness), ('metallic', Sdf.ValueTypeNames.Float, metallic), ('opacity', Sdf.ValueTypeNames.Float, opacity)]:
                portable.CreateInput(name, typ).Set(value)
            # Preserve any available base-color image when only another MDL
            # dependency was missing (for example the grass AO texture).
            for child in list(Usd.PrimRange(prim)):
                if not child.IsA(UsdShade.Shader):
                    continue
                image = UsdShade.Shader(child).GetInput('diffuse_texture')
                if image and image.Get() and resolve(image.Get().path):
                    reader = UsdShade.Shader.Define(stage, path + '/IC382UV')
                    reader.CreateIdAttr('UsdPrimvarReader_float2')
                    reader.CreateInput('varname', Sdf.ValueTypeNames.Token).Set('st')
                    texture = UsdShade.Shader.Define(stage, path + '/IC382BaseColor')
                    texture.CreateIdAttr('UsdUVTexture')
                    texture.CreateInput('file', Sdf.ValueTypeNames.Asset).Set(Sdf.AssetPath(str(resolve(image.Get().path))))
                    texture.CreateInput('sourceColorSpace', Sdf.ValueTypeNames.Token).Set('sRGB')
                    texture.CreateInput('st', Sdf.ValueTypeNames.Float2).ConnectToSource(reader.ConnectableAPI(), 'result')
                    portable.GetInput('diffuseColor').ConnectToSource(texture.ConnectableAPI(), 'rgb')
                    break
        # Clear broken texture links and MDL source fields only within affected materials.
        for child in list(Usd.PrimRange(prim)):
            for attr in child.GetAttributes():
                if attr.GetTypeName() == Sdf.ValueTypeNames.Asset:
                    value = attr.Get()
                    target = resolve(value.path) if value and value.path else None
                    if value and value.path and (not target or missing_mdl_images(str(target))) and '://' not in value.path:
                        attr.Set(Sdf.AssetPath(''))
        for output in material.GetSurfaceOutputs():
            output.DisconnectSource()
        # Keep available portable textures, but disconnect inputs whose texture
        # files were unavailable so authored scalar/color defaults can take over.
        for inp in portable.GetInputs():
            for connection in inp.GetAttr().GetConnections():
                upstream = stage.GetPrimAtPath(connection.GetPrimPath())
                if upstream and upstream.IsA(UsdShade.Shader):
                    file_input = UsdShade.Shader(upstream).GetInput('file')
                    if file_input and (not file_input.Get() or not file_input.Get().path):
                        inp.DisconnectSource()
        material.CreateSurfaceOutput().ConnectToSource(portable.ConnectableAPI(), 'surface')
        report['fallback_materials'].append(path)

    # This long architectural mesh is fixed scenery, not a moving robot part.
    cube = stage.GetPrimAtPath('/World/IC_building_scene/Cube_02')
    if cube:
        UsdPhysics.RigidBodyAPI(cube).CreateRigidBodyEnabledAttr(False)
        UsdPhysics.CollisionAPI.Apply(cube).CreateCollisionEnabledAttr(True)
        UsdPhysics.MeshCollisionAPI.Apply(cube).CreateApproximationAttr('none')
    destination.parent.mkdir(parents=True, exist_ok=True)
    layer.Export(str(destination))
    if archive:
        archive.close()
    destination.with_suffix('.json').write_text(json.dumps(report, indent=2))
    print('IC382_SCENE_REPAIRED', len(report['resolved']), 'resolved assets;', len(bad_materials), 'portable materials', flush=True)
    return destination


if __name__ == '__main__':
    import sys
    repair_scene(*sys.argv[1:4])
