"""Persistent map scenes: map, keepout map and desk geometry stay together."""
from copy import deepcopy
from pathlib import Path
import os
import yaml

PATHS = ('map', 'navigation_map', 'params_file', 'points', 'log_directory')


def read_config(path):
    document = yaml.safe_load(Path(path).read_text(encoding='utf-8')) or {}
    for key in PATHS:
        if document.get(key):
            target = Path(document[key]).expanduser()
            document[key] = str(target if target.is_absolute() else Path(path).resolve().parent/target)
    return document


def write_config(path, document):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name+'.tmp')
    temporary.write_text(yaml.safe_dump(document, allow_unicode=True, sort_keys=False),encoding='utf-8')
    os.replace(temporary, path)


def valid_map(path):
    try:
        path = Path(path)
        data = yaml.safe_load(path.read_text())
        image = path.parent/str(data['image'])
        return image.is_file() and float(data['resolution']) > 0 and len(data['origin']) == 3
    except (OSError, ValueError, TypeError, KeyError, yaml.YAMLError):
        return False


def scene_ready(config):
    return (valid_map(config.get('map', '')) and valid_map(config.get('navigation_map', ''))
            and bool(config.get('inspection', {}).get('desks')))


class MapCatalog:
    def __init__(self, root, runtime_path):
        self.root = Path(root)
        self.runtime_path = Path(runtime_path)
        self.directory = self.root/'maps'

    def save_current(self, config):
        """Snapshot the known matched scene, without guessing geometry for new maps."""
        if not valid_map(config.get('map', '')):
            return
        folder = Path(config['map']).parent
        # Keep imported maps outside maps/ discoverable as profiles too.
        if not folder.is_relative_to(self.directory.resolve()):
            folder = self.directory/'imported-current'
        target = folder/'scene.yaml'
        if not target.exists():
            document = deepcopy(config)
            document['scene_name'] = folder.name
            write_config(target, document)

    def discover(self, current):
        self.save_current(current)
        items, seen, overlays = [], set(), set()
        for path in sorted(self.directory.rglob('scene.yaml')):
            try:
                config = read_config(path)
                map_path = str(Path(config.get('map', '')).resolve())
                if not valid_map(map_path): continue
                if config.get('navigation_map'): overlays.add(str(Path(config['navigation_map']).resolve()))
                items.append(dict(name=str(config.get('scene_name', path.parent.name)),
                                  profile=str(path), config=config, ready=scene_ready(config)))
                seen.add(map_path)
            except (OSError, ValueError, TypeError, yaml.YAMLError):
                continue
        for path in sorted(self.directory.rglob('*.yaml')):
            absolute = str(path.resolve())
            if absolute in seen or absolute in overlays or path.name == 'navigation_map.yaml': continue
            if not valid_map(path): continue
            config = deepcopy(current)
            config.update(map=absolute, navigation_map='', points='', scene_name=path.parent.name+'/'+path.stem)
            config['inspection'] = deepcopy(current.get('inspection', {}))
            config['inspection']['desks'] = []
            # A previous scene's optional Nav2 override may contain map-specific geometry.
            config['params_file'] = ''
            config['start_hardware'] = False
            items.append(dict(name=config['scene_name'], profile='', config=config, ready=False))
        return items

    def activate(self, item):
        config = deepcopy(item['config'])
        if not valid_map(config.get('map', '')): raise ValueError('Map image/YAML is missing or invalid')
        if self.runtime_path.exists():
            backup = self.runtime_path.with_name(self.runtime_path.name+'.previous')
            temporary=backup.with_name(backup.name+'.tmp')
            temporary.write_bytes(self.runtime_path.read_bytes())
            os.replace(temporary,backup)
        config['start_hardware'] = False
        write_config(self.runtime_path, config)
        return config

    def register_saved(self, map_path, current):
        if not valid_map(map_path): raise ValueError('Saved map files are incomplete')
        config = deepcopy(current)
        config.update(map=str(Path(map_path).resolve()), navigation_map='', points='', params_file='',
                      scene_name=Path(map_path).parent.name, start_hardware=False)
        config['inspection'] = deepcopy(current.get('inspection', {}))
        config['inspection']['desks'] = []
        write_config(Path(map_path).parent/'scene.yaml', config)
