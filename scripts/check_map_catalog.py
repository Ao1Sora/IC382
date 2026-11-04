"""Map switching must keep scene geometry associated and survive restarts."""
from pathlib import Path
import tempfile
from unittest.mock import Mock
import yaml
import rclpy
from map_catalog import MapCatalog, read_config, write_config
from robot_console import Console


def map_file(folder, name='map'):
    folder.mkdir(parents=True, exist_ok=True)
    (folder/(name+'.pgm')).write_bytes(b'P5\n2 2\n255\n'+bytes([254]*4))
    path = folder/(name+'.yaml')
    write_config(path, dict(image=name+'.pgm', resolution=.05, origin=[0,0,0],
                            negate=0, occupied_thresh=.65, free_thresh=.25))
    return str(path)


rclpy.init()
try:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        first = map_file(root/'maps/room-a')
        keepout = map_file(root/'maps/room-a', 'navigation_map')
        second = map_file(root/'maps/room-b')
        config = dict(schema_version=1, map=first, navigation_map=keepout, points='', params_file='',
                      start_hardware=False, inspection=dict(desks=[dict(id='T01',polygon=[[0,0],[1,0],[1,1],[0,1]])]))
        runtime = root/'ros2_ws/src/ic382_navigation/config/physical_runtime.yaml'
        write_config(runtime, config)
        app = Console(root, test_mode=True)
        commands = []
        app.start = lambda name, command: commands.append((name, command))
        app.open_rviz = lambda: None
        app.mode = 'NAVIGATION'
        app.x = .1
        app.key('L')
        assert app.mode == 'MANUAL' and app.x == 0.
        assert len(app.map_items) == 2, 'Overlay must not be listed as a separate map'
        app.key('i'); assert app.x == 0., 'Movement must be disabled in selector'
        index = next(i for i,item in enumerate(app.map_items) if item['config']['map'] == second)
        app.map_index = index; app.key('\r')
        assert app.config['map'] == second
        assert not app.desks and app.config['navigation_map'] == ''
        assert commands[-1][0] == 'localization'
        assert app.mode == 'LOCALIZATION' and not app.global_requested
        assert read_config(runtime)['map'] == second, 'Selection must persist'
        try: app.start_navigation()
        except RuntimeError: pass
        else: raise AssertionError('Unconfigured map must not start inspection navigation')
        app.key('L')
        app.map_index = next(i for i,item in enumerate(app.map_items) if item['config']['map'] == first)
        app.key('\r')
        assert app.desks == ['T01'] and app.config['navigation_map'] == keepout
        app.start_navigation()
        assert any('config_file:='+str(runtime) in command for _, command in commands)
        app.key('L'); app.key('\x1b'); assert app.map_items is None
        saved = map_file(root/'maps/new-slam')
        app.catalog.register_saved(saved, app.config)
        scene = read_config(root/'maps/new-slam/scene.yaml')
        assert scene['inspection']['desks'] == [] and scene['navigation_map'] == ''
        (root/'maps/broken.yaml').write_text('image: missing.pgm\nresolution: 0.05\norigin: [0,0,0]\n')
        assert len(app.catalog.discover(app.config)) == 3
        for _ in range(5):
            item=next(i for i in app.catalog.discover(app.config) if i['config']['map']==first)
            app.catalog.activate(item)
        assert runtime.with_name(runtime.name+'.previous').is_file()
        assert not list(runtime.parent.glob(runtime.name+'.before-map-switch-*')), 'Map switching accumulated old backups'
        app.node.destroy_node()
        print('PASS: menu stops motion, map/scene discovery, pairing, preview, persistence, switch back, invalid maps, saved-map registration')
finally:
    rclpy.shutdown()
