import os
os.environ['DISPLAY']=':5';os.environ['XAUTHORITY']='/home/student/.Xauthority'
from Xlib import display,X
from PIL import Image
d=display.Display();root=d.screen().root;g=root.get_geometry();raw=root.get_image(0,0,g.width,g.height,X.ZPixmap,0xffffffff)
Image.frombytes('RGB',(g.width,g.height),raw.data,'raw','BGRX').save('/workspace/logs/week06-rviz-desktop.png')
print('IC382_RVIZ_DESKTOP_CAPTURED',g.width,g.height,flush=True)
