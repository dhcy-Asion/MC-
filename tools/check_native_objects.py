"""Compile the production conditional registry mutation and HTTP adapter offline.

Actual core types, lock scopes, comparisons and dispatch are compiled unchanged;
the registry, game queue and physical removal are isolated fixture boundaries.
No listener, running game, saved project or Minecraft state is touched.
"""
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "vendor/world-builder/asi/cdmodkit"
COMPILER = Path("C:/msys64/ucrt64/bin/g++.exe")

HARNESS = r'''
#include "core.h"
#include <algorithm>
#include <atomic>
#include <cassert>
#include <chrono>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <iostream>
#include <map>
#include <set>
#include <thread>
using Fields = std::map<std::string, std::string>;
namespace core {
static std::mutex g_projMutex, g_groundOpMutex, g_regMutex;
static std::vector<std::string> g_projNames;
static std::vector<SpawnedObj> g_reg;
static std::set<int> g_projDirty;
__GROUND_TYPE__
static unsigned g_groundWorldWriting = 0;
static std::map<int, GroundHandle> g_groundLeases;
static std::map<int, int> g_groundMutationPending;
static std::vector<std::weak_ptr<GroundOp>> g_groundOps;
static uint64_t g_nextGen = 40;
static int forgotten = 0, nativeWork = 0;
static bool ready = true;
static std::vector<std::function<void()>> queue;
static std::vector<uintptr_t> removed;
static thread_local int registryDepth = 0;
struct LockNote { LockNote() { ++registryDepth; } ~LockNote() { --registryDepth; } };
#define REG_LOCK std::lock_guard<std::mutex> l(g_regMutex); LockNote note_
bool GameThreadReady() { return ready; }
bool HooksReady() { return ready; }
static int IndexOfUidLocked(int uid) { for (size_t i=0;i<g_reg.size();++i) if(g_reg[i].uid==uid) return int(i); return -1; }
static uint64_t NewGenLocked() { return g_nextGen++; }
static void MarkDirtyLocked(int project) { if(project>0) g_projDirty.insert(project); }
static void ForgetCopyValueLocked(int) { ++forgotten; }
static void AssertOutsideLocks() {
    assert(registryDepth == 0);
    bool unlocked = false;
    std::thread check([&]() {
        std::unique_lock<std::mutex> a(g_projMutex,std::try_to_lock), b(g_groundOpMutex,std::try_to_lock), c(g_regMutex,std::try_to_lock);
        unlocked=a.owns_lock() && b.owns_lock() && c.owns_lock();
    }); check.join(); assert(unlocked);
}
static std::shared_ptr<void> TrackProjectNativeWork(int) { AssertOutsideLocks(); ++nativeWork; return {}; }
void RunOnGameThread(std::function<void()> fn) { AssertOutsideLocks(); queue.push_back(std::move(fn)); }
static bool DoRemove(uintptr_t object) { AssertOutsideLocks(); removed.push_back(object); return true; }
__GROUND_TOUCHES__
__PRODUCTION_CORE__
}
__PRODUCTION_HELPERS__
__PRODUCTION_READY__
__PRODUCTION_HTTP__
static const char* blue = "/object/00_common/system/cd_testfield_grid_box_1m.prefab";
static int checks = 0;
static void Pass(const char* name) { ++checks; std::cout << "PASS " << name << std::endl; }
static void Reset() {
    using namespace core;
    g_projNames={"", "CrimsonMC", "Foreign"}; g_reg.clear(); g_projDirty.clear(); g_nextGen=40;
    g_groundWorldWriting=0; g_groundLeases.clear(); g_groundMutationPending.clear(); g_groundOps.clear();
    forgotten=nativeWork=0; ready=true; queue.clear(); removed.clear();
    SpawnedObj e{}; e.uid=11; e.prefab=blue; e.proj=1; e.obj=1234; e.scale=1; e.gen=39;
    e.pos={1.23456789f,-234.56789f,9876.543f}; e.rot={13.3f,-17.7f,89.125f};
    e.colRot=e.rot; e.colScale=e.scale; g_reg.push_back(e);
}
static Fields Snapshot() {
    const auto& e=core::g_reg.front();
    return {{"expectedProject",core::g_projNames[e.proj]},{"expectedPrefab",e.prefab},
        {"expectedX",Num(e.pos.x)},{"expectedY",Num(e.pos.y)},{"expectedZ",Num(e.pos.z)},
        {"expectedYaw",Num(e.rot.yaw)},{"expectedPitch",Num(e.rot.pitch)},{"expectedRoll",Num(e.rot.roll)},
        {"expectedScale",Num(e.scale)},{"expectedHidden",Bool(e.hidden)},{"name","Assigned"}};
}
static std::string Request(const Fields& fields, bool assign, int expectedStatus) {
    int status=200; std::string output;
    assert(ConditionalObjectRequest(11,assign?"POST":"DELETE",assign?"project":"",fields,status,output));
    assert(status==expectedStatus);
    return output;
}
static void Unchanged(const std::string& output, const char* reason) {
    using namespace core;
    assert(output.find("\"mutationApplied\":false")!=std::string::npos);
    assert(output.find(std::string("\"reason\":\"")+reason+"\"")!=std::string::npos);
    assert(output.find(std::string("\"objectMismatch\":")+(std::string(reason)=="object_changed"?"true":"false"))!=std::string::npos);
    assert(g_projNames.size()==3 && g_projDirty.empty() && g_nextGen==40 && forgotten==0 && queue.empty() && removed.empty() && nativeWork==0);
}
int main() {
    using namespace core;
    Reset(); auto expected=Snapshot();
    assert(Request(expected,true,200).find("\"conditional\":true")!=std::string::npos);
    assert(g_reg[0].proj==3 && g_projNames.back()=="Assigned" && g_projDirty==std::set<int>({1,3}) && queue.empty());
    Pass("exact nine-digit float snapshot atomically assigns project and marks both projects dirty");
    for(bool assign:{false,true}) for(int field=0;field<10;++field) {
        Reset(); expected=Snapshot(); auto& e=g_reg[0];
        float* values[]={&e.pos.x,&e.pos.y,&e.pos.z,&e.rot.yaw,&e.rot.pitch,&e.rot.roll,&e.scale};
        if(field<7) *values[field]=std::nextafter(*values[field],INFINITY);
        else if(field==7) e.proj=2; else if(field==8) e.prefab="/foreign.prefab"; else e.hidden=true;
        Unchanged(Request(expected,assign,409),"object_changed");
        assert(g_reg.size()==1 && g_reg[0].obj==1234);
    }
    Pass("all ten stale snapshot fields reject assignment and deletion without any admission side effects");
    for(bool assign:{false,true}) { Reset(); expected=Snapshot(); g_reg.clear(); Unchanged(Request(expected,assign,409),"object_changed"); }
    Pass("missing UID is a proven no-mutation snapshot conflict");
    for(bool assign:{false,true}) for(int kind=0;kind<5;++kind) {
        Reset(); expected=Snapshot(); GroundHandle active;
        if(kind==0) g_groundWorldWriting=1;
        if(kind==1) g_groundLeases[11]={};
        if(kind==2) g_groundMutationPending[11]=1;
        if(kind>=3) {
            active=std::make_shared<GroundOp>(); active->view.state=kind==3?GroundApplying:GroundProbing;
            active->view.members.push_back({}); active->view.members[0].before.uid=11; g_groundOps.push_back(active);
        }
        Unchanged(Request(expected,assign,409),"busy");
        if(active) assert(active->view.state==(kind==3?GroundApplying:GroundProbing));
    }
    Pass("world writes, ground leases, deferred reservations and unfinished ground operations reject without deferral");
    for(bool assign:{false,true}) for(int kind=0;kind<6;++kind) {
        Reset(); auto& e=g_reg[0]; std::shared_ptr<PlaceRequest> placement;
        if(kind==0) e.gimmick=true; if(kind==1) e.standin=true; if(kind==2) e.actor=876;
        if(kind==3) e.placeRow=0;
        if(kind==4) { placement=std::make_shared<PlaceRequest>(); e.placeReq=placement; }
        if(kind==5) e.prefab="/foreign.prefab";
        Unchanged(Request(Snapshot(),assign,409),"unsupported");
    }
    Pass("dynamic, stand-in, actor, placement-owned and non-blue records are outside conditional scope");
    Reset(); g_reg[0].obj=0; expected=Snapshot();
    assert(Request(expected,true,200).find("\"conditional\":true")!=std::string::npos && g_reg[0].proj==3 && queue.empty());
    Reset(); g_reg[0].obj=0; Unchanged(Request(Snapshot(),false,409),"busy");
    Pass("pending ordinary spawn can be assigned but visible unmaterialized deletion waits");
    Reset(); g_reg[0].poseGen=1; Unchanged(Request(Snapshot(),false,409),"unsupported");
    assert(Request(Snapshot(),true,200).find("\"conditional\":true")!=std::string::npos);
    Pass("legacy move history refuses physical deletion but still permits an exact project assignment");
    Reset(); expected=Snapshot(); auto uid=g_reg[0].uid; auto gen=g_reg[0].gen;
    assert(Request(expected,false,202).find("\"conditional\":true")!=std::string::npos);
    assert(g_reg.empty() && g_nextGen==41 && forgotten==1 && g_projDirty.count(1) && queue.size()==1 && removed.empty() && nativeWork==1);
    assert(IndexOfUidLocked(uid)<0); // the production UID/generation attachment predicate cannot match
    SpawnedObj other{}; other.uid=12; other.obj=5678; other.gen=gen; g_reg.push_back(other);
    auto job=queue.front(); queue.clear(); job(); assert(removed==std::vector<uintptr_t>({1234}) && g_reg[0].obj==5678);
    Pass("delete atomically invalidates and forgets then removes only the captured physical object outside all locks");
    Reset(); g_reg[0].hidden=true; g_reg[0].obj=0;
    Request(Snapshot(),false,202); assert(g_reg.empty() && queue.empty() && forgotten==1);
    Reset(); g_reg[0].hidden=true; Unchanged(Request(Snapshot(),false,409),"unsupported");
    Pass("hidden no-handle cleanup is synchronous and inconsistent hidden handles are refused");
    for(bool assign:{false,true}) for(const char* key:kObjectExpectedKeys) {
        Reset(); expected=Snapshot(); expected.erase(key); Request(expected,assign,400);
        assert(g_reg[0].proj==1 && g_projNames.size()==3 && g_projDirty.empty() && queue.empty());
    }
    Reset(); expected=Snapshot(); for(auto& p:expected) if(p.first.rfind("expected",0)==0) p.second="";
    Request(expected,true,400); Request(expected,false,400);
    for(const char* key:{"expectedX","expectedY","expectedZ","expectedYaw","expectedPitch","expectedRoll","expectedScale"}) {
        for(const char* bad:{"nan","inf","1e99","","{}"}) { Reset(); expected=Snapshot(); expected[key]=bad; Request(expected,false,400); assert(queue.empty() && g_reg.size()==1); }
    }
    Reset(); expected=Snapshot(); expected["expectedHidden"]="1"; Request(expected,false,400);
    expected=Snapshot(); expected["expectedUnknown"]="true"; Request(expected,true,400);
    Pass("missing, empty, nonfinite and unknown conditions reject before mutation with no legacy fallback");
    Reset(); int status=200; std::string out;
    assert(!ConditionalObjectRequest(11,"POST","project",{{"name","Legacy"}},status,out));
    assert(!ConditionalObjectRequest(11,"DELETE","",{},status,out));
    assert(ConditionalObjectRequest(11,"POST","hide",Snapshot(),status,out) && status==400);
    Pass("no-condition requests retain legacy routing and conditions cannot silently target a different action");
    for(bool assign:{false,true}) for(int change=0;change<3;++change) {
        Reset(); expected=Snapshot();
        std::unique_lock<std::mutex> held(g_regMutex); std::string result; int code=0;
        std::thread contender([&]() { result=Request(expected,assign,409); code=409; });
        const auto end=std::chrono::steady_clock::now()+std::chrono::seconds(3);
        bool waiting=false;
        while(std::chrono::steady_clock::now()<end) {
            if(!g_groundOpMutex.try_lock()) { waiting=true; break; }
            g_groundOpMutex.unlock(); std::this_thread::yield();
        }
        assert(waiting); // contender has the operation lock and must wait for this registry lock
        if(change==0) g_reg[0].proj=2;
        if(change==1) g_reg[0].pos.x=std::nextafter(g_reg[0].pos.x,INFINITY);
        if(change==2) g_reg[0].hidden=true;
        held.unlock(); contender.join(); assert(code==409);
        Unchanged(result,"object_changed");
        assert((change!=0 || g_reg[0].proj==2) && (change!=2 || g_reg[0].hidden));
    }
    Pass("real concurrent reassign, move and hide cannot cross the atomic compare and write");
    std::cout << checks << " isolated atomic object checks passed" << std::endl;
}
'''


