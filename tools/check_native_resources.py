"""Exercise bounded native resource reads without a game or network.

The isolated executable compiles the exact production backend with fake loader
objects and real Windows fault guards. It also exercises the production ticket
service/parser, including a paused pump and sequential 27-resource probes.
"""
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
PATCHES = ROOT / "red-side-patches"
VENDOR = ROOT / "vendor/world-builder"
SRC = VENDOR / "asi/cdmodkit"
COMPILER = Path("C:/msys64/ucrt64/bin/g++.exe")

HARNESS = r'''
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include "guard.h"
#include "mc_resource_probe.h"
#include <algorithm>
#include <cassert>
#include <cstring>
#include <deque>
#include <iostream>
#include <set>
#include <stdexcept>
namespace cdk { thread_local FaultInfo t_fault; thread_local GuardFrame* t_guardTop = nullptr; }
using namespace mc_resource_probe;
static int checks = 0;
void Pass(const char* name) { ++checks; std::cout << "PASS " << name << std::endl; }
static bool allocFault=false, normalizeFault=false, loadFault=false, metadataFault=false, readFault=false, releaseFault=false, missing=false, zero=false;
static int reads=0, releases=0, loads=0;
alignas(16) static uint8_t handlerData[64], workerData[8];
static uintptr_t handlerVt[1], workerVt[6];
static char pathBuffer[256]; static uintptr_t pathSd=(uintptr_t)pathBuffer;
void Fault() { RaiseException(0xE0424242u, 0, 0, nullptr); }
static uintptr_t Alloc(int n) { assert(n<128); if(allocFault) Fault(); return (uintptr_t)&pathSd; }
static void* Normalize(void* obj,const void*) { if(normalizeFault) Fault(); return obj; }
static void* Load(void*,void** out,void*,uint32_t flags) {
    ++loads; assert(flags==0); *out=missing?nullptr:handlerData; if(loadFault) Fault(); return *out;
}
static uint8_t Read(void*,void*,void* bytes,uint32_t capacity,uint32_t offset,uint32_t length) {
    ++reads; assert(capacity<=MAX_BYTES && !offset && !length); if(readFault) Fault();
    std::memset(bytes,zero?0:42,capacity); return 1;
}
static void Release(void*,int one) { ++releases; assert(one==1); if(releaseFault) Fault(); }
static uintptr_t g_base=0, kRva_StringDataAlloc=(uintptr_t)&Alloc, kRva_PathNormalizeCtor=(uintptr_t)&Normalize;
static void* g_resLoader=(void*)1;
static auto g_origResLoad=&Load;
__ADAPTER__
void Reset(uint32_t stored=8,uint32_t decoded=8,uint8_t flags=0) {
    allocFault=normalizeFault=loadFault=metadataFault=readFault=releaseFault=missing=zero=false;
    reads=releases=loads=0; std::memset(handlerData,0,sizeof handlerData);
    handlerVt[0]=(uintptr_t)&Release; workerVt[5]=(uintptr_t)&Read;
    *(uintptr_t*)handlerData=(uintptr_t)handlerVt; *(uintptr_t*)workerData=(uintptr_t)workerVt;
    *(uintptr_t*)(handlerData+0x20)=(uintptr_t)workerData;
    *(uint32_t*)(handlerData+0x34)=stored; *(uint32_t*)(handlerData+0x38)=decoded; *(uint8_t*)(handlerData+0x3c)=flags;
}
ReadResult Actual() { const std::string path="object/bin__/00_common/system/cd_testfield_grid_box_1m.prefab"; ResourceProbeBackend b{path}; return ReadBounded(b); }
LONG CALLBACK GuardHandler(EXCEPTION_POINTERS* ep) { if(cdk::t_guardTop) cdk::GuardDispatch(ep); return EXCEPTION_CONTINUE_SEARCH; }
struct Pump {
    uint64_t clock=10; bool ready=true; int reads=0; std::deque<std::function<void()>> queue;
    std::function<ReadResult()> action=[](){ ReadResult r; r.state=State::Read; r.bytes={1,2,3}; r.storedSize=r.decodedSize=3; r.handlerPresent=r.handlerReleased=true; return r; };
    Hooks hooks() { return {[this](){return ready;},[this](){return clock;},[this](std::function<void()> f){queue.push_back(std::move(f));},[this](const std::string& path){assert(path==ResourcePath("oak_y_prefab")); ++reads; return action();}}; }
    void tick() { assert(!queue.empty()); auto f=std::move(queue.front()); queue.pop_front(); f(); }
};
int main() {
    AddVectoredExceptionHandler(1,GuardHandler);
    std::set<std::string> paths;
    for(const char* prefix:{"blue","oak_x","oak_y","oak_z"}) for(const char* suffix:{"prefab","meshinfo","pam","pamlod","pami","hkx"}) {
        auto p=ResourcePath(std::string(prefix)+"_"+suffix); assert(!p.empty() && p[0]!='/' && paths.insert(p).second);
        if(std::string(suffix)=="prefab" || std::string(suffix)=="meshinfo") assert(p.rfind("object/bin__/",0)==0);
    }
    for(const char* s:{"oak_atlas","oak_atlas_n","oak_atlas_sp"}) assert(paths.insert(ResourcePath(s)).second);
    assert(paths.size()==27 && ResourcePath("/object/x.prefab").empty() && ResourcePath("oak_y_../prefab").empty()); Pass("27 fixed physical paths");
    std::string resource;
    assert(ParseBody(" { \"resource\" : \"oak_y_prefab\" } \n",resource) && resource=="oak_y_prefab");
    for(const char* s:{"{}","{\"resource\":1}","{\"resource\":true}","{\"resource\":null}","{\"resource\":[]}","{\"path\":\"x\"}","{\"resource\":\"x\",\"path\":\"x\"}","{\"resource\":\"x\",\"resource\":\"y\"}","{\"resource\":\"oak_y_prefab\"} trailing","{\"resource\":\"oak\\u005fy_prefab\"}","{\"resource\":\"\"}"}) assert(!ParseBody(s,resource));
    assert(!ParseBody(std::string(129,' '),resource)); Pass("strict one-string body");
    int ticket; assert(ParseTicket("1",ticket)&&ticket==1); assert(ParseTicket("2147483646",ticket));
    for(const char* s:{"0","-1","+1","1.0","1e1"," 1","1 ","NaN","2147483647","9999999999999","1&ticket=2"}) { assert(!ParseTicket(s,ticket)); }
    Pass("decimal tickets bounded and exact");
    assert(Fnv1a64({})==UINT64_C(0xcbf29ce484222325)); assert(Fnv1a64({'h','e','l','l','o'})==UINT64_C(0xa430d84680aabd0b)); Pass("canonical FNV1a64 vectors");
    Reset(); auto r=Actual(); assert(r.state==State::Read && r.bytes.size()==8 && r.handlerPresent&&r.handlerReleased&&reads==1&&releases==1); Pass("exact native backend read ABI and release");
    Reset(); missing=true; r=Actual(); assert(r.state==State::NotFound && !r.handlerPresent && releases==0 && reads==0); Pass("not-found has no handler to release");
    Reset(); allocFault=true; r=Actual(); assert(r.state==State::ReadFailed && !r.handlerPresent && releases==0);
    Reset(); normalizeFault=true; r=Actual(); assert(r.state==State::ReadFailed && !r.handlerPresent && releases==0); Pass("allocator and normalizer faults caught");
    Reset(); loadFault=true; r=Actual(); assert(r.state==State::ReadFailed && r.handlerReleased && releases==1 && reads==0); Pass("captured handler released after loader fault");
    Reset(); *(uintptr_t*)(handlerData+0x20)=0; r=Actual(); assert(r.state==State::ReadFailed && r.handlerReleased && releases==1 && reads==0); Pass("missing worker released");
    Reset(); readFault=true; r=Actual(); assert(r.state==State::ReadFailed && r.handlerReleased && releases==1 && reads==1 && r.bytes.empty()); Pass("worker fault releases outside native guard");
    Reset(); releaseFault=true; r=Actual(); assert(r.state==State::ReadFailed && r.handlerPresent && !r.handlerReleased && releases==1 && r.bytes.empty()); Pass("release fault not retried");
    for(uint8_t f:{uint8_t(0),uint8_t(1),uint8_t(0x32)}) {
        Reset(MAX_BYTES+1,8,f); r=Actual(); assert(r.state==State::TooLarge && r.handlerReleased && !reads && r.bytes.empty());
        Reset(8,MAX_BYTES+1,f); r=Actual(); assert(r.state==State::TooLarge && r.handlerReleased && !reads && r.bytes.empty());
    } Pass("both native sizes checked before worker and allocation");
    Reset(MAX_BYTES,MAX_BYTES); r=Actual(); assert(r.state==State::Read&&r.bytes.size()==MAX_BYTES&&reads==1&&releases==1);
    Reset(8,16,1); r=Actual(); assert(r.state==State::Read&&r.bytes.size()==8);
    Reset(8,16,0x32); r=Actual(); assert(r.state==State::Read&&r.bytes.size()==16); Pass("exact boundary and partial/full returned lengths");
    Reset(0,0); r=Actual(); assert(r.state==State::ReadFailed && r.handlerReleased && !reads);
    Reset(); zero=true; r=Actual(); assert(r.state==State::EmptyBuffer && r.handlerReleased && r.bytes.empty()); Pass("zero-length and empty-buffer outcomes");
    // Metadata deliberately faults on an unreadable handler after load. Its
    // release also faults, but is still attempted once and never re-entered.
    Reset(); auto saved=g_origResLoad;
    g_origResLoad=+[](void*,void** out,void*,uint32_t)->void*{*out=(void*)1;return *out;};
    r=Actual(); assert(r.state==State::ReadFailed&&r.handlerPresent&&!r.handlerReleased&&r.bytes.empty()); g_origResLoad=saved; Pass("metadata and release faults survived without RAII guard objects");
    { Pump p; Service s(p.hooks()); Snapshot a,b; assert(s.Submit("oak_y_prefab",a)==Admission::Accepted && a.attempts==0 && p.reads==0 && p.queue.size()==1);
      assert(s.Lookup(a.ticket,b)&&b.state==State::Pending&&p.reads==0); p.tick(); assert(s.Lookup(a.ticket,b)&&b.state==State::Read&&b.attempts==1&&b.head16hex=="010203"&&b.fnv1a64=="d0aa6218672cf5ab");
      assert(s.Lookup(a.ticket,b)&&p.reads==1&&p.queue.empty()); Pass("POST enqueues; GET snapshots without reading"); }
    { Pump p; Service s(p.hooks()); Snapshot a,b; p.ready=false; assert(s.Submit("oak_y_prefab",a)==Admission::Unavailable&&p.queue.empty()); p.ready=true;
      assert(s.Submit("anything",a)==Admission::UnknownResource); assert(s.Submit("oak_y_prefab",a)==Admission::Accepted); p.ready=false; p.tick(); assert(s.Lookup(a.ticket,b)&&b.state==State::Unavailable&&p.reads==0); Pass("readiness checked at admission and game tick"); }
    { Pump p; p.action=[](){ReadResult r;r.state=State::EmptyBuffer;return r;}; Service s(p.hooks()); Snapshot a,b; s.Submit("oak_y_prefab",a);
      for(int n=1;n<=3;++n){p.tick();assert(s.Lookup(a.ticket,b)&&b.attempts==(unsigned)n&&p.reads==n);assert(b.state==(n<3?State::Pending:State::EmptyBuffer));assert(p.queue.size()==(n<3?1u:0u));}
      assert(s.Lookup(a.ticket,b)&&p.reads==3); Pass("empty-buffer retry exactly one per queued tick, maximum three"); }
    { Pump p; Service s(p.hooks()); Snapshot a,b; s.Submit("oak_y_prefab",a);p.clock+=TTL_MS;assert(s.Lookup(a.ticket,b)&&b.state==State::Expired&&b.attempts==0);p.tick();assert(!p.reads&&p.queue.empty());Pass("TTL expiry before execution prevents native read"); }
    { Pump p; Service s(p.hooks()); Snapshot a,b;p.action=[&p](){p.clock+=TTL_MS;ReadResult r;r.state=State::EmptyBuffer;return r;};s.Submit("oak_y_prefab",a);p.tick();assert(s.Lookup(a.ticket,b)&&b.state==State::Expired&&p.reads==1&&p.queue.empty());Pass("TTL crossed during read suppresses retries"); }
    { Pump p; Service s(p.hooks()); Snapshot a,b;for(unsigned n=0;n<MAX_TICKETS;++n)assert(s.Submit("oak_y_prefab",a)==Admission::Accepted);assert(p.queue.size()==MAX_TICKETS);
      for(int n=0;n<4;++n){p.clock+=TTL_MS;assert(s.Submit("oak_y_prefab",b)==Admission::Busy&&p.queue.size()==MAX_TICKETS);}while(!p.queue.empty())p.tick();assert(!p.reads);assert(s.Submit("oak_y_prefab",b)==Admission::Accepted);Pass("paused pump cannot grow queue by TTL reuse"); }
    { Pump p; Service s(p.hooks()); Snapshot a,b;int first=0;for(int n=0;n<27;++n){assert(s.Submit("oak_y_prefab",a)==Admission::Accepted);if(!n)first=a.ticket;p.tick();assert(s.Lookup(a.ticket,b)&&b.state==State::Read);}
      assert(p.reads==27&&p.queue.empty()&&!s.Lookup(first,b));Pass("completed receipts evicted for sequential all27"); }
    std::cout << checks << " isolated checks passed" << std::endl;
}
'''


