static void *compile_bytes(const char *ptx,size_t *size){
 uint64_t h=1469598103934665603ULL;for(const unsigned char *p=(const unsigned char*)ptx;*p;p++){h^=*p;h*=1099511628211ULL;}
 char source[512],binary[512];snprintf(source,sizeof source,"/workspace/cache/rtx-ptx-%016lx.ptx",h);snprintf(binary,sizeof binary,"/workspace/cache/rtx-ptx-%016lx.cubin",h);
 if(access(binary,R_OK)!=0){FILE *f=fopen(source,"w");if(!f)return NULL;fputs(ptx,f);fclose(f);pid_t p=fork();if(p==0){execl("/workspace/tools/cuda-nvcc-12-8/usr/local/cuda-12.8/bin/ptxas","ptxas","--gpu-name=sm_86",source,"-o",binary,(char*)NULL);_exit(127);}if(p<0)return NULL;int status;waitpid(p,&status,0);if(!WIFEXITED(status)||WEXITSTATUS(status)){fprintf(stderr,"IC382_PTX_LINK_COMPILE_FAILED %s\n",source);return NULL;}}
 FILE *f=fopen(binary,"rb");if(!f)return NULL;fseek(f,0,SEEK_END);*size=ftell(f);rewind(f);void *data=malloc(*size);if(!data){fclose(f);return NULL;}fread(data,1,*size,f);fclose(f);fprintf(stderr,"IC382_PTX_LINK_COMPILED %s\n",binary);return data;
}
int cuLinkAddData_v2(void *state,int type,void *data,size_t size,const char *name,unsigned int n,void *options,void *values){
 init();int(*fn)(void*,int,void*,size_t,const char*,unsigned int,void*,void*)=native_dlsym(driver,"cuLinkAddData_v2");int r=fn(state,type,data,size,name,n,options,values);
 if(r==222&&type==1){size_t length;void *compiled=compile_bytes(data,&length);if(compiled){r=fn(state,0,compiled,length,name,n,options,values);free(compiled);fprintf(stderr,"IC382_PTX_LINK_LOADED result=%d\n",r);}}
 return r;
}
int cuLinkAddData(void *state,int type,void *data,size_t size,const char *name,unsigned int n,void *options,void *values){return cuLinkAddData_v2(state,type,data,size,name,n,options,values);}
int cuLibraryLoadData(void **lib,const void *code,void *jitOptions,void *jitValues,unsigned int nJit,void *libOptions,void *libValues,unsigned int nLib){
 init();int(*fn)(void**,const void*,void*,void*,unsigned int,void*,void*,unsigned int)=native_dlsym(driver,"cuLibraryLoadData");int r=fn(lib,code,jitOptions,jitValues,nJit,libOptions,libValues,nLib);
 if(r==222){size_t length;void *compiled=compile_bytes(code,&length);if(compiled){r=fn(lib,compiled,jitOptions,jitValues,nJit,libOptions,libValues,nLib);free(compiled);fprintf(stderr,"IC382_PTX_LIBRARY_LOADED result=%d\n",r);}}
 return r;
}
