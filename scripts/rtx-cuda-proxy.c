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
static void init(void){if(!native_dlsym)native_dlsym=dlvsym(RTLD_NEXT,"dlsym","GLIBC_2.2.5");if(!driver)driver=dlopen("/opt/nvidia/lib/libcuda.so.550.54.14",RTLD_NOW|RTLD_LOCAL);}
int cuModuleLoadData(void **module,const void *data);
int cuModuleLoadDataEx(void **module,const void *data,unsigned int n,void *options,void *values);
int cuGetProcAddress(const char *name,void **ptr,int version,unsigned long long flags);
int cuGetProcAddress_v2(const char *name,void **ptr,int version,unsigned long long flags,void *status);
int cuLinkAddData_v2(void*,int,void*,size_t,const char*,unsigned int,void*,void*);
int cuLinkAddData(void*,int,void*,size_t,const char*,unsigned int,void*,void*);
int cuLibraryLoadData(void**,const void*,void*,void*,unsigned int,void*,void*,unsigned int);
int cuLinkComplete(void*,void**,size_t*);
int cuLinkDestroy(void*);
static void *override(const char *name){
 if(!strcmp(name,"cuModuleLoadData"))return cuModuleLoadData;
 if(!strcmp(name,"cuModuleLoadDataEx"))return cuModuleLoadDataEx;
 if(!strcmp(name,"cuGetProcAddress"))return cuGetProcAddress;
 if(!strcmp(name,"cuGetProcAddress_v2"))return cuGetProcAddress_v2;
 if(!strcmp(name,"cuLinkAddData"))return cuLinkAddData;
 if(!strcmp(name,"cuLinkAddData_v2"))return cuLinkAddData_v2;
 if(!strcmp(name,"cuLinkComplete"))return cuLinkComplete;
 if(!strcmp(name,"cuLinkDestroy"))return cuLinkDestroy;
 return NULL;
}
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

__attribute__((visibility("hidden"))) void *forward_0;

__attribute__((visibility("hidden"))) void *forward_1;

__attribute__((visibility("hidden"))) void *forward_2;

__attribute__((visibility("hidden"))) void *forward_3;

__attribute__((visibility("hidden"))) void *forward_4;

__attribute__((visibility("hidden"))) void *forward_5;

__attribute__((visibility("hidden"))) void *forward_6;

__attribute__((visibility("hidden"))) void *forward_7;

__attribute__((visibility("hidden"))) void *forward_8;

__attribute__((visibility("hidden"))) void *forward_9;

__attribute__((visibility("hidden"))) void *forward_10;

__attribute__((visibility("hidden"))) void *forward_11;

__attribute__((visibility("hidden"))) void *forward_12;

__attribute__((visibility("hidden"))) void *forward_13;

__attribute__((visibility("hidden"))) void *forward_14;

__attribute__((visibility("hidden"))) void *forward_15;

__attribute__((visibility("hidden"))) void *forward_16;

__attribute__((visibility("hidden"))) void *forward_17;

__attribute__((visibility("hidden"))) void *forward_18;

__attribute__((visibility("hidden"))) void *forward_19;

__attribute__((visibility("hidden"))) void *forward_20;

__attribute__((visibility("hidden"))) void *forward_21;

__attribute__((visibility("hidden"))) void *forward_22;

__attribute__((visibility("hidden"))) void *forward_23;

__attribute__((visibility("hidden"))) void *forward_24;

__attribute__((visibility("hidden"))) void *forward_25;

__attribute__((visibility("hidden"))) void *forward_26;

__attribute__((visibility("hidden"))) void *forward_27;

__attribute__((visibility("hidden"))) void *forward_28;

__attribute__((visibility("hidden"))) void *forward_29;

__attribute__((visibility("hidden"))) void *forward_30;

__attribute__((visibility("hidden"))) void *forward_31;

__attribute__((visibility("hidden"))) void *forward_32;

__attribute__((visibility("hidden"))) void *forward_33;

__attribute__((visibility("hidden"))) void *forward_34;

__attribute__((visibility("hidden"))) void *forward_35;

__attribute__((visibility("hidden"))) void *forward_36;

__attribute__((visibility("hidden"))) void *forward_37;

__attribute__((visibility("hidden"))) void *forward_38;

__attribute__((visibility("hidden"))) void *forward_39;

__attribute__((visibility("hidden"))) void *forward_40;

__attribute__((visibility("hidden"))) void *forward_41;

__attribute__((visibility("hidden"))) void *forward_42;

__attribute__((visibility("hidden"))) void *forward_43;

__attribute__((visibility("hidden"))) void *forward_44;

__attribute__((visibility("hidden"))) void *forward_45;

__attribute__((visibility("hidden"))) void *forward_46;

__attribute__((visibility("hidden"))) void *forward_47;

__attribute__((visibility("hidden"))) void *forward_48;

__attribute__((visibility("hidden"))) void *forward_49;

__attribute__((visibility("hidden"))) void *forward_50;

__attribute__((visibility("hidden"))) void *forward_51;

__attribute__((visibility("hidden"))) void *forward_52;

__attribute__((visibility("hidden"))) void *forward_53;

__attribute__((visibility("hidden"))) void *forward_54;

__attribute__((visibility("hidden"))) void *forward_55;

__attribute__((visibility("hidden"))) void *forward_56;

__attribute__((visibility("hidden"))) void *forward_57;

__attribute__((visibility("hidden"))) void *forward_58;

__attribute__((visibility("hidden"))) void *forward_59;

__attribute__((visibility("hidden"))) void *forward_60;

__attribute__((visibility("hidden"))) void *forward_61;

__attribute__((visibility("hidden"))) void *forward_62;

__attribute__((visibility("hidden"))) void *forward_63;

__attribute__((visibility("hidden"))) void *forward_64;

__attribute__((visibility("hidden"))) void *forward_65;

__attribute__((visibility("hidden"))) void *forward_66;

__attribute__((visibility("hidden"))) void *forward_67;

__attribute__((visibility("hidden"))) void *forward_68;

__attribute__((visibility("hidden"))) void *forward_69;

__attribute__((visibility("hidden"))) void *forward_70;

__attribute__((visibility("hidden"))) void *forward_71;

__attribute__((visibility("hidden"))) void *forward_72;

__attribute__((visibility("hidden"))) void *forward_73;

__attribute__((visibility("hidden"))) void *forward_74;

__attribute__((visibility("hidden"))) void *forward_75;

__attribute__((visibility("hidden"))) void *forward_76;

__attribute__((visibility("hidden"))) void *forward_77;

__attribute__((visibility("hidden"))) void *forward_78;

__attribute__((visibility("hidden"))) void *forward_79;

__attribute__((visibility("hidden"))) void *forward_80;

__attribute__((visibility("hidden"))) void *forward_81;

__attribute__((visibility("hidden"))) void *forward_82;

__attribute__((visibility("hidden"))) void *forward_83;

__attribute__((visibility("hidden"))) void *forward_84;

__attribute__((visibility("hidden"))) void *forward_85;

__attribute__((visibility("hidden"))) void *forward_86;

__attribute__((visibility("hidden"))) void *forward_87;

__attribute__((visibility("hidden"))) void *forward_88;

__attribute__((visibility("hidden"))) void *forward_89;

__attribute__((visibility("hidden"))) void *forward_90;

__attribute__((visibility("hidden"))) void *forward_91;

__attribute__((visibility("hidden"))) void *forward_92;

__attribute__((visibility("hidden"))) void *forward_93;

__attribute__((visibility("hidden"))) void *forward_94;

__attribute__((visibility("hidden"))) void *forward_95;

__attribute__((visibility("hidden"))) void *forward_96;

__attribute__((visibility("hidden"))) void *forward_97;

__attribute__((visibility("hidden"))) void *forward_98;

__attribute__((visibility("hidden"))) void *forward_99;

__attribute__((visibility("hidden"))) void *forward_100;

__attribute__((visibility("hidden"))) void *forward_101;

__attribute__((visibility("hidden"))) void *forward_102;

__attribute__((visibility("hidden"))) void *forward_103;

__attribute__((visibility("hidden"))) void *forward_104;

__attribute__((visibility("hidden"))) void *forward_105;

__attribute__((visibility("hidden"))) void *forward_106;

__attribute__((visibility("hidden"))) void *forward_107;

__attribute__((visibility("hidden"))) void *forward_108;

__attribute__((visibility("hidden"))) void *forward_109;

__attribute__((visibility("hidden"))) void *forward_110;

__attribute__((visibility("hidden"))) void *forward_111;

__attribute__((visibility("hidden"))) void *forward_112;

__attribute__((visibility("hidden"))) void *forward_113;

__attribute__((visibility("hidden"))) void *forward_114;

__attribute__((visibility("hidden"))) void *forward_115;

__attribute__((visibility("hidden"))) void *forward_116;

__attribute__((visibility("hidden"))) void *forward_117;

__attribute__((visibility("hidden"))) void *forward_118;

__attribute__((visibility("hidden"))) void *forward_119;

__attribute__((visibility("hidden"))) void *forward_120;

__attribute__((visibility("hidden"))) void *forward_121;

__attribute__((visibility("hidden"))) void *forward_122;

__attribute__((visibility("hidden"))) void *forward_123;

__attribute__((visibility("hidden"))) void *forward_124;

__attribute__((visibility("hidden"))) void *forward_125;

__attribute__((visibility("hidden"))) void *forward_126;

__attribute__((visibility("hidden"))) void *forward_127;

__attribute__((visibility("hidden"))) void *forward_128;

__attribute__((visibility("hidden"))) void *forward_129;

__attribute__((visibility("hidden"))) void *forward_130;

__attribute__((visibility("hidden"))) void *forward_131;

__attribute__((visibility("hidden"))) void *forward_132;

__attribute__((visibility("hidden"))) void *forward_133;

__attribute__((visibility("hidden"))) void *forward_134;

__attribute__((visibility("hidden"))) void *forward_135;

__attribute__((visibility("hidden"))) void *forward_136;

__attribute__((visibility("hidden"))) void *forward_137;

__attribute__((visibility("hidden"))) void *forward_138;

__attribute__((visibility("hidden"))) void *forward_139;

__attribute__((visibility("hidden"))) void *forward_140;

__attribute__((visibility("hidden"))) void *forward_141;

__attribute__((visibility("hidden"))) void *forward_142;

__attribute__((visibility("hidden"))) void *forward_143;

__attribute__((visibility("hidden"))) void *forward_144;

__attribute__((visibility("hidden"))) void *forward_145;

__attribute__((visibility("hidden"))) void *forward_146;

__attribute__((visibility("hidden"))) void *forward_147;

__attribute__((visibility("hidden"))) void *forward_148;

__attribute__((visibility("hidden"))) void *forward_149;

__attribute__((visibility("hidden"))) void *forward_150;

__attribute__((visibility("hidden"))) void *forward_151;

__attribute__((visibility("hidden"))) void *forward_152;

__attribute__((visibility("hidden"))) void *forward_153;

__attribute__((visibility("hidden"))) void *forward_154;

__attribute__((visibility("hidden"))) void *forward_155;

__attribute__((visibility("hidden"))) void *forward_156;

__attribute__((visibility("hidden"))) void *forward_157;

__attribute__((visibility("hidden"))) void *forward_158;

__attribute__((visibility("hidden"))) void *forward_159;

__attribute__((visibility("hidden"))) void *forward_160;

__attribute__((visibility("hidden"))) void *forward_161;

