typedef struct {void *state;int count;char *files[64];void *image;size_t size;} OfflineLink;
static OfflineLink links[32];
static OfflineLink *lookup(void *state,int create){for(int i=0;i<32;i++)if(links[i].state==state)return &links[i];if(create)for(int i=0;i<32;i++)if(!links[i].state){links[i].state=state;return &links[i];}return NULL;}
static char *compile_object(const char *ptx){
 uint64_t h=1469598103934665603ULL;for(const unsigned char *p=(const unsigned char*)ptx;*p;p++){h^=*p;h*=1099511628211ULL;}
 char source[512],object[512];snprintf(source,sizeof source,"/workspace/cache/rtx-ptx-%016lx.ptx",h);snprintf(object,sizeof object,"/workspace/cache/rtx-ptx-%016lx.o",h);
 if(access(object,R_OK)!=0){FILE *f=fopen(source,"w");if(!f)return NULL;fputs(ptx,f);fclose(f);pid_t pid=fork();if(pid==0){execl("/workspace/tools/cuda-nvcc-12-8/usr/local/cuda-12.8/bin/ptxas","ptxas","--gpu-name=sm_86","--compile-only",source,"-o",object,(char*)NULL);_exit(127);}if(pid<0)return NULL;int status;waitpid(pid,&status,0);if(!WIFEXITED(status)||WEXITSTATUS(status)){fprintf(stderr,"IC382_ORIGINAL_PTX_OBJECT_FAILED %s\n",source);return NULL;}}
 fprintf(stderr,"IC382_ORIGINAL_PTX_OBJECT %s\n",object);return strdup(object);
}
int cuLinkAddData_v2(void *state,int type,void *data,size_t size,const char *name,unsigned int n,void *options,void *values){
 init();int(*fn)(void*,int,void*,size_t,const char*,unsigned int,void*,void*)=native_dlsym(driver,"cuLinkAddData_v2");
 if(type!=1)return fn(state,type,data,size,name,n,options,values);
 pthread_mutex_lock(&mutex);OfflineLink *link=lookup(state,1);char *file=compile_object(data);int r=222;
 if(link&&file&&link->count<64){link->files[link->count++]=file;r=0;}
 pthread_mutex_unlock(&mutex);return r;
}
int cuLinkAddData(void *state,int type,void *data,size_t size,const char *name,unsigned int n,void *options,void *values){return cuLinkAddData_v2(state,type,data,size,name,n,options,values);}
int cuLinkComplete(void *state,void **image,size_t *size){
 init();pthread_mutex_lock(&mutex);OfflineLink *link=lookup(state,0);
 if(!link||!link->count){pthread_mutex_unlock(&mutex);int(*fn)(void*,void**,size_t*)=native_dlsym(driver,"cuLinkComplete");return fn(state,image,size);}
 char binary[512];snprintf(binary,sizeof binary,"/workspace/cache/rtx-link-%d-%p.cubin",(int)getpid(),state);
 char *argv[72];int n=0;argv[n++]="nvlink";argv[n++]="--arch=sm_86";for(int i=0;i<link->count;i++)argv[n++]=link->files[i];argv[n++]="-o";argv[n++]=binary;argv[n]=NULL;
 pid_t pid=fork();if(pid==0){execv("/workspace/tools/cuda-nvcc-12-8/usr/local/cuda-12.8/bin/nvlink",argv);_exit(127);}int status;waitpid(pid,&status,0);int r=222;
 if(pid>0&&WIFEXITED(status)&&WEXITSTATUS(status)==0){FILE *f=fopen(binary,"rb");if(f){fseek(f,0,SEEK_END);link->size=ftell(f);rewind(f);link->image=malloc(link->size);if(link->image){fread(link->image,1,link->size,f);*image=link->image;*size=link->size;r=0;}fclose(f);}}
 fprintf(stderr,"IC382_ORIGINAL_PTX_OFFLINE_LINK modules=%d result=%d bytes=%zu\n",link->count,r,link->size);pthread_mutex_unlock(&mutex);return r;
}
int cuLinkDestroy(void *state){init();pthread_mutex_lock(&mutex);OfflineLink *link=lookup(state,0);if(link){for(int i=0;i<link->count;i++)free(link->files[i]);free(link->image);memset(link,0,sizeof *link);}pthread_mutex_unlock(&mutex);int(*fn)(void*)=native_dlsym(driver,"cuLinkDestroy");return fn(state);}
