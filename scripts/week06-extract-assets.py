from pathlib import Path
import zipfile, shutil
project=Path.home()/'Desktop/IC382'
dest=(project/'dev').resolve()
prefix='ROS2 Isaac_Sim Materials/'
with zipfile.ZipFile(project/'downloads/week06-canvas-assets.zip') as archive:
    for item in archive.infolist():
        if not item.filename.startswith(prefix): raise ValueError('Unexpected archive root')
        relative=item.filename[len(prefix):]
        if not relative: continue
        target=(dest/relative).resolve()
        if target!=dest and dest not in target.parents: raise ValueError('Unsafe archive path')
        if item.is_dir(): target.mkdir(parents=True,exist_ok=True); continue
        target.parent.mkdir(parents=True,exist_ok=True)
        with archive.open(item) as src, open(target,'wb') as out: shutil.copyfileobj(src,out,1024*1024)
print('IC382_WEEK06_ASSETS_EXTRACTED')