__attribute__((visibility("hidden"))) void *forward_162;

__attribute__((visibility("hidden"))) void *forward_163;

__attribute__((visibility("hidden"))) void *forward_164;

__attribute__((visibility("hidden"))) void *forward_165;

__attribute__((visibility("hidden"))) void *forward_166;

__attribute__((visibility("hidden"))) void *forward_167;

__attribute__((visibility("hidden"))) void *forward_168;

__attribute__((visibility("hidden"))) void *forward_169;

__attribute__((visibility("hidden"))) void *forward_170;

__attribute__((visibility("hidden"))) void *forward_171;

__attribute__((visibility("hidden"))) void *forward_172;

__attribute__((visibility("hidden"))) void *forward_173;

__attribute__((visibility("hidden"))) void *forward_174;

__attribute__((visibility("hidden"))) void *forward_175;

__attribute__((visibility("hidden"))) void *forward_176;

__attribute__((visibility("hidden"))) void *forward_177;

__attribute__((visibility("hidden"))) void *forward_178;

__attribute__((visibility("hidden"))) void *forward_179;

__attribute__((visibility("hidden"))) void *forward_180;

__attribute__((visibility("hidden"))) void *forward_181;

__attribute__((visibility("hidden"))) void *forward_182;

__attribute__((visibility("hidden"))) void *forward_183;

__attribute__((visibility("hidden"))) void *forward_184;

__attribute__((visibility("hidden"))) void *forward_185;

__attribute__((visibility("hidden"))) void *forward_186;

__attribute__((visibility("hidden"))) void *forward_187;

__attribute__((visibility("hidden"))) void *forward_188;

__attribute__((visibility("hidden"))) void *forward_189;

__attribute__((visibility("hidden"))) void *forward_190;

__attribute__((visibility("hidden"))) void *forward_191;

__attribute__((visibility("hidden"))) void *forward_192;

__attribute__((visibility("hidden"))) void *forward_193;

__attribute__((visibility("hidden"))) void *forward_194;

__attribute__((visibility("hidden"))) void *forward_195;

__attribute__((visibility("hidden"))) void *forward_196;

__attribute__((visibility("hidden"))) void *forward_197;

__attribute__((visibility("hidden"))) void *forward_198;

__attribute__((visibility("hidden"))) void *forward_199;

__attribute__((visibility("hidden"))) void *forward_200;

__attribute__((visibility("hidden"))) void *forward_201;

__attribute__((visibility("hidden"))) void *forward_202;

__attribute__((visibility("hidden"))) void *forward_203;

__attribute__((visibility("hidden"))) void *forward_204;

__attribute__((visibility("hidden"))) void *forward_205;

__attribute__((visibility("hidden"))) void *forward_206;

__attribute__((visibility("hidden"))) void *forward_207;

__attribute__((visibility("hidden"))) void *forward_208;

__attribute__((visibility("hidden"))) void *forward_209;

__attribute__((visibility("hidden"))) void *forward_210;

__attribute__((visibility("hidden"))) void *forward_211;

__attribute__((visibility("hidden"))) void *forward_212;

__attribute__((visibility("hidden"))) void *forward_213;

__attribute__((visibility("hidden"))) void *forward_214;

__attribute__((visibility("hidden"))) void *forward_215;

__attribute__((visibility("hidden"))) void *forward_216;

__attribute__((visibility("hidden"))) void *forward_217;

__attribute__((visibility("hidden"))) void *forward_218;

__attribute__((visibility("hidden"))) void *forward_219;

__attribute__((visibility("hidden"))) void *forward_220;

__attribute__((visibility("hidden"))) void *forward_221;

__attribute__((visibility("hidden"))) void *forward_222;

__attribute__((visibility("hidden"))) void *forward_223;

__attribute__((visibility("hidden"))) void *forward_224;

__attribute__((visibility("hidden"))) void *forward_225;

__attribute__((visibility("hidden"))) void *forward_226;

__attribute__((visibility("hidden"))) void *forward_227;

__attribute__((visibility("hidden"))) void *forward_228;

__attribute__((visibility("hidden"))) void *forward_229;

__attribute__((visibility("hidden"))) void *forward_230;

__attribute__((visibility("hidden"))) void *forward_231;

__attribute__((visibility("hidden"))) void *forward_232;

__attribute__((visibility("hidden"))) void *forward_233;

__attribute__((visibility("hidden"))) void *forward_234;

__attribute__((visibility("hidden"))) void *forward_235;

__attribute__((visibility("hidden"))) void *forward_236;

__attribute__((visibility("hidden"))) void *forward_237;

__attribute__((visibility("hidden"))) void *forward_238;

__attribute__((visibility("hidden"))) void *forward_239;

__attribute__((visibility("hidden"))) void *forward_240;

__attribute__((visibility("hidden"))) void *forward_241;

__attribute__((visibility("hidden"))) void *forward_242;

__attribute__((visibility("hidden"))) void *forward_243;

__attribute__((visibility("hidden"))) void *forward_244;

__attribute__((visibility("hidden"))) void *forward_245;

__attribute__((visibility("hidden"))) void *forward_246;

__attribute__((visibility("hidden"))) void *forward_247;

__attribute__((visibility("hidden"))) void *forward_248;

__attribute__((visibility("hidden"))) void *forward_249;

__attribute__((visibility("hidden"))) void *forward_250;

__attribute__((visibility("hidden"))) void *forward_251;

__attribute__((visibility("hidden"))) void *forward_252;

__attribute__((visibility("hidden"))) void *forward_253;

__attribute__((visibility("hidden"))) void *forward_254;

__attribute__((visibility("hidden"))) void *forward_255;

__attribute__((visibility("hidden"))) void *forward_256;

__attribute__((visibility("hidden"))) void *forward_257;

__attribute__((visibility("hidden"))) void *forward_258;

__attribute__((visibility("hidden"))) void *forward_259;

__attribute__((visibility("hidden"))) void *forward_260;

__attribute__((visibility("hidden"))) void *forward_261;

__attribute__((visibility("hidden"))) void *forward_262;

__attribute__((visibility("hidden"))) void *forward_263;

__attribute__((visibility("hidden"))) void *forward_264;

__attribute__((visibility("hidden"))) void *forward_265;

__attribute__((visibility("hidden"))) void *forward_266;

__attribute__((visibility("hidden"))) void *forward_267;

__attribute__((visibility("hidden"))) void *forward_268;

__attribute__((visibility("hidden"))) void *forward_269;

__attribute__((visibility("hidden"))) void *forward_270;

__attribute__((visibility("hidden"))) void *forward_271;

__attribute__((visibility("hidden"))) void *forward_272;

__attribute__((visibility("hidden"))) void *forward_273;

__attribute__((visibility("hidden"))) void *forward_274;

__attribute__((visibility("hidden"))) void *forward_275;

__attribute__((visibility("hidden"))) void *forward_276;

__attribute__((visibility("hidden"))) void *forward_277;

__attribute__((visibility("hidden"))) void *forward_278;

__attribute__((visibility("hidden"))) void *forward_279;

__attribute__((visibility("hidden"))) void *forward_280;

__attribute__((visibility("hidden"))) void *forward_281;

__attribute__((visibility("hidden"))) void *forward_282;

__attribute__((visibility("hidden"))) void *forward_283;

__attribute__((visibility("hidden"))) void *forward_284;

__attribute__((visibility("hidden"))) void *forward_285;

__attribute__((visibility("hidden"))) void *forward_286;

__attribute__((visibility("hidden"))) void *forward_287;

__attribute__((visibility("hidden"))) void *forward_288;

__attribute__((visibility("hidden"))) void *forward_289;

__attribute__((visibility("hidden"))) void *forward_290;

__attribute__((visibility("hidden"))) void *forward_291;

__attribute__((visibility("hidden"))) void *forward_292;

__attribute__((visibility("hidden"))) void *forward_293;

__attribute__((visibility("hidden"))) void *forward_294;

__attribute__((visibility("hidden"))) void *forward_295;

__attribute__((visibility("hidden"))) void *forward_296;

__attribute__((visibility("hidden"))) void *forward_297;

__attribute__((visibility("hidden"))) void *forward_298;

__attribute__((visibility("hidden"))) void *forward_299;

__attribute__((visibility("hidden"))) void *forward_300;

__attribute__((visibility("hidden"))) void *forward_301;

__attribute__((visibility("hidden"))) void *forward_302;

__attribute__((visibility("hidden"))) void *forward_303;

__attribute__((visibility("hidden"))) void *forward_304;

__attribute__((visibility("hidden"))) void *forward_305;

__attribute__((visibility("hidden"))) void *forward_306;

__attribute__((visibility("hidden"))) void *forward_307;

__attribute__((visibility("hidden"))) void *forward_308;

__attribute__((visibility("hidden"))) void *forward_309;

__attribute__((visibility("hidden"))) void *forward_310;

__attribute__((visibility("hidden"))) void *forward_311;

__attribute__((visibility("hidden"))) void *forward_312;

__attribute__((visibility("hidden"))) void *forward_313;

__attribute__((visibility("hidden"))) void *forward_314;

__attribute__((visibility("hidden"))) void *forward_315;

__attribute__((visibility("hidden"))) void *forward_316;

__attribute__((visibility("hidden"))) void *forward_317;

__attribute__((visibility("hidden"))) void *forward_318;

__attribute__((visibility("hidden"))) void *forward_319;

__attribute__((visibility("hidden"))) void *forward_320;

__attribute__((visibility("hidden"))) void *forward_321;

__attribute__((visibility("hidden"))) void *forward_322;

__attribute__((visibility("hidden"))) void *forward_323;

__attribute__((visibility("hidden"))) void *forward_324;

__attribute__((visibility("hidden"))) void *forward_325;

__attribute__((visibility("hidden"))) void *forward_326;

__attribute__((visibility("hidden"))) void *forward_327;

__attribute__((visibility("hidden"))) void *forward_328;

__attribute__((visibility("hidden"))) void *forward_329;

__attribute__((visibility("hidden"))) void *forward_330;

__attribute__((visibility("hidden"))) void *forward_331;

__attribute__((visibility("hidden"))) void *forward_332;

__attribute__((visibility("hidden"))) void *forward_333;

__attribute__((visibility("hidden"))) void *forward_334;

__attribute__((visibility("hidden"))) void *forward_335;

__attribute__((visibility("hidden"))) void *forward_336;

__attribute__((visibility("hidden"))) void *forward_337;

__attribute__((visibility("hidden"))) void *forward_338;

__attribute__((visibility("hidden"))) void *forward_339;

__attribute__((visibility("hidden"))) void *forward_340;

__attribute__((visibility("hidden"))) void *forward_341;

__attribute__((visibility("hidden"))) void *forward_342;

__attribute__((visibility("hidden"))) void *forward_343;

__attribute__((visibility("hidden"))) void *forward_344;

__attribute__((visibility("hidden"))) void *forward_345;

__attribute__((visibility("hidden"))) void *forward_346;

__attribute__((visibility("hidden"))) void *forward_347;

__attribute__((visibility("hidden"))) void *forward_348;

__attribute__((visibility("hidden"))) void *forward_349;

__attribute__((visibility("hidden"))) void *forward_350;

__attribute__((visibility("hidden"))) void *forward_351;

__attribute__((visibility("hidden"))) void *forward_352;

__attribute__((visibility("hidden"))) void *forward_353;

__attribute__((visibility("hidden"))) void *forward_354;