def run(args):
    result = subprocess.run([str(x) for x in args], cwd=ROOT, capture_output=True,
                            text=True, encoding="utf-8", errors="replace", timeout=180)
    if result.returncode:
        raise RuntimeError(f"Command failed: {args[0]}\n{result.stdout}\n{result.stderr}")
    return result.stdout


def section(source, start, end):
    return source[source.index(start):source.index(end, source.index(start))]


def main():
    core = (SRC / "cdmodkit.cpp").read_text(encoding="utf-8")
    http = (SRC / "http_api.cpp").read_text(encoding="utf-8")
    replacements = {
        "__GROUND_TYPE__": section(core, "struct GroundOp {", "static std::mutex g_groundOpMutex"),
        "__GROUND_TOUCHES__": section(core, "static bool GroundTouches(", "// Caller keeps the operation mutex"),
        "__PRODUCTION_CORE__": section(core, "// CrimsonMC atomic object preconditions.", "// End CrimsonMC atomic object preconditions."),
        "__PRODUCTION_HELPERS__": section(http, "static std::string Quote(", "static std::string ObjectJson("),
        "__PRODUCTION_READY__": section(http, "static bool Ready(", "// CrimsonMC conditional object request:"),
        "__PRODUCTION_HTTP__": section(http, "// CrimsonMC conditional object request:", "// End CrimsonMC conditional object request."),
    }
    route = section(http, 'if (path.rfind("/api/objects/", 0) == 0)', 'if (method == "POST" && path == "/api/groups")')
    assert route.index("ConditionalObjectRequest(") < route.index("core::IndexOfUid(")
    assert '"objectPreconditions\\\":true' in http
    code = HARNESS
    for key, value in replacements.items():
        code = code.replace(key, value)
    folder = ROOT / "build/native-object-host"
    folder.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="isolated-", dir=folder) as temporary:
        stage = Path(temporary)
        harness = stage / "harness.cpp"
        harness.write_text(code, encoding="utf-8")
        executable = stage / "check.exe"
        run([COMPILER, "-std=c++17", "-O1", "-Wall", "-Wextra", "-Werror", "-Wno-unused-function", "-Wno-misleading-indentation", "-static",
             "-I" + str(SRC), harness, "-o", executable])
        print(run([executable]), end="")


if __name__ == "__main__":
    main()
