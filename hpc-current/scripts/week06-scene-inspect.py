import os,runpy
from isaacsim import SimulationApp
app=SimulationApp({'headless':True,'extra_args':['--/plugins/carb.tasking.plugin/threadCount=6','--/plugins/omni.tbb.globalcontrol/maxThreadCount=6']})
try:
    from pathlib import Path
    source=Path('/workspace/scripts/week06-usd-inspect.py').read_text()
    source=source.replace("Path.home()/'Desktop/IC382'", "Path('/workspace')")
    source=source.replace("Path.home()/'Desktop/IC382/dev", "Path('/workspace/dev")
    source=source.replace("Path.home()/'Desktop/IC382/logs", "Path('/workspace/logs")
    # The two full paths below are kept explicit so the script runs in the Ubuntu workspace.
    source=Path('/workspace/scripts/week06-usd-inspect.py').read_text().replace("Path.home()/'Desktop/IC382/dev/Collected_final_wheeltec_with_scene/final_wheeltec_with_scene.usd'", "Path('/workspace/dev/Collected_final_wheeltec_with_scene/final_wheeltec_with_scene.usd')").replace("Path.home()/'Desktop/IC382/logs/week06-usd-inspect.json'", "Path('/workspace/logs/week06-usd-inspect.json')")
    exec(compile(source,'week06-usd-inspect.py','exec'))
finally: app.close()