__attribute__((visibility("hidden"))) void *forward_355;

__attribute__((visibility("hidden"))) void *forward_356;

__attribute__((visibility("hidden"))) void *forward_357;

__attribute__((visibility("hidden"))) void *forward_358;

__attribute__((visibility("hidden"))) void *forward_359;

__attribute__((visibility("hidden"))) void *forward_360;

__attribute__((visibility("hidden"))) void *forward_361;

__attribute__((visibility("hidden"))) void *forward_362;

__attribute__((visibility("hidden"))) void *forward_363;

__attribute__((visibility("hidden"))) void *forward_364;

__attribute__((visibility("hidden"))) void *forward_365;

__attribute__((visibility("hidden"))) void *forward_366;

__attribute__((visibility("hidden"))) void *forward_367;

__attribute__((visibility("hidden"))) void *forward_368;

__attribute__((visibility("hidden"))) void *forward_369;

__attribute__((visibility("hidden"))) void *forward_370;

__attribute__((visibility("hidden"))) void *forward_371;

__attribute__((visibility("hidden"))) void *forward_372;

__attribute__((visibility("hidden"))) void *forward_373;

__attribute__((visibility("hidden"))) void *forward_374;

__attribute__((visibility("hidden"))) void *forward_375;

__attribute__((visibility("hidden"))) void *forward_376;

__attribute__((visibility("hidden"))) void *forward_377;

__attribute__((visibility("hidden"))) void *forward_378;

__attribute__((visibility("hidden"))) void *forward_379;

__attribute__((visibility("hidden"))) void *forward_380;

__attribute__((visibility("hidden"))) void *forward_381;

__attribute__((visibility("hidden"))) void *forward_382;

__attribute__((visibility("hidden"))) void *forward_383;

__attribute__((visibility("hidden"))) void *forward_384;

__attribute__((visibility("hidden"))) void *forward_385;

__attribute__((visibility("hidden"))) void *forward_386;

__attribute__((visibility("hidden"))) void *forward_387;

__attribute__((visibility("hidden"))) void *forward_388;

__attribute__((visibility("hidden"))) void *forward_389;

__attribute__((visibility("hidden"))) void *forward_390;

__attribute__((visibility("hidden"))) void *forward_391;

__attribute__((visibility("hidden"))) void *forward_392;

__attribute__((visibility("hidden"))) void *forward_393;

__attribute__((visibility("hidden"))) void *forward_394;

__attribute__((visibility("hidden"))) void *forward_395;

__attribute__((visibility("hidden"))) void *forward_396;

__attribute__((visibility("hidden"))) void *forward_397;

__attribute__((visibility("hidden"))) void *forward_398;

__attribute__((visibility("hidden"))) void *forward_399;

__attribute__((visibility("hidden"))) void *forward_400;

__attribute__((visibility("hidden"))) void *forward_401;

__attribute__((visibility("hidden"))) void *forward_402;

__attribute__((visibility("hidden"))) void *forward_403;

__attribute__((visibility("hidden"))) void *forward_404;

__attribute__((visibility("hidden"))) void *forward_405;

__attribute__((visibility("hidden"))) void *forward_406;

__attribute__((visibility("hidden"))) void *forward_407;

__attribute__((visibility("hidden"))) void *forward_408;

__attribute__((visibility("hidden"))) void *forward_409;

__attribute__((visibility("hidden"))) void *forward_410;

__attribute__((visibility("hidden"))) void *forward_411;

__attribute__((visibility("hidden"))) void *forward_412;

__attribute__((visibility("hidden"))) void *forward_413;

__attribute__((visibility("hidden"))) void *forward_414;

__attribute__((visibility("hidden"))) void *forward_415;

__attribute__((visibility("hidden"))) void *forward_416;

__attribute__((visibility("hidden"))) void *forward_417;

__attribute__((visibility("hidden"))) void *forward_418;

__attribute__((visibility("hidden"))) void *forward_419;

__attribute__((visibility("hidden"))) void *forward_420;

__attribute__((visibility("hidden"))) void *forward_421;

__attribute__((visibility("hidden"))) void *forward_422;

__attribute__((visibility("hidden"))) void *forward_423;

__attribute__((visibility("hidden"))) void *forward_424;

__attribute__((visibility("hidden"))) void *forward_425;

__attribute__((visibility("hidden"))) void *forward_426;

__attribute__((visibility("hidden"))) void *forward_427;

__attribute__((visibility("hidden"))) void *forward_428;

__attribute__((visibility("hidden"))) void *forward_429;

__attribute__((visibility("hidden"))) void *forward_430;

__attribute__((visibility("hidden"))) void *forward_431;

__attribute__((visibility("hidden"))) void *forward_432;

__attribute__((visibility("hidden"))) void *forward_433;

__attribute__((visibility("hidden"))) void *forward_434;

__attribute__((visibility("hidden"))) void *forward_435;

__attribute__((visibility("hidden"))) void *forward_436;

__attribute__((visibility("hidden"))) void *forward_437;

__attribute__((visibility("hidden"))) void *forward_438;

__attribute__((visibility("hidden"))) void *forward_439;

__attribute__((visibility("hidden"))) void *forward_440;

__attribute__((visibility("hidden"))) void *forward_441;

__attribute__((visibility("hidden"))) void *forward_442;

__attribute__((visibility("hidden"))) void *forward_443;

__attribute__((visibility("hidden"))) void *forward_444;

__attribute__((visibility("hidden"))) void *forward_445;

__attribute__((visibility("hidden"))) void *forward_446;

__attribute__((visibility("hidden"))) void *forward_447;

__attribute__((visibility("hidden"))) void *forward_448;

__attribute__((visibility("hidden"))) void *forward_449;

__attribute__((visibility("hidden"))) void *forward_450;

__attribute__((visibility("hidden"))) void *forward_451;

__attribute__((visibility("hidden"))) void *forward_452;

__attribute__((visibility("hidden"))) void *forward_453;

__attribute__((visibility("hidden"))) void *forward_454;

__attribute__((visibility("hidden"))) void *forward_455;

__attribute__((visibility("hidden"))) void *forward_456;

__attribute__((visibility("hidden"))) void *forward_457;

__attribute__((visibility("hidden"))) void *forward_458;

__attribute__((visibility("hidden"))) void *forward_459;

__attribute__((visibility("hidden"))) void *forward_460;

__attribute__((visibility("hidden"))) void *forward_461;

__attribute__((visibility("hidden"))) void *forward_462;

__attribute__((visibility("hidden"))) void *forward_463;

__attribute__((visibility("hidden"))) void *forward_464;

__attribute__((visibility("hidden"))) void *forward_465;

__attribute__((visibility("hidden"))) void *forward_466;

__attribute__((visibility("hidden"))) void *forward_467;

__attribute__((visibility("hidden"))) void *forward_468;

__attribute__((visibility("hidden"))) void *forward_469;

__attribute__((visibility("hidden"))) void *forward_470;

__attribute__((visibility("hidden"))) void *forward_471;

__attribute__((visibility("hidden"))) void *forward_472;

__attribute__((visibility("hidden"))) void *forward_473;

__attribute__((visibility("hidden"))) void *forward_474;

__attribute__((visibility("hidden"))) void *forward_475;

__attribute__((visibility("hidden"))) void *forward_476;

__attribute__((visibility("hidden"))) void *forward_477;

__attribute__((visibility("hidden"))) void *forward_478;

__attribute__((visibility("hidden"))) void *forward_479;

__attribute__((visibility("hidden"))) void *forward_480;

__attribute__((visibility("hidden"))) void *forward_481;

__attribute__((visibility("hidden"))) void *forward_482;

__attribute__((visibility("hidden"))) void *forward_483;

__attribute__((visibility("hidden"))) void *forward_484;

__attribute__((visibility("hidden"))) void *forward_485;

__attribute__((visibility("hidden"))) void *forward_486;

__attribute__((visibility("hidden"))) void *forward_487;

__attribute__((visibility("hidden"))) void *forward_488;

__attribute__((visibility("hidden"))) void *forward_489;

__attribute__((visibility("hidden"))) void *forward_490;

__attribute__((visibility("hidden"))) void *forward_491;

__attribute__((visibility("hidden"))) void *forward_492;

__attribute__((visibility("hidden"))) void *forward_493;

__attribute__((visibility("hidden"))) void *forward_494;

__attribute__((visibility("hidden"))) void *forward_495;

__attribute__((visibility("hidden"))) void *forward_496;

__attribute__((visibility("hidden"))) void *forward_497;

__attribute__((visibility("hidden"))) void *forward_498;

__attribute__((visibility("hidden"))) void *forward_499;

__attribute__((visibility("hidden"))) void *forward_500;

__attribute__((visibility("hidden"))) void *forward_501;

__attribute__((visibility("hidden"))) void *forward_502;

__attribute__((visibility("hidden"))) void *forward_503;

__attribute__((visibility("hidden"))) void *forward_504;

__attribute__((visibility("hidden"))) void *forward_505;

__attribute__((visibility("hidden"))) void *forward_506;

__attribute__((visibility("hidden"))) void *forward_507;

__attribute__((visibility("hidden"))) void *forward_508;

__attribute__((visibility("hidden"))) void *forward_509;

__attribute__((visibility("hidden"))) void *forward_510;

__attribute__((visibility("hidden"))) void *forward_511;

__attribute__((visibility("hidden"))) void *forward_512;

__attribute__((visibility("hidden"))) void *forward_513;

__attribute__((visibility("hidden"))) void *forward_514;

__attribute__((visibility("hidden"))) void *forward_515;

__attribute__((visibility("hidden"))) void *forward_516;

__attribute__((visibility("hidden"))) void *forward_517;

__attribute__((visibility("hidden"))) void *forward_518;

__attribute__((visibility("hidden"))) void *forward_519;

__attribute__((visibility("hidden"))) void *forward_520;

__attribute__((visibility("hidden"))) void *forward_521;

__attribute__((visibility("hidden"))) void *forward_522;

__attribute__((visibility("hidden"))) void *forward_523;

__attribute__((visibility("hidden"))) void *forward_524;

__attribute__((visibility("hidden"))) void *forward_525;

__attribute__((visibility("hidden"))) void *forward_526;

__attribute__((visibility("hidden"))) void *forward_527;

__attribute__((visibility("hidden"))) void *forward_528;

__attribute__((visibility("hidden"))) void *forward_529;

__attribute__((visibility("hidden"))) void *forward_530;

__attribute__((visibility("hidden"))) void *forward_531;

__attribute__((visibility("hidden"))) void *forward_532;

__attribute__((visibility("hidden"))) void *forward_533;

__attribute__((visibility("hidden"))) void *forward_534;

__attribute__((visibility("hidden"))) void *forward_535;

__attribute__((visibility("hidden"))) void *forward_536;

__attribute__((visibility("hidden"))) void *forward_537;

__attribute__((visibility("hidden"))) void *forward_538;

__attribute__((visibility("hidden"))) void *forward_539;

__attribute__((visibility("hidden"))) void *forward_540;

__attribute__((visibility("hidden"))) void *forward_541;

__attribute__((visibility("hidden"))) void *forward_542;

__attribute__((visibility("hidden"))) void *forward_543;

__attribute__((visibility("hidden"))) void *forward_544;

__attribute__((visibility("hidden"))) void *forward_545;

__attribute__((visibility("hidden"))) void *forward_546;

__attribute__((visibility("hidden"))) void *forward_547;

