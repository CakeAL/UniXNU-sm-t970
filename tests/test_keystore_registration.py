"""Exercise actual board registration with IOKit lifecycle failure substitutes."""
from pathlib import Path
import subprocess
import tempfile
import unittest

DEVICE = Path(__file__).resolve().parents[1]


class Registration(unittest.TestCase):
    def test_ram_gate_lifecycle_and_counters(self):
        stub = r'''
#pragma once
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <cassert>
static bool flags=true,chosenOK=true,propertyOK=true,existing=false,preOK=true,providerOK=true;
static unsigned ephemeral=1,propertyLength=4,allocations,initializers,detaches,releases;
static int postError,fail;
extern "C" bool native_aks_state_enabled(void);
struct kmod_info_t { char name[16]; };
static int PE_parse_boot_argn(const char *name,void *out,unsigned size){
 assert(size==4 && (!strcmp(name,"sheng-aks")||!strcmp(name,"offline-key-events")));
 *(unsigned *)out=flags?1:0;return flags;
}
class OSData {public:unsigned getLength(){return propertyLength;}const void *getBytesNoCopy(){return &ephemeral;}};
static OSData data;
class IORegistryEntry {public:
 static IORegistryEntry *fromPath(const char *path,int){assert(!strcmp(path,"/chosen"));return chosenOK?new IORegistryEntry:nullptr;}
 OSData *getProperty(const char *name){assert(!strcmp(name,"ephemeral-storage"));return propertyOK?&data:nullptr;}
 void release(){delete this;}
};
static const int gIODTPlane=0;
#define OSDynamicCast(type,p) (p)
#define OSSafeReleaseNULL(p) do{if(p){(p)->release();(p)=nullptr;}}while(0)
class OSSymbol {public:static const OSSymbol *withCString(const char *name){assert(!strcmp(name,"AppleKeyStore"));return new OSSymbol;}void release()const{delete this;}};
class OSMetaClass {public:
 static bool getMetaClassWithName(const OSSymbol *){return existing;}
 static void *preModLoad(const char *){return preOK?(void *)1:nullptr;}
 static int postModLoad(void *){return postError;}
};
class IOService {public:
 static IOService *getResourceService(){static IOService provider;return providerOK?&provider:nullptr;}
 bool init(){return fail!=1;}
 bool attach(IOService *){return fail!=2;}
 bool start(IOService *){assert(native_aks_state_enabled());return fail!=3;}
 void detach(IOService *){++detaches;}
 void release(){++releases;delete this;}
};
static void IOLog(const char *,...){}
'''
        main = r'''
extern "C" { kmod_info_t g_kernel_kmod_info={"test"}; }
extern "C" void keyStoreStaticInit(void){++initializers;}
extern "C" IOService *native_keyevents_allocate(void){++allocations;return fail==4?nullptr:new IOService;}
static void reset(){
 if(keyService){keyService->release();keyService=nullptr;}
 attempted=false;stage=opens=refused=calls=lastSelector=lastResult=0;metaStatus=-1;
 flags=chosenOK=propertyOK=preOK=providerOK=true;existing=false;ephemeral=1;propertyLength=4;
 allocations=initializers=detaches=releases=0;postError=fail=0;
}
int main(){
 reset();flags=false;t970_keystore_start();assert(!attempted&&!initializers&&!native_aks_state_enabled());
 for(unsigned kind=0;kind<5;++kind){reset();switch(kind){case 0:chosenOK=false;break;case 1:propertyOK=false;break;case 2:propertyLength=8;break;case 3:ephemeral=0;break;case 4:ephemeral=2;break;}t970_keystore_start();assert(stage==1&&!initializers&&!allocations&&!native_aks_state_enabled());}
 reset();existing=true;t970_keystore_start();assert(stage==2&&!initializers&&!allocations);
 reset();preOK=false;t970_keystore_start();assert(stage==2&&!initializers&&!allocations);
 reset();providerOK=false;t970_keystore_start();assert(stage==2&&!initializers&&!allocations);
 reset();postError=17;t970_keystore_start();assert(stage==2&&metaStatus==17&&initializers==1&&!allocations);
 for(int error=1;error<=4;++error){reset();fail=error;t970_keystore_start();assert(stage==3&&!keyService&&!native_aks_state_enabled());assert(releases==(error==4?0:1));assert(detaches==(error==3?1:0));}
 reset();t970_keystore_start();assert(stage==4&&keyService&&native_aks_state_enabled());
 t970_keystore_start();assert(initializers==1&&allocations==1);
 native_aks_opened();native_keyevents_open_refused();native_aks_call(35,-7);
 assert(native_aks_lock_state()==3);
 char row[180];native_t970_keystore_state(row,sizeof(row));assert(strstr(row,"stage=4 meta=0 ready=1 open/refused/calls=1/1/1 sel=35 rc=fffffff9"));
 native_t970_keystore_state(nullptr,0);char tiny[3]={'a','b','c'};native_t970_keystore_state(tiny,1);assert(!tiny[0]&&tiny[1]=='b');
 flags=false;assert(!native_aks_state_enabled());reset();return 0;
}
'''
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'stub.h').write_text(stub)
            for name in ['IOKit/IOService.h','IOKit/IODeviceTreeSupport.h','IOKit/IOLib.h',
                         'libkern/c++/OSData.h','libkern/c++/OSSymbol.h','mach/kmod.h','pexpert/pexpert.h']:
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text('#include "stub.h"\n')
            source = root / 'test.cpp'
            source.write_text((DEVICE / 'package/T970Display/KeyStoreRegistration.cpp').read_text() + main)
            exe = root / 'test'
            subprocess.run(['xcrun','clang++','-std=c++17','-Wall','-Wextra','-Werror',
                            '-fsanitize=address,undefined','-I',str(root),str(source),'-o',str(exe)],check=True)
            subprocess.run([str(exe)],check=True)
