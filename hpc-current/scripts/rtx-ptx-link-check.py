exec(open('/workspace/scripts/rtx-ptx-jit-check.py').read().split("for version in")[0])
state=ctypes.c_void_p();check(c.cuLinkCreate_v2(0,None,None,ctypes.byref(state)),'linkCreate')
ptx=b'.version 8.7\n.target sm_86\n.address_size 64\n.visible .entry noop(){ret;}\n'
check(c.cuLinkAddData_v2(state,1,ctypes.c_char_p(ptx),ctypes.c_size_t(len(ptx)+1),b'original.ptx',0,None,None),'linkAddOriginalPTX87')
image=ctypes.c_void_p();size=ctypes.c_size_t();check(c.cuLinkComplete(state,ctypes.byref(image),ctypes.byref(size)),'linkComplete');print('CUBIN_BYTES',size.value)
c.cuLinkDestroy(state);c.cuCtxDestroy_v2(ctx)