__attribute__((visibility("hidden"))) void *forward_548;

__attribute__((visibility("hidden"))) void *forward_549;

__attribute__((visibility("hidden"))) void *forward_550;

__attribute__((visibility("hidden"))) void *forward_551;

__attribute__((visibility("hidden"))) void *forward_552;

__attribute__((visibility("hidden"))) void *forward_553;

__attribute__((visibility("hidden"))) void *forward_554;

__attribute__((visibility("hidden"))) void *forward_555;

__attribute__((visibility("hidden"))) void *forward_556;

__attribute__((visibility("hidden"))) void *forward_557;

__attribute__((visibility("hidden"))) void *forward_558;

__attribute__((visibility("hidden"))) void *forward_559;

__attribute__((visibility("hidden"))) void *forward_560;

__attribute__((visibility("hidden"))) void *forward_561;

__attribute__((visibility("hidden"))) void *forward_562;

__attribute__((visibility("hidden"))) void *forward_563;

__attribute__((visibility("hidden"))) void *forward_564;

__attribute__((visibility("hidden"))) void *forward_565;

__attribute__((visibility("hidden"))) void *forward_566;

__attribute__((visibility("hidden"))) void *forward_567;

__attribute__((visibility("hidden"))) void *forward_568;

__attribute__((visibility("hidden"))) void *forward_569;

__attribute__((visibility("hidden"))) void *forward_570;

__attribute__((visibility("hidden"))) void *forward_571;

__attribute__((visibility("hidden"))) void *forward_572;

__attribute__((visibility("hidden"))) void *forward_573;

__attribute__((visibility("hidden"))) void *forward_574;

__attribute__((visibility("hidden"))) void *forward_575;

__attribute__((visibility("hidden"))) void *forward_576;

__attribute__((visibility("hidden"))) void *forward_577;

__attribute__((visibility("hidden"))) void *forward_578;

__attribute__((visibility("hidden"))) void *forward_579;

__attribute__((visibility("hidden"))) void *forward_580;

__attribute__((visibility("hidden"))) void *forward_581;

__attribute__((visibility("hidden"))) void *forward_582;

__attribute__((visibility("hidden"))) void *forward_583;

__attribute__((visibility("hidden"))) void *forward_584;

__attribute__((visibility("hidden"))) void *forward_585;

__attribute__((visibility("hidden"))) void *forward_586;

__attribute__((visibility("hidden"))) void *forward_587;

__attribute__((visibility("hidden"))) void *forward_588;

__attribute__((visibility("hidden"))) void *forward_589;

__attribute__((visibility("hidden"))) void *forward_590;

__attribute__((visibility("hidden"))) void *forward_591;

__attribute__((visibility("hidden"))) void *forward_592;

__attribute__((visibility("hidden"))) void *forward_593;

__attribute__((visibility("hidden"))) void *forward_594;

__attribute__((visibility("hidden"))) void *forward_595;

__attribute__((visibility("hidden"))) void *forward_596;

__attribute__((visibility("hidden"))) void *forward_597;

__attribute__((visibility("hidden"))) void *forward_598;

__attribute__((visibility("hidden"))) void *forward_599;

__attribute__((visibility("hidden"))) void *forward_600;

__attribute__((visibility("hidden"))) void *forward_601;

__attribute__((visibility("hidden"))) void *forward_602;

__attribute__((visibility("hidden"))) void *forward_603;

__attribute__((visibility("hidden"))) void *forward_604;

__attribute__((visibility("hidden"))) void *forward_605;

__attribute__((visibility("hidden"))) void *forward_606;

__attribute__((visibility("hidden"))) void *forward_607;

__attribute__((visibility("hidden"))) void *forward_608;

__attribute__((visibility("hidden"))) void *forward_609;

__attribute__((visibility("hidden"))) void *forward_610;

__attribute__((visibility("hidden"))) void *forward_611;

__attribute__((visibility("hidden"))) void *forward_612;

__attribute__((visibility("hidden"))) void *forward_613;

__attribute__((visibility("hidden"))) void *forward_614;

__attribute__((visibility("hidden"))) void *forward_615;

__attribute__((visibility("hidden"))) void *forward_616;

__attribute__((visibility("hidden"))) void *forward_617;

__attribute__((visibility("hidden"))) void *forward_618;

__attribute__((visibility("hidden"))) void *forward_619;

__attribute__((visibility("hidden"))) void *forward_620;

__attribute__((visibility("hidden"))) void *forward_621;

__attribute__((visibility("hidden"))) void *forward_622;

__attribute__((visibility("hidden"))) void *forward_623;

__attribute__((visibility("hidden"))) void *forward_624;

__attribute__((visibility("hidden"))) void *forward_625;

__attribute__((visibility("hidden"))) void *forward_626;

__attribute__((visibility("hidden"))) void *forward_627;

__attribute__((visibility("hidden"))) void *forward_628;

__attribute__((visibility("hidden"))) void *forward_629;

__attribute__((visibility("hidden"))) void *forward_630;

__attribute__((visibility("hidden"))) void *forward_631;

__attribute__((visibility("hidden"))) void *forward_632;

__attribute__((visibility("hidden"))) void *forward_633;

__attribute__((visibility("hidden"))) void *forward_634;

__attribute__((visibility("hidden"))) void *forward_635;

__attribute__((visibility("hidden"))) void *forward_636;

__attribute__((visibility("hidden"))) void *forward_637;

__attribute__((visibility("hidden"))) void *forward_638;

__attribute__((visibility("hidden"))) void *forward_639;

__attribute__((visibility("hidden"))) void *forward_640;

__attribute__((visibility("hidden"))) void *forward_641;

__attribute__((visibility("hidden"))) void *forward_642;

__attribute__((visibility("hidden"))) void *forward_643;

__attribute__((visibility("hidden"))) void *forward_644;

__attribute__((visibility("hidden"))) void *forward_645;

__attribute__((visibility("hidden"))) void *forward_646;

__attribute__((visibility("hidden"))) void *forward_647;