def run(args, cwd=ROOT):
    result = subprocess.run([str(arg) for arg in args], cwd=cwd, capture_output=True, text=True, errors="replace")
    if result.returncode:
        raise RuntimeError(f"Command failed: {args[0]}\n{result.stdout}\n{result.stderr}")
    return result.stdout


def function(source, marker):
    start = source.index(marker)
    brace = source.index("{", start)
    # These named routines contain no braces in strings; exact text preserves
    # all old conditions, native ABIs and fault branches for regression proof.
    level = 1
    end = brace + 1
    while level:
        level += (source[end] == "{") - (source[end] == "}")
        end += 1
    return source[start:end]


def main():
    expected = "4dcedc8dfe1592fdee0528894389221291900b8d"
    assert run(["git", "rev-parse", "HEAD"], VENDOR).strip() == expected
    source = (SRC / "cdmodkit.cpp").read_text(encoding="utf-8")
    baseline = run(["git", "show", "HEAD:asi/cdmodkit/cdmodkit.cpp"], VENDOR)
    for marker in ("static bool GameReadFileGuarded(", "bool GameReadAvailable()", "bool GameReadFile(const", "bool GameReadFileRange(const std::string& path, std::vector<uint8_t>& out, uint32_t offset, uint32_t length, uint32_t* storedTotal, bool* notFound) {"):
        assert function(source, marker) == function(baseline, marker), marker
    print("PASS legacy GameReadFile/Range functions byte-identical to pinned upstream", flush=True)
    for name in ("mc_resource_probe.h", "mc_resource_probe.cpp"):
        assert (SRC / name).read_bytes() == (PATCHES / name).read_bytes(), f"Prepared source differs: {name}"
    run(["git", "apply", "--reverse", "--check", PATCHES / "upstream.patch"], VENDOR)
    http = (SRC / "http_api.cpp").read_text(encoding="utf-8")
    assert http.index("mc_resource_probe::ParseBody(body, resource)") < http.index("if (length && !JsonObject(body, fields))")
    assert "GetCurrentThreadId() != g_gameThread" in source
    print("PASS prepared source/patch and raw-body/game-thread boundaries", flush=True)
    adapter = source[source.index("struct ResourceProbeBackend {"):source.index("mc_resource_probe::ReadResult ReadResourceBounded(")]
    build = ROOT / "build/native-resource-host"
    build.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="isolated-", dir=build) as temp:
        folder = Path(temp)
        harness = folder / "harness.cpp"
        harness.write_text(HARNESS.replace("__ADAPTER__", adapter), encoding="utf-8")
        output = folder / "check.exe"
        run([COMPILER, "-std=c++17", "-O1", "-Wall", "-Wextra", "-Werror", "-static", "-I" + str(PATCHES), "-I" + str(SRC), harness, PATCHES / "mc_resource_probe.cpp", "-o", output])
        print(run([output]), end="")


if __name__ == "__main__":
    main()
