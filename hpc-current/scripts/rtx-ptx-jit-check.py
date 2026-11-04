import ctypes,json
c=ctypes.CDLL('libcuda.so.1')
def check(code,name):
 p=ctypes.c_char_p();c.cuGetErrorName(code,ctypes.byref(p));print(name,code,p.value,flush=True)
 if code:raise RuntimeError(name)
check(c.cuInit(0),'cuInit');v=ctypes.c_int();c.cuDriverGetVersion(ctypes.byref(v));print('DRIVER_API',v.value,flush=True)
d=ctypes.c_int();check(c.cuDeviceGet(ctypes.byref(d),0),'device');ctx=ctypes.c_void_p();check(c.cuCtxCreate_v2(ctypes.byref(ctx),0,d),'context')
for version in ['8.4','8.7','8.8']:
 m=ctypes.c_void_p();ptx=('.version '+version+'\n.target sm_86\n.address_size 64\n.visible .entry noop(){ret;}\n').encode()
 code=c.cuModuleLoadData(ctypes.byref(m),ctypes.c_char_p(ptx));p=ctypes.c_char_p();c.cuGetErrorName(code,ctypes.byref(p));print('PTX_JIT_RESULT',version,code,p.value,flush=True)
 if code==0:c.cuModuleUnload(m)
c.cuCtxDestroy_v2(ctx)
