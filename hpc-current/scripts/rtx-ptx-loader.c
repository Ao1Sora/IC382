#define _GNU_SOURCE
#include <dlfcn.h>
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>
#include <unistd.h>
#include <sys/wait.h>
#include <pthread.h>
static void *(*native_dlsym)(void *, const char *);
static void *driver;
static pthread_mutex_t mutex=PTHREAD_MUTEX_INITIALIZER;
static void init(void){if(!native_dlsym)native_dlsym=dlvsym(RTLD_NEXT,"dlsym","GLIBC_2.2.5");if(!driver)driver=dlopen("libcuda.so.1",RTLD_NOW|RTLD_LOCAL);}
int cuModuleLoadData(void **module,const void *data);
int cuModuleLoadDataEx(void **module,const void *data,unsigned int n,void *options,void *values);
int cuGetProcAddress(const char *name,void **ptr,int version,unsigned long long flags);
int cuGetProcAddress_v2(const char *name,void **ptr,int version,unsigned long long flags,void *status);
static void *override(const char *name){
 if(!strcmp(name,"cuModuleLoadData"))return cuModuleLoadData;
 if(!strcmp(name,"cuModuleLoadDataEx"))return cuModuleLoadDataEx;
 if(!strcmp(name,"cuGetProcAddress"))return cuGetProcAddress;
 if(!strcmp(name,"cuGetProcAddress_v2"))return cuGetProcAddress_v2;
 return NULL;
}
void *dlsym(void *handle,const char *name){if(!native_dlsym)native_dlsym=dlvsym(RTLD_NEXT,"dlsym","GLIBC_2.2.5");void *p=override(name);return p?p:native_dlsym(handle,name);}
static int compile_load(void **module,const char *ptx){
 init();pthread_mutex_lock(&mutex);
 uint64_t h=1469598103934665603ULL;for(const unsigned char *p=(const unsigned char*)ptx;*p;p++){h^=*p;h*=1099511628211ULL;}
 char source[512],binary[512];snprintf(source,sizeof source,"/workspace/cache/rtx-ptx-%016lx.ptx",h);snprintf(binary,sizeof binary,"/workspace/cache/rtx-ptx-%016lx.cubin",h);
 int result=222;
 if(access(binary,R_OK)!=0){
  FILE *f=fopen(source,"w");if(!f)goto done;fputs(ptx,f);fclose(f);
  pid_t p=fork();if(p==0){execl("/workspace/tools/cuda-nvcc-12-8/usr/local/cuda-12.8/bin/ptxas","ptxas","--gpu-name=sm_86",source,"-o",binary,(char*)NULL);_exit(127);}
  if(p<0)goto done;int status;waitpid(p,&status,0);if(!WIFEXITED(status)||WEXITSTATUS(status)!=0){fprintf(stderr,"IC382_PTX_COMPILE_FAILED %s\n",source);goto done;}
 }
 int(*load)(void**,const char*)=native_dlsym(driver,"cuModuleLoad");result=load(module,binary);fprintf(stderr,"IC382_ORIGINAL_PTX_CUBIN_LOADED %s result=%d\n",binary,result);
 done:pthread_mutex_unlock(&mutex);return result;
}
int cuModuleLoadData(void **module,const void *data){init();int(*fn)(void**,const void*)=native_dlsym(driver,"cuModuleLoadData");int r=fn(module,data);return r==222?compile_load(module,data):r;}
int cuModuleLoadDataEx(void **module,const void *data,unsigned int n,void *options,void *values){init();int(*fn)(void**,const void*,unsigned int,void*,void*)=native_dlsym(driver,"cuModuleLoadDataEx");int r=fn(module,data,n,options,values);return r==222?compile_load(module,data):r;}
int cuGetProcAddress(const char *name,void **ptr,int version,unsigned long long flags){init();int(*fn)(const char*,void**,int,unsigned long long)=native_dlsym(driver,"cuGetProcAddress");int r=fn(name,ptr,version,flags);void *p=override(name);if(r==0&&p)*ptr=p;return r;}
int cuGetProcAddress_v2(const char *name,void **ptr,int version,unsigned long long flags,void *status){init();int(*fn)(const char*,void**,int,unsigned long long,void*)=native_dlsym(driver,"cuGetProcAddress_v2");int r=fn(name,ptr,version,flags,status);void *p=override(name);if(r==0&&p)*ptr=p;return r;}
