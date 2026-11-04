import os,time
os.environ['DISPLAY']=':5';os.environ['XAUTHORITY']='/home/student/.Xauthority'
from Xlib import display,X
from PIL import Image
d=display.Display();root=d.screen().root
def visit(w,depth=0):
 try:
  name=w.get_wm_name();g=w.get_geometry();state=w.get_attributes().map_state
  if name:print('WINDOW',w.id,name,g.width,g.height,state,flush=True)
  if name and 'RViz' in str(name) and state==X.IsViewable:
   raw=w.get_image(0,0,g.width,g.height,X.ZPixmap,0xffffffff);Image.frombytes('RGB',(g.width,g.height),raw.data,'raw','BGRX').save('/workspace/logs/week06-rviz-window.png');print('RVIZ_WINDOW_CAPTURED',flush=True)
  if depth<2:
   for c in w.query_tree().children:visit(c,depth+1)
 except Exception as e:print(type(e).__name__,str(e)[:100],flush=True)
visit(root)