__attribute__((visibility("hidden"))) void *forward_648;
__attribute__((constructor)) static void initialize_forwards(void){init();
forward_0=native_dlsym(driver,"cuArray3DCreate");
forward_1=native_dlsym(driver,"cuArray3DCreate_v2");
forward_2=native_dlsym(driver,"cuArray3DGetDescriptor");
forward_3=native_dlsym(driver,"cuArray3DGetDescriptor_v2");
forward_4=native_dlsym(driver,"cuArrayCreate");
forward_5=native_dlsym(driver,"cuArrayCreate_v2");
forward_6=native_dlsym(driver,"cuArrayDestroy");
forward_7=native_dlsym(driver,"cuArrayGetDescriptor");
forward_8=native_dlsym(driver,"cuArrayGetDescriptor_v2");
forward_9=native_dlsym(driver,"cuArrayGetMemoryRequirements");
forward_10=native_dlsym(driver,"cuArrayGetPlane");
forward_11=native_dlsym(driver,"cuArrayGetSparseProperties");
forward_12=native_dlsym(driver,"cuCoredumpGetAttribute");
forward_13=native_dlsym(driver,"cuCoredumpGetAttributeGlobal");
forward_14=native_dlsym(driver,"cuCoredumpSetAttribute");
forward_15=native_dlsym(driver,"cuCoredumpSetAttributeGlobal");
forward_16=native_dlsym(driver,"cuCtxAttach");
forward_17=native_dlsym(driver,"cuCtxCreate");
forward_18=native_dlsym(driver,"cuCtxCreate_v2");
forward_19=native_dlsym(driver,"cuCtxCreate_v3");
forward_20=native_dlsym(driver,"cuCtxDestroy");
forward_21=native_dlsym(driver,"cuCtxDestroy_v2");
forward_22=native_dlsym(driver,"cuCtxDetach");
forward_23=native_dlsym(driver,"cuCtxDisablePeerAccess");
forward_24=native_dlsym(driver,"cuCtxEnablePeerAccess");
forward_25=native_dlsym(driver,"cuCtxFromGreenCtx");
forward_26=native_dlsym(driver,"cuCtxGetApiVersion");
forward_27=native_dlsym(driver,"cuCtxGetCacheConfig");
forward_28=native_dlsym(driver,"cuCtxGetCurrent");
forward_29=native_dlsym(driver,"cuCtxGetDevResource");
forward_30=native_dlsym(driver,"cuCtxGetDevice");
forward_31=native_dlsym(driver,"cuCtxGetExecAffinity");
forward_32=native_dlsym(driver,"cuCtxGetFlags");
forward_33=native_dlsym(driver,"cuCtxGetId");
forward_34=native_dlsym(driver,"cuCtxGetLimit");
forward_35=native_dlsym(driver,"cuCtxGetSharedMemConfig");
forward_36=native_dlsym(driver,"cuCtxGetStreamPriorityRange");
forward_37=native_dlsym(driver,"cuCtxPopCurrent");
forward_38=native_dlsym(driver,"cuCtxPopCurrent_v2");
forward_39=native_dlsym(driver,"cuCtxPushCurrent");
forward_40=native_dlsym(driver,"cuCtxPushCurrent_v2");
forward_41=native_dlsym(driver,"cuCtxResetPersistingL2Cache");
forward_42=native_dlsym(driver,"cuCtxSetCacheConfig");
forward_43=native_dlsym(driver,"cuCtxSetCurrent");
forward_44=native_dlsym(driver,"cuCtxSetFlags");
forward_45=native_dlsym(driver,"cuCtxSetLimit");
forward_46=native_dlsym(driver,"cuCtxSetSharedMemConfig");
forward_47=native_dlsym(driver,"cuCtxSynchronize");
forward_48=native_dlsym(driver,"cuDestroyExternalMemory");
forward_49=native_dlsym(driver,"cuDestroyExternalSemaphore");
forward_50=native_dlsym(driver,"cuDevResourceGenerateDesc");
forward_51=native_dlsym(driver,"cuDevSmResourceSplitByCount");
forward_52=native_dlsym(driver,"cuDeviceCanAccessPeer");
forward_53=native_dlsym(driver,"cuDeviceComputeCapability");
forward_54=native_dlsym(driver,"cuDeviceGet");
forward_55=native_dlsym(driver,"cuDeviceGetAttribute");
forward_56=native_dlsym(driver,"cuDeviceGetByPCIBusId");
forward_57=native_dlsym(driver,"cuDeviceGetCount");
forward_58=native_dlsym(driver,"cuDeviceGetDefaultMemPool");
forward_59=native_dlsym(driver,"cuDeviceGetDevResource");
forward_60=native_dlsym(driver,"cuDeviceGetExecAffinitySupport");
forward_61=native_dlsym(driver,"cuDeviceGetGraphMemAttribute");
forward_62=native_dlsym(driver,"cuDeviceGetLuid");
forward_63=native_dlsym(driver,"cuDeviceGetMemPool");
forward_64=native_dlsym(driver,"cuDeviceGetName");
forward_65=native_dlsym(driver,"cuDeviceGetNvSciSyncAttributes");
forward_66=native_dlsym(driver,"cuDeviceGetP2PAttribute");
forward_67=native_dlsym(driver,"cuDeviceGetPCIBusId");
forward_68=native_dlsym(driver,"cuDeviceGetProperties");
forward_69=native_dlsym(driver,"cuDeviceGetTexture1DLinearMaxWidth");
forward_70=native_dlsym(driver,"cuDeviceGetUuid");
forward_71=native_dlsym(driver,"cuDeviceGetUuid_v2");
forward_72=native_dlsym(driver,"cuDeviceGraphMemTrim");
forward_73=native_dlsym(driver,"cuDevicePrimaryCtxGetState");
forward_74=native_dlsym(driver,"cuDevicePrimaryCtxRelease");
forward_75=native_dlsym(driver,"cuDevicePrimaryCtxRelease_v2");
forward_76=native_dlsym(driver,"cuDevicePrimaryCtxReset");
forward_77=native_dlsym(driver,"cuDevicePrimaryCtxReset_v2");
forward_78=native_dlsym(driver,"cuDevicePrimaryCtxRetain");
forward_79=native_dlsym(driver,"cuDevicePrimaryCtxSetFlags");
forward_80=native_dlsym(driver,"cuDevicePrimaryCtxSetFlags_v2");
forward_81=native_dlsym(driver,"cuDeviceRegisterAsyncNotification");
forward_82=native_dlsym(driver,"cuDeviceSetGraphMemAttribute");
forward_83=native_dlsym(driver,"cuDeviceSetMemPool");
forward_84=native_dlsym(driver,"cuDeviceTotalMem");
forward_85=native_dlsym(driver,"cuDeviceTotalMem_v2");
forward_86=native_dlsym(driver,"cuDeviceUnregisterAsyncNotification");
forward_87=native_dlsym(driver,"cuDriverGetVersion");
forward_88=native_dlsym(driver,"cuEGLApiInit");
forward_89=native_dlsym(driver,"cuEGLStreamConsumerAcquireFrame");
forward_90=native_dlsym(driver,"cuEGLStreamConsumerConnect");
forward_91=native_dlsym(driver,"cuEGLStreamConsumerConnectWithFlags");
forward_92=native_dlsym(driver,"cuEGLStreamConsumerDisconnect");
forward_93=native_dlsym(driver,"cuEGLStreamConsumerReleaseFrame");
forward_94=native_dlsym(driver,"cuEGLStreamProducerConnect");
forward_95=native_dlsym(driver,"cuEGLStreamProducerDisconnect");
forward_96=native_dlsym(driver,"cuEGLStreamProducerPresentFrame");
forward_97=native_dlsym(driver,"cuEGLStreamProducerReturnFrame");
forward_98=native_dlsym(driver,"cuEventCreate");
forward_99=native_dlsym(driver,"cuEventDestroy");
forward_100=native_dlsym(driver,"cuEventDestroy_v2");
forward_101=native_dlsym(driver,"cuEventElapsedTime");
forward_102=native_dlsym(driver,"cuEventQuery");
forward_103=native_dlsym(driver,"cuEventRecord");
forward_104=native_dlsym(driver,"cuEventRecordWithFlags");
forward_105=native_dlsym(driver,"cuEventRecordWithFlags_ptsz");
forward_106=native_dlsym(driver,"cuEventRecord_ptsz");
forward_107=native_dlsym(driver,"cuEventSynchronize");
forward_108=native_dlsym(driver,"cuExternalMemoryGetMappedBuffer");
forward_109=native_dlsym(driver,"cuExternalMemoryGetMappedMipmappedArray");
forward_110=native_dlsym(driver,"cuFlushGPUDirectRDMAWrites");
forward_111=native_dlsym(driver,"cuFuncGetAttribute");
forward_112=native_dlsym(driver,"cuFuncGetModule");
forward_113=native_dlsym(driver,"cuFuncGetName");
forward_114=native_dlsym(driver,"cuFuncGetParamInfo");
forward_115=native_dlsym(driver,"cuFuncIsLoaded");
forward_116=native_dlsym(driver,"cuFuncLoad");
forward_117=native_dlsym(driver,"cuFuncSetAttribute");
forward_118=native_dlsym(driver,"cuFuncSetBlockShape");
forward_119=native_dlsym(driver,"cuFuncSetCacheConfig");
forward_120=native_dlsym(driver,"cuFuncSetSharedMemConfig");
forward_121=native_dlsym(driver,"cuFuncSetSharedSize");
forward_122=native_dlsym(driver,"cuGLCtxCreate");
forward_123=native_dlsym(driver,"cuGLCtxCreate_v2");
forward_124=native_dlsym(driver,"cuGLGetDevices");
forward_125=native_dlsym(driver,"cuGLGetDevices_v2");
forward_126=native_dlsym(driver,"cuGLInit");
forward_127=native_dlsym(driver,"cuGLMapBufferObject");
forward_128=native_dlsym(driver,"cuGLMapBufferObjectAsync");
forward_129=native_dlsym(driver,"cuGLMapBufferObjectAsync_v2");
forward_130=native_dlsym(driver,"cuGLMapBufferObjectAsync_v2_ptsz");
forward_131=native_dlsym(driver,"cuGLMapBufferObject_v2");
forward_132=native_dlsym(driver,"cuGLMapBufferObject_v2_ptds");
forward_133=native_dlsym(driver,"cuGLRegisterBufferObject");
forward_134=native_dlsym(driver,"cuGLSetBufferObjectMapFlags");
forward_135=native_dlsym(driver,"cuGLUnmapBufferObject");
forward_136=native_dlsym(driver,"cuGLUnmapBufferObjectAsync");
forward_137=native_dlsym(driver,"cuGLUnregisterBufferObject");
forward_138=native_dlsym(driver,"cuGetErrorName");
forward_139=native_dlsym(driver,"cuGetErrorString");
forward_140=native_dlsym(driver,"cuGetExportTable");
forward_141=native_dlsym(driver,"cuGraphAddBatchMemOpNode");
forward_142=native_dlsym(driver,"cuGraphAddChildGraphNode");
forward_143=native_dlsym(driver,"cuGraphAddDependencies");
forward_144=native_dlsym(driver,"cuGraphAddDependencies_v2");
forward_145=native_dlsym(driver,"cuGraphAddEmptyNode");
forward_146=native_dlsym(driver,"cuGraphAddEventRecordNode");
forward_147=native_dlsym(driver,"cuGraphAddEventWaitNode");
forward_148=native_dlsym(driver,"cuGraphAddExternalSemaphoresSignalNode");
forward_149=native_dlsym(driver,"cuGraphAddExternalSemaphoresWaitNode");
forward_150=native_dlsym(driver,"cuGraphAddHostNode");
forward_151=native_dlsym(driver,"cuGraphAddKernelNode");
forward_152=native_dlsym(driver,"cuGraphAddKernelNode_v2");
forward_153=native_dlsym(driver,"cuGraphAddMemAllocNode");
forward_154=native_dlsym(driver,"cuGraphAddMemFreeNode");
forward_155=native_dlsym(driver,"cuGraphAddMemcpyNode");
forward_156=native_dlsym(driver,"cuGraphAddMemsetNode");
forward_157=native_dlsym(driver,"cuGraphAddNode");
forward_158=native_dlsym(driver,"cuGraphAddNode_v2");
forward_159=native_dlsym(driver,"cuGraphBatchMemOpNodeGetParams");
forward_160=native_dlsym(driver,"cuGraphBatchMemOpNodeSetParams");
forward_161=native_dlsym(driver,"cuGraphChildGraphNodeGetGraph");
forward_162=native_dlsym(driver,"cuGraphClone");
forward_163=native_dlsym(driver,"cuGraphConditionalHandleCreate");
forward_164=native_dlsym(driver,"cuGraphCreate");
forward_165=native_dlsym(driver,"cuGraphDebugDotPrint");
forward_166=native_dlsym(driver,"cuGraphDestroy");
forward_167=native_dlsym(driver,"cuGraphDestroyNode");
forward_168=native_dlsym(driver,"cuGraphEventRecordNodeGetEvent");
forward_169=native_dlsym(driver,"cuGraphEventRecordNodeSetEvent");
forward_170=native_dlsym(driver,"cuGraphEventWaitNodeGetEvent");
forward_171=native_dlsym(driver,"cuGraphEventWaitNodeSetEvent");
forward_172=native_dlsym(driver,"cuGraphExecBatchMemOpNodeSetParams");
forward_173=native_dlsym(driver,"cuGraphExecChildGraphNodeSetParams");
forward_174=native_dlsym(driver,"cuGraphExecDestroy");
forward_175=native_dlsym(driver,"cuGraphExecEventRecordNodeSetEvent");
forward_176=native_dlsym(driver,"cuGraphExecEventWaitNodeSetEvent");
forward_177=native_dlsym(driver,"cuGraphExecExternalSemaphoresSignalNodeSetParams");
forward_178=native_dlsym(driver,"cuGraphExecExternalSemaphoresWaitNodeSetParams");
forward_179=native_dlsym(driver,"cuGraphExecGetFlags");
forward_180=native_dlsym(driver,"cuGraphExecHostNodeSetParams");
forward_181=native_dlsym(driver,"cuGraphExecKernelNodeSetParams");
forward_182=native_dlsym(driver,"cuGraphExecKernelNodeSetParams_v2");
forward_183=native_dlsym(driver,"cuGraphExecMemcpyNodeSetParams");
forward_184=native_dlsym(driver,"cuGraphExecMemsetNodeSetParams");
forward_185=native_dlsym(driver,"cuGraphExecNodeSetParams");
forward_186=native_dlsym(driver,"cuGraphExecUpdate");
forward_187=native_dlsym(driver,"cuGraphExecUpdate_v2");
forward_188=native_dlsym(driver,"cuGraphExternalSemaphoresSignalNodeGetParams");
forward_189=native_dlsym(driver,"cuGraphExternalSemaphoresSignalNodeSetParams");
forward_190=native_dlsym(driver,"cuGraphExternalSemaphoresWaitNodeGetParams");
forward_191=native_dlsym(driver,"cuGraphExternalSemaphoresWaitNodeSetParams");
forward_192=native_dlsym(driver,"cuGraphGetEdges");
forward_193=native_dlsym(driver,"cuGraphGetEdges_v2");
forward_194=native_dlsym(driver,"cuGraphGetNodes");
forward_195=native_dlsym(driver,"cuGraphGetRootNodes");
forward_196=native_dlsym(driver,"cuGraphHostNodeGetParams");
forward_197=native_dlsym(driver,"cuGraphHostNodeSetParams");
forward_198=native_dlsym(driver,"cuGraphInstantiate");
forward_199=native_dlsym(driver,"cuGraphInstantiateWithFlags");
forward_200=native_dlsym(driver,"cuGraphInstantiateWithParams");
forward_201=native_dlsym(driver,"cuGraphInstantiateWithParams_ptsz");
forward_202=native_dlsym(driver,"cuGraphInstantiate_v2");
forward_203=native_dlsym(driver,"cuGraphKernelNodeCopyAttributes");
forward_204=native_dlsym(driver,"cuGraphKernelNodeGetAttribute");
forward_205=native_dlsym(driver,"cuGraphKernelNodeGetParams");
forward_206=native_dlsym(driver,"cuGraphKernelNodeGetParams_v2");
forward_207=native_dlsym(driver,"cuGraphKernelNodeSetAttribute");
forward_208=native_dlsym(driver,"cuGraphKernelNodeSetParams");
forward_209=native_dlsym(driver,"cuGraphKernelNodeSetParams_v2");
forward_210=native_dlsym(driver,"cuGraphLaunch");
forward_211=native_dlsym(driver,"cuGraphLaunch_ptsz");
forward_212=native_dlsym(driver,"cuGraphMemAllocNodeGetParams");
forward_213=native_dlsym(driver,"cuGraphMemFreeNodeGetParams");
forward_214=native_dlsym(driver,"cuGraphMemcpyNodeGetParams");
forward_215=native_dlsym(driver,"cuGraphMemcpyNodeSetParams");
forward_216=native_dlsym(driver,"cuGraphMemsetNodeGetParams");
forward_217=native_dlsym(driver,"cuGraphMemsetNodeSetParams");
forward_218=native_dlsym(driver,"cuGraphNodeFindInClone");
forward_219=native_dlsym(driver,"cuGraphNodeGetDependencies");
forward_220=native_dlsym(driver,"cuGraphNodeGetDependencies_v2");
forward_221=native_dlsym(driver,"cuGraphNodeGetDependentNodes");
forward_222=native_dlsym(driver,"cuGraphNodeGetDependentNodes_v2");
forward_223=native_dlsym(driver,"cuGraphNodeGetEnabled");
forward_224=native_dlsym(driver,"cuGraphNodeGetType");
forward_225=native_dlsym(driver,"cuGraphNodeSetEnabled");
forward_226=native_dlsym(driver,"cuGraphNodeSetParams");
forward_227=native_dlsym(driver,"cuGraphReleaseUserObject");
forward_228=native_dlsym(driver,"cuGraphRemoveDependencies");
forward_229=native_dlsym(driver,"cuGraphRemoveDependencies_v2");
forward_230=native_dlsym(driver,"cuGraphRetainUserObject");
forward_231=native_dlsym(driver,"cuGraphUpload");
forward_232=native_dlsym(driver,"cuGraphUpload_ptsz");
forward_233=native_dlsym(driver,"cuGraphicsEGLRegisterImage");
forward_234=native_dlsym(driver,"cuGraphicsGLRegisterBuffer");
forward_235=native_dlsym(driver,"cuGraphicsGLRegisterImage");
forward_236=native_dlsym(driver,"cuGraphicsMapResources");
forward_237=native_dlsym(driver,"cuGraphicsMapResources_ptsz");
forward_238=native_dlsym(driver,"cuGraphicsResourceGetMappedEglFrame");
forward_239=native_dlsym(driver,"cuGraphicsResourceGetMappedMipmappedArray");
forward_240=native_dlsym(driver,"cuGraphicsResourceGetMappedPointer");
forward_241=native_dlsym(driver,"cuGraphicsResourceGetMappedPointer_v2");
forward_242=native_dlsym(driver,"cuGraphicsResourceSetMapFlags");
forward_243=native_dlsym(driver,"cuGraphicsResourceSetMapFlags_v2");
forward_244=native_dlsym(driver,"cuGraphicsSubResourceGetMappedArray");
forward_245=native_dlsym(driver,"cuGraphicsUnmapResources");
forward_246=native_dlsym(driver,"cuGraphicsUnmapResources_ptsz");
forward_247=native_dlsym(driver,"cuGraphicsUnregisterResource");
forward_248=native_dlsym(driver,"cuGraphicsVDPAURegisterOutputSurface");
forward_249=native_dlsym(driver,"cuGraphicsVDPAURegisterVideoSurface");
forward_250=native_dlsym(driver,"cuGreenCtxCreate");
forward_251=native_dlsym(driver,"cuGreenCtxDestroy");
forward_252=native_dlsym(driver,"cuGreenCtxGetDevResource");
forward_253=native_dlsym(driver,"cuGreenCtxRecordEvent");
forward_254=native_dlsym(driver,"cuGreenCtxWaitEvent");
forward_255=native_dlsym(driver,"cuImportExternalMemory");
forward_256=native_dlsym(driver,"cuImportExternalSemaphore");
forward_257=native_dlsym(driver,"cuInit");
forward_258=native_dlsym(driver,"cuIpcCloseMemHandle");
forward_259=native_dlsym(driver,"cuIpcGetEventHandle");
forward_260=native_dlsym(driver,"cuIpcGetMemHandle");
forward_261=native_dlsym(driver,"cuIpcOpenEventHandle");
forward_262=native_dlsym(driver,"cuIpcOpenMemHandle");
forward_263=native_dlsym(driver,"cuIpcOpenMemHandle_v2");
forward_264=native_dlsym(driver,"cuKernelGetAttribute");
forward_265=native_dlsym(driver,"cuKernelGetFunction");
forward_266=native_dlsym(driver,"cuKernelGetName");
forward_267=native_dlsym(driver,"cuKernelGetParamInfo");
forward_268=native_dlsym(driver,"cuKernelSetAttribute");
forward_269=native_dlsym(driver,"cuKernelSetCacheConfig");
forward_270=native_dlsym(driver,"cuLaunch");
forward_271=native_dlsym(driver,"cuLaunchCooperativeKernel");
forward_272=native_dlsym(driver,"cuLaunchCooperativeKernelMultiDevice");
forward_273=native_dlsym(driver,"cuLaunchCooperativeKernel_ptsz");
forward_274=native_dlsym(driver,"cuLaunchGrid");
forward_275=native_dlsym(driver,"cuLaunchGridAsync");
forward_276=native_dlsym(driver,"cuLaunchHostFunc");
forward_277=native_dlsym(driver,"cuLaunchHostFunc_ptsz");
forward_278=native_dlsym(driver,"cuLaunchKernel");
forward_279=native_dlsym(driver,"cuLaunchKernelEx");
forward_280=native_dlsym(driver,"cuLaunchKernelEx_ptsz");
forward_281=native_dlsym(driver,"cuLaunchKernel_ptsz");
forward_282=native_dlsym(driver,"cuLibraryEnumerateKernels");
forward_283=native_dlsym(driver,"cuLibraryGetGlobal");
forward_284=native_dlsym(driver,"cuLibraryGetKernel");
forward_285=native_dlsym(driver,"cuLibraryGetKernelCount");
forward_286=native_dlsym(driver,"cuLibraryGetManaged");
forward_287=native_dlsym(driver,"cuLibraryGetModule");
forward_288=native_dlsym(driver,"cuLibraryGetUnifiedFunction");
forward_289=native_dlsym(driver,"cuLibraryLoadFromFile");
forward_290=native_dlsym(driver,"cuLibraryUnload");
forward_291=native_dlsym(driver,"cuLinkAddFile");
forward_292=native_dlsym(driver,"cuLinkAddFile_v2");
forward_293=native_dlsym(driver,"cuLinkComplete");
forward_294=native_dlsym(driver,"cuLinkCreate");
forward_295=native_dlsym(driver,"cuLinkCreate_v2");
forward_296=native_dlsym(driver,"cuLinkDestroy");
forward_297=native_dlsym(driver,"cuMemAddressFree");
forward_298=native_dlsym(driver,"cuMemAddressReserve");
forward_299=native_dlsym(driver,"cuMemAdvise");
forward_300=native_dlsym(driver,"cuMemAdvise_v2");
forward_301=native_dlsym(driver,"cuMemAlloc");
forward_302=native_dlsym(driver,"cuMemAllocAsync");
forward_303=native_dlsym(driver,"cuMemAllocAsync_ptsz");
forward_304=native_dlsym(driver,"cuMemAllocFromPoolAsync");
forward_305=native_dlsym(driver,"cuMemAllocFromPoolAsync_ptsz");
forward_306=native_dlsym(driver,"cuMemAllocHost");
forward_307=native_dlsym(driver,"cuMemAllocHost_v2");
forward_308=native_dlsym(driver,"cuMemAllocManaged");
forward_309=native_dlsym(driver,"cuMemAllocPitch");
forward_310=native_dlsym(driver,"cuMemAllocPitch_v2");
forward_311=native_dlsym(driver,"cuMemAlloc_v2");
forward_312=native_dlsym(driver,"cuMemCreate");
forward_313=native_dlsym(driver,"cuMemExportToShareableHandle");
forward_314=native_dlsym(driver,"cuMemFree");
forward_315=native_dlsym(driver,"cuMemFreeAsync");
forward_316=native_dlsym(driver,"cuMemFreeAsync_ptsz");
forward_317=native_dlsym(driver,"cuMemFreeHost");
forward_318=native_dlsym(driver,"cuMemFree_v2");
forward_319=native_dlsym(driver,"cuMemGetAccess");
forward_320=native_dlsym(driver,"cuMemGetAddressRange");
forward_321=native_dlsym(driver,"cuMemGetAddressRange_v2");
forward_322=native_dlsym(driver,"cuMemGetAllocationGranularity");
forward_323=native_dlsym(driver,"cuMemGetAllocationPropertiesFromHandle");
forward_324=native_dlsym(driver,"cuMemGetAttribute");
forward_325=native_dlsym(driver,"cuMemGetAttribute_v2");
forward_326=native_dlsym(driver,"cuMemGetHandleForAddressRange");
forward_327=native_dlsym(driver,"cuMemGetInfo");
forward_328=native_dlsym(driver,"cuMemGetInfo_v2");
forward_329=native_dlsym(driver,"cuMemHostAlloc");
forward_330=native_dlsym(driver,"cuMemHostGetDevicePointer");
forward_331=native_dlsym(driver,"cuMemHostGetDevicePointer_v2");
forward_332=native_dlsym(driver,"cuMemHostGetFlags");
forward_333=native_dlsym(driver,"cuMemHostRegister");
forward_334=native_dlsym(driver,"cuMemHostRegister_v2");
forward_335=native_dlsym(driver,"cuMemHostUnregister");
forward_336=native_dlsym(driver,"cuMemImportFromShareableHandle");
forward_337=native_dlsym(driver,"cuMemMap");
forward_338=native_dlsym(driver,"cuMemMapArrayAsync");
forward_339=native_dlsym(driver,"cuMemMapArrayAsync_ptsz");
forward_340=native_dlsym(driver,"cuMemPoolCreate");
forward_341=native_dlsym(driver,"cuMemPoolDestroy");
forward_342=native_dlsym(driver,"cuMemPoolExportPointer");
forward_343=native_dlsym(driver,"cuMemPoolExportToShareableHandle");
forward_344=native_dlsym(driver,"cuMemPoolGetAccess");
forward_345=native_dlsym(driver,"cuMemPoolGetAttribute");
forward_346=native_dlsym(driver,"cuMemPoolImportFromShareableHandle");
forward_347=native_dlsym(driver,"cuMemPoolImportPointer");
forward_348=native_dlsym(driver,"cuMemPoolSetAccess");
forward_349=native_dlsym(driver,"cuMemPoolSetAttribute");
forward_350=native_dlsym(driver,"cuMemPoolTrimTo");
forward_351=native_dlsym(driver,"cuMemPrefetchAsync");
forward_352=native_dlsym(driver,"cuMemPrefetchAsync_ptsz");
forward_353=native_dlsym(driver,"cuMemPrefetchAsync_v2");
forward_354=native_dlsym(driver,"cuMemPrefetchAsync_v2_ptsz");
forward_355=native_dlsym(driver,"cuMemRangeGetAttribute");
forward_356=native_dlsym(driver,"cuMemRangeGetAttributes");
forward_357=native_dlsym(driver,"cuMemRelease");
forward_358=native_dlsym(driver,"cuMemRetainAllocationHandle");
forward_359=native_dlsym(driver,"cuMemSetAccess");
forward_360=native_dlsym(driver,"cuMemUnmap");
forward_361=native_dlsym(driver,"cuMemcpy");
forward_362=native_dlsym(driver,"cuMemcpy2D");
forward_363=native_dlsym(driver,"cuMemcpy2DAsync");
forward_364=native_dlsym(driver,"cuMemcpy2DAsync_v2");
forward_365=native_dlsym(driver,"cuMemcpy2DAsync_v2_ptsz");
forward_366=native_dlsym(driver,"cuMemcpy2DUnaligned");
forward_367=native_dlsym(driver,"cuMemcpy2DUnaligned_v2");
forward_368=native_dlsym(driver,"cuMemcpy2DUnaligned_v2_ptds");
forward_369=native_dlsym(driver,"cuMemcpy2D_v2");
forward_370=native_dlsym(driver,"cuMemcpy2D_v2_ptds");
forward_371=native_dlsym(driver,"cuMemcpy3D");
forward_372=native_dlsym(driver,"cuMemcpy3DAsync");
forward_373=native_dlsym(driver,"cuMemcpy3DAsync_v2");
forward_374=native_dlsym(driver,"cuMemcpy3DAsync_v2_ptsz");
forward_375=native_dlsym(driver,"cuMemcpy3DPeer");
forward_376=native_dlsym(driver,"cuMemcpy3DPeerAsync");
forward_377=native_dlsym(driver,"cuMemcpy3DPeerAsync_ptsz");
forward_378=native_dlsym(driver,"cuMemcpy3DPeer_ptds");
forward_379=native_dlsym(driver,"cuMemcpy3D_v2");
forward_380=native_dlsym(driver,"cuMemcpy3D_v2_ptds");
forward_381=native_dlsym(driver,"cuMemcpyAsync");
forward_382=native_dlsym(driver,"cuMemcpyAsync_ptsz");
forward_383=native_dlsym(driver,"cuMemcpyAtoA");
forward_384=native_dlsym(driver,"cuMemcpyAtoA_v2");
forward_385=native_dlsym(driver,"cuMemcpyAtoA_v2_ptds");
forward_386=native_dlsym(driver,"cuMemcpyAtoD");
forward_387=native_dlsym(driver,"cuMemcpyAtoD_v2");
forward_388=native_dlsym(driver,"cuMemcpyAtoD_v2_ptds");
forward_389=native_dlsym(driver,"cuMemcpyAtoH");
forward_390=native_dlsym(driver,"cuMemcpyAtoHAsync");
forward_391=native_dlsym(driver,"cuMemcpyAtoHAsync_v2");
forward_392=native_dlsym(driver,"cuMemcpyAtoHAsync_v2_ptsz");
forward_393=native_dlsym(driver,"cuMemcpyAtoH_v2");
forward_394=native_dlsym(driver,"cuMemcpyAtoH_v2_ptds");
forward_395=native_dlsym(driver,"cuMemcpyDtoA");
forward_396=native_dlsym(driver,"cuMemcpyDtoA_v2");
forward_397=native_dlsym(driver,"cuMemcpyDtoA_v2_ptds");
forward_398=native_dlsym(driver,"cuMemcpyDtoD");
forward_399=native_dlsym(driver,"cuMemcpyDtoDAsync");
forward_400=native_dlsym(driver,"cuMemcpyDtoDAsync_v2");
forward_401=native_dlsym(driver,"cuMemcpyDtoDAsync_v2_ptsz");
forward_402=native_dlsym(driver,"cuMemcpyDtoD_v2");
forward_403=native_dlsym(driver,"cuMemcpyDtoD_v2_ptds");
forward_404=native_dlsym(driver,"cuMemcpyDtoH");
forward_405=native_dlsym(driver,"cuMemcpyDtoHAsync");
forward_406=native_dlsym(driver,"cuMemcpyDtoHAsync_v2");
forward_407=native_dlsym(driver,"cuMemcpyDtoHAsync_v2_ptsz");
forward_408=native_dlsym(driver,"cuMemcpyDtoH_v2");
forward_409=native_dlsym(driver,"cuMemcpyDtoH_v2_ptds");
forward_410=native_dlsym(driver,"cuMemcpyHtoA");
forward_411=native_dlsym(driver,"cuMemcpyHtoAAsync");
forward_412=native_dlsym(driver,"cuMemcpyHtoAAsync_v2");
forward_413=native_dlsym(driver,"cuMemcpyHtoAAsync_v2_ptsz");
forward_414=native_dlsym(driver,"cuMemcpyHtoA_v2");
forward_415=native_dlsym(driver,"cuMemcpyHtoA_v2_ptds");
forward_416=native_dlsym(driver,"cuMemcpyHtoD");
forward_417=native_dlsym(driver,"cuMemcpyHtoDAsync");
forward_418=native_dlsym(driver,"cuMemcpyHtoDAsync_v2");
forward_419=native_dlsym(driver,"cuMemcpyHtoDAsync_v2_ptsz");
forward_420=native_dlsym(driver,"cuMemcpyHtoD_v2");
forward_421=native_dlsym(driver,"cuMemcpyHtoD_v2_ptds");
forward_422=native_dlsym(driver,"cuMemcpyPeer");
forward_423=native_dlsym(driver,"cuMemcpyPeerAsync");
forward_424=native_dlsym(driver,"cuMemcpyPeerAsync_ptsz");
forward_425=native_dlsym(driver,"cuMemcpyPeer_ptds");
forward_426=native_dlsym(driver,"cuMemcpy_ptds");
forward_427=native_dlsym(driver,"cuMemsetD16");
forward_428=native_dlsym(driver,"cuMemsetD16Async");
forward_429=native_dlsym(driver,"cuMemsetD16Async_ptsz");
forward_430=native_dlsym(driver,"cuMemsetD16_v2");
forward_431=native_dlsym(driver,"cuMemsetD16_v2_ptds");
forward_432=native_dlsym(driver,"cuMemsetD2D16");
forward_433=native_dlsym(driver,"cuMemsetD2D16Async");
forward_434=native_dlsym(driver,"cuMemsetD2D16Async_ptsz");
forward_435=native_dlsym(driver,"cuMemsetD2D16_v2");
forward_436=native_dlsym(driver,"cuMemsetD2D16_v2_ptds");
forward_437=native_dlsym(driver,"cuMemsetD2D32");
forward_438=native_dlsym(driver,"cuMemsetD2D32Async");
forward_439=native_dlsym(driver,"cuMemsetD2D32Async_ptsz");
forward_440=native_dlsym(driver,"cuMemsetD2D32_v2");
forward_441=native_dlsym(driver,"cuMemsetD2D32_v2_ptds");
forward_442=native_dlsym(driver,"cuMemsetD2D8");
forward_443=native_dlsym(driver,"cuMemsetD2D8Async");
forward_444=native_dlsym(driver,"cuMemsetD2D8Async_ptsz");
forward_445=native_dlsym(driver,"cuMemsetD2D8_v2");
forward_446=native_dlsym(driver,"cuMemsetD2D8_v2_ptds");
forward_447=native_dlsym(driver,"cuMemsetD32");
forward_448=native_dlsym(driver,"cuMemsetD32Async");
forward_449=native_dlsym(driver,"cuMemsetD32Async_ptsz");
forward_450=native_dlsym(driver,"cuMemsetD32_v2");
forward_451=native_dlsym(driver,"cuMemsetD32_v2_ptds");
forward_452=native_dlsym(driver,"cuMemsetD8");
forward_453=native_dlsym(driver,"cuMemsetD8Async");
forward_454=native_dlsym(driver,"cuMemsetD8Async_ptsz");
forward_455=native_dlsym(driver,"cuMemsetD8_v2");
forward_456=native_dlsym(driver,"cuMemsetD8_v2_ptds");
forward_457=native_dlsym(driver,"cuMipmappedArrayCreate");
forward_458=native_dlsym(driver,"cuMipmappedArrayDestroy");
forward_459=native_dlsym(driver,"cuMipmappedArrayGetLevel");
forward_460=native_dlsym(driver,"cuMipmappedArrayGetMemoryRequirements");
forward_461=native_dlsym(driver,"cuMipmappedArrayGetSparseProperties");
forward_462=native_dlsym(driver,"cuModuleEnumerateFunctions");
forward_463=native_dlsym(driver,"cuModuleGetFunction");
forward_464=native_dlsym(driver,"cuModuleGetFunctionCount");
forward_465=native_dlsym(driver,"cuModuleGetGlobal");
forward_466=native_dlsym(driver,"cuModuleGetGlobal_v2");
forward_467=native_dlsym(driver,"cuModuleGetLoadingMode");
forward_468=native_dlsym(driver,"cuModuleGetSurfRef");
forward_469=native_dlsym(driver,"cuModuleGetTexRef");
forward_470=native_dlsym(driver,"cuModuleLoad");
forward_471=native_dlsym(driver,"cuModuleLoadFatBinary");
forward_472=native_dlsym(driver,"cuModuleUnload");
forward_473=native_dlsym(driver,"cuMulticastAddDevice");
forward_474=native_dlsym(driver,"cuMulticastBindAddr");
forward_475=native_dlsym(driver,"cuMulticastBindMem");
forward_476=native_dlsym(driver,"cuMulticastCreate");
forward_477=native_dlsym(driver,"cuMulticastGetGranularity");
forward_478=native_dlsym(driver,"cuMulticastUnbind");
forward_479=native_dlsym(driver,"cuOccupancyAvailableDynamicSMemPerBlock");
forward_480=native_dlsym(driver,"cuOccupancyMaxActiveBlocksPerMultiprocessor");
forward_481=native_dlsym(driver,"cuOccupancyMaxActiveBlocksPerMultiprocessorWithFlags");
forward_482=native_dlsym(driver,"cuOccupancyMaxActiveClusters");
forward_483=native_dlsym(driver,"cuOccupancyMaxPotentialBlockSize");
forward_484=native_dlsym(driver,"cuOccupancyMaxPotentialBlockSizeWithFlags");
forward_485=native_dlsym(driver,"cuOccupancyMaxPotentialClusterSize");
forward_486=native_dlsym(driver,"cuParamSetSize");
forward_487=native_dlsym(driver,"cuParamSetTexRef");
forward_488=native_dlsym(driver,"cuParamSetf");
forward_489=native_dlsym(driver,"cuParamSeti");
forward_490=native_dlsym(driver,"cuParamSetv");
forward_491=native_dlsym(driver,"cuPointerGetAttribute");
forward_492=native_dlsym(driver,"cuPointerGetAttributes");
forward_493=native_dlsym(driver,"cuPointerSetAttribute");
forward_494=native_dlsym(driver,"cuProfilerInitialize");
forward_495=native_dlsym(driver,"cuProfilerStart");
forward_496=native_dlsym(driver,"cuProfilerStop");
forward_497=native_dlsym(driver,"cuSignalExternalSemaphoresAsync");
forward_498=native_dlsym(driver,"cuSignalExternalSemaphoresAsync_ptsz");
forward_499=native_dlsym(driver,"cuStreamAddCallback");
forward_500=native_dlsym(driver,"cuStreamAddCallback_ptsz");
forward_501=native_dlsym(driver,"cuStreamAttachMemAsync");
forward_502=native_dlsym(driver,"cuStreamAttachMemAsync_ptsz");
forward_503=native_dlsym(driver,"cuStreamBatchMemOp");
forward_504=native_dlsym(driver,"cuStreamBatchMemOp_ptsz");
forward_505=native_dlsym(driver,"cuStreamBatchMemOp_v2");
forward_506=native_dlsym(driver,"cuStreamBatchMemOp_v2_ptsz");
forward_507=native_dlsym(driver,"cuStreamBeginCapture");
forward_508=native_dlsym(driver,"cuStreamBeginCaptureToGraph");
forward_509=native_dlsym(driver,"cuStreamBeginCaptureToGraph_ptsz");
forward_510=native_dlsym(driver,"cuStreamBeginCapture_ptsz");
forward_511=native_dlsym(driver,"cuStreamBeginCapture_v2");
forward_512=native_dlsym(driver,"cuStreamBeginCapture_v2_ptsz");
forward_513=native_dlsym(driver,"cuStreamCopyAttributes");
forward_514=native_dlsym(driver,"cuStreamCopyAttributes_ptsz");
forward_515=native_dlsym(driver,"cuStreamCreate");
forward_516=native_dlsym(driver,"cuStreamCreateWithPriority");
forward_517=native_dlsym(driver,"cuStreamDestroy");
forward_518=native_dlsym(driver,"cuStreamDestroy_v2");
forward_519=native_dlsym(driver,"cuStreamEndCapture");
forward_520=native_dlsym(driver,"cuStreamEndCapture_ptsz");
forward_521=native_dlsym(driver,"cuStreamGetAttribute");
forward_522=native_dlsym(driver,"cuStreamGetAttribute_ptsz");
forward_523=native_dlsym(driver,"cuStreamGetCaptureInfo");
forward_524=native_dlsym(driver,"cuStreamGetCaptureInfo_ptsz");
forward_525=native_dlsym(driver,"cuStreamGetCaptureInfo_v2");
forward_526=native_dlsym(driver,"cuStreamGetCaptureInfo_v2_ptsz");
forward_527=native_dlsym(driver,"cuStreamGetCaptureInfo_v3");
forward_528=native_dlsym(driver,"cuStreamGetCaptureInfo_v3_ptsz");
forward_529=native_dlsym(driver,"cuStreamGetCtx");
forward_530=native_dlsym(driver,"cuStreamGetCtx_ptsz");
forward_531=native_dlsym(driver,"cuStreamGetFlags");
forward_532=native_dlsym(driver,"cuStreamGetFlags_ptsz");
forward_533=native_dlsym(driver,"cuStreamGetGreenCtx");
forward_534=native_dlsym(driver,"cuStreamGetId");
forward_535=native_dlsym(driver,"cuStreamGetId_ptsz");
forward_536=native_dlsym(driver,"cuStreamGetPriority");
forward_537=native_dlsym(driver,"cuStreamGetPriority_ptsz");
forward_538=native_dlsym(driver,"cuStreamIsCapturing");
forward_539=native_dlsym(driver,"cuStreamIsCapturing_ptsz");
forward_540=native_dlsym(driver,"cuStreamQuery");
forward_541=native_dlsym(driver,"cuStreamQuery_ptsz");
forward_542=native_dlsym(driver,"cuStreamSetAttribute");
forward_543=native_dlsym(driver,"cuStreamSetAttribute_ptsz");
forward_544=native_dlsym(driver,"cuStreamSynchronize");
forward_545=native_dlsym(driver,"cuStreamSynchronize_ptsz");
forward_546=native_dlsym(driver,"cuStreamUpdateCaptureDependencies");
forward_547=native_dlsym(driver,"cuStreamUpdateCaptureDependencies_ptsz");
forward_548=native_dlsym(driver,"cuStreamUpdateCaptureDependencies_v2");
forward_549=native_dlsym(driver,"cuStreamUpdateCaptureDependencies_v2_ptsz");
forward_550=native_dlsym(driver,"cuStreamWaitEvent");
forward_551=native_dlsym(driver,"cuStreamWaitEvent_ptsz");
forward_552=native_dlsym(driver,"cuStreamWaitValue32");
forward_553=native_dlsym(driver,"cuStreamWaitValue32_ptsz");
forward_554=native_dlsym(driver,"cuStreamWaitValue32_v2");
forward_555=native_dlsym(driver,"cuStreamWaitValue32_v2_ptsz");
forward_556=native_dlsym(driver,"cuStreamWaitValue64");
forward_557=native_dlsym(driver,"cuStreamWaitValue64_ptsz");
forward_558=native_dlsym(driver,"cuStreamWaitValue64_v2");
forward_559=native_dlsym(driver,"cuStreamWaitValue64_v2_ptsz");
forward_560=native_dlsym(driver,"cuStreamWriteValue32");
forward_561=native_dlsym(driver,"cuStreamWriteValue32_ptsz");
forward_562=native_dlsym(driver,"cuStreamWriteValue32_v2");
forward_563=native_dlsym(driver,"cuStreamWriteValue32_v2_ptsz");
forward_564=native_dlsym(driver,"cuStreamWriteValue64");
forward_565=native_dlsym(driver,"cuStreamWriteValue64_ptsz");
forward_566=native_dlsym(driver,"cuStreamWriteValue64_v2");
forward_567=native_dlsym(driver,"cuStreamWriteValue64_v2_ptsz");
forward_568=native_dlsym(driver,"cuSurfObjectCreate");
forward_569=native_dlsym(driver,"cuSurfObjectDestroy");
forward_570=native_dlsym(driver,"cuSurfObjectGetResourceDesc");
forward_571=native_dlsym(driver,"cuSurfRefGetArray");
forward_572=native_dlsym(driver,"cuSurfRefSetArray");
forward_573=native_dlsym(driver,"cuTensorMapEncodeIm2col");
forward_574=native_dlsym(driver,"cuTensorMapEncodeTiled");
forward_575=native_dlsym(driver,"cuTensorMapReplaceAddress");
forward_576=native_dlsym(driver,"cuTexObjectCreate");
forward_577=native_dlsym(driver,"cuTexObjectDestroy");
forward_578=native_dlsym(driver,"cuTexObjectGetResourceDesc");
forward_579=native_dlsym(driver,"cuTexObjectGetResourceViewDesc");
forward_580=native_dlsym(driver,"cuTexObjectGetTextureDesc");
forward_581=native_dlsym(driver,"cuTexRefCreate");
forward_582=native_dlsym(driver,"cuTexRefDestroy");
forward_583=native_dlsym(driver,"cuTexRefGetAddress");
forward_584=native_dlsym(driver,"cuTexRefGetAddressMode");
forward_585=native_dlsym(driver,"cuTexRefGetAddress_v2");
forward_586=native_dlsym(driver,"cuTexRefGetArray");
forward_587=native_dlsym(driver,"cuTexRefGetBorderColor");
forward_588=native_dlsym(driver,"cuTexRefGetFilterMode");
forward_589=native_dlsym(driver,"cuTexRefGetFlags");
forward_590=native_dlsym(driver,"cuTexRefGetFormat");
forward_591=native_dlsym(driver,"cuTexRefGetMaxAnisotropy");
forward_592=native_dlsym(driver,"cuTexRefGetMipmapFilterMode");
forward_593=native_dlsym(driver,"cuTexRefGetMipmapLevelBias");
forward_594=native_dlsym(driver,"cuTexRefGetMipmapLevelClamp");
forward_595=native_dlsym(driver,"cuTexRefGetMipmappedArray");
forward_596=native_dlsym(driver,"cuTexRefSetAddress");
forward_597=native_dlsym(driver,"cuTexRefSetAddress2D");
forward_598=native_dlsym(driver,"cuTexRefSetAddress2D_v2");
forward_599=native_dlsym(driver,"cuTexRefSetAddress2D_v3");
forward_600=native_dlsym(driver,"cuTexRefSetAddressMode");
forward_601=native_dlsym(driver,"cuTexRefSetAddress_v2");
forward_602=native_dlsym(driver,"cuTexRefSetArray");
forward_603=native_dlsym(driver,"cuTexRefSetBorderColor");
forward_604=native_dlsym(driver,"cuTexRefSetFilterMode");
forward_605=native_dlsym(driver,"cuTexRefSetFlags");
forward_606=native_dlsym(driver,"cuTexRefSetFormat");
forward_607=native_dlsym(driver,"cuTexRefSetMaxAnisotropy");
forward_608=native_dlsym(driver,"cuTexRefSetMipmapFilterMode");
forward_609=native_dlsym(driver,"cuTexRefSetMipmapLevelBias");
forward_610=native_dlsym(driver,"cuTexRefSetMipmapLevelClamp");
forward_611=native_dlsym(driver,"cuTexRefSetMipmappedArray");
forward_612=native_dlsym(driver,"cuThreadExchangeStreamCaptureMode");
forward_613=native_dlsym(driver,"cuUserObjectCreate");
forward_614=native_dlsym(driver,"cuUserObjectRelease");
forward_615=native_dlsym(driver,"cuUserObjectRetain");
forward_616=native_dlsym(driver,"cuVDPAUCtxCreate");
forward_617=native_dlsym(driver,"cuVDPAUCtxCreate_v2");
forward_618=native_dlsym(driver,"cuVDPAUGetDevice");
forward_619=native_dlsym(driver,"cuWaitExternalSemaphoresAsync");
forward_620=native_dlsym(driver,"cuWaitExternalSemaphoresAsync_ptsz");
forward_621=native_dlsym(driver,"cudbgApiAttach");
forward_622=native_dlsym(driver,"cudbgApiClientPid");
forward_623=native_dlsym(driver,"cudbgApiClientRevision");
forward_624=native_dlsym(driver,"cudbgApiDetach");
forward_625=native_dlsym(driver,"cudbgApiInit");
forward_626=native_dlsym(driver,"cudbgAttachHandlerAvailable");
forward_627=native_dlsym(driver,"cudbgDebuggerCapabilities");
forward_628=native_dlsym(driver,"cudbgDebuggerInitialized");
forward_629=native_dlsym(driver,"cudbgDetachSuspendedDevicesMask");
forward_630=native_dlsym(driver,"cudbgEnableIntegratedMemcheck");
forward_631=native_dlsym(driver,"cudbgEnableLaunchBlocking");
forward_632=native_dlsym(driver,"cudbgEnablePreemptionDebugging");
forward_633=native_dlsym(driver,"cudbgGetAPI");
forward_634=native_dlsym(driver,"cudbgGetAPIVersion");
forward_635=native_dlsym(driver,"cudbgInjectionPath");
forward_636=native_dlsym(driver,"cudbgIpcFlag");
forward_637=native_dlsym(driver,"cudbgMain");
forward_638=native_dlsym(driver,"cudbgReportDriverApiError");
forward_639=native_dlsym(driver,"cudbgReportDriverApiErrorFlags");
forward_640=native_dlsym(driver,"cudbgReportDriverInternalError");
forward_641=native_dlsym(driver,"cudbgReportedDriverApiErrorCode");
forward_642=native_dlsym(driver,"cudbgReportedDriverApiErrorFuncNameAddr");
forward_643=native_dlsym(driver,"cudbgReportedDriverApiErrorFuncNameSize");
forward_644=native_dlsym(driver,"cudbgReportedDriverInternalErrorCode");
forward_645=native_dlsym(driver,"cudbgResumeForAttachDetach");
forward_646=native_dlsym(driver,"cudbgRpcEnabled");
forward_647=native_dlsym(driver,"cudbgSessionId");
forward_648=native_dlsym(driver,"cudbgUseExternalDebugger");}

int cuLibraryLoadData(void **lib,const void *code,void *a,void *b,unsigned int c,void *d,void *e,unsigned int f){init();int(*fn)(void**,const void*,void*,void*,unsigned int,void*,void*,unsigned int)=native_dlsym(driver,"cuLibraryLoadData");return fn(lib,code,a,b,c,d,e,f);}
