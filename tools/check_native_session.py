"""Compile the exact native HTTP parser/session gate in an isolated host.

Memory sockets and a counting dispatcher prove rejected requests cannot reach
native object mutations. No listener, game process, Minecraft or scene is used.
"""
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
VENDOR = ROOT / "vendor/world-builder"
SOURCE = VENDOR / "asi/cdmodkit/http_api.cpp"
PATCH = ROOT / "red-side-patches/upstream.patch"
COMPILER = Path("C:/msys64/ucrt64/bin/g++.exe")

HARNESS = r'''
#define WIN32_LEAN_AND_MEAN
#include <winsock2.h>
#include <windows.h>
#include <algorithm>
#include <cassert>
#include <cctype>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <iostream>
#include <map>
#include <string>
#include "mc_resource_probe.h"
using Fields = std::map<std::string, std::string>;
static DWORD fixturePid = 4321;
static uint64_t fixtureCreation = UINT64_C(134357748895555000);
static bool identityAvailable = true;
static int identityReads = 0;
static DWORD FixturePid() { return fixturePid; }
static BOOL FixtureTimes(HANDLE, LPFILETIME created, LPFILETIME, LPFILETIME, LPFILETIME) {
    ++identityReads;
    created->dwLowDateTime = DWORD(fixtureCreation);
    created->dwHighDateTime = DWORD(fixtureCreation >> 32);
    return identityAvailable;
}
#define GetCurrentProcessId FixturePid
#define GetProcessTimes FixtureTimes
__PRODUCTION_HELPERS__
#undef GetCurrentProcessId
#undef GetProcessTimes
namespace core {
static bool HooksReady() { return true; }
static bool GameThreadReady() { return true; }
static bool BuildOk() { return true; }
static const char* GameVersion() { return "1.0.0.2976"; }
static const char* BuildMessage() { return "isolated native fixture"; }
static int PendingSpawns() { return 0; }
}
static int dispatches = 0, enqueues = 0, responseStatus = 0;
static std::string responseBody, wire;
static size_t wirePosition = 0, chunkSize = 4096;
static int SocketOption(SOCKET, int, int, const char*, int) { return 0; }
static int Receive(SOCKET, char* output, int maximum, int) {
    const size_t n = (std::min)({size_t(maximum), chunkSize, wire.size() - wirePosition});
    std::memcpy(output, wire.data() + wirePosition, n); wirePosition += n; return int(n);
}
static void Reply(SOCKET, int status, const std::string& body) { responseStatus = status; responseBody = body; }
static std::string Handle(const std::string& method, const std::string& path, const Fields&, int& status) {
    ++dispatches; status = 200;
    __PRODUCTION_STATUS__
    if (SessionObjectWrite(method, path)) { ++enqueues; status = 202; }
    return "{\"fixtureDispatched\":true}";
}
#define setsockopt SocketOption
#define recv Receive
__PRODUCTION_CLIENT__
#undef setsockopt
#undef recv
static void Request(const std::string& method, const std::string& path, const std::string& headers = "", bool snapshot = true) {
    std::string body = method == "POST" ? "{}" : "";
    if (snapshot && !headers.empty() && SessionObjectWrite(method, path) && path != "/api/objects")
        body = "{\"expectedProject\":\"\",\"expectedPrefab\":\"blue\",\"expectedX\":0,\"expectedY\":0,\"expectedZ\":0,\"expectedYaw\":0,\"expectedPitch\":0,\"expectedRoll\":0,\"expectedScale\":1,\"expectedHidden\":false}";
    wire = method + " " + path + " HTTP/1.1\r\nHost: 127.0.0.1:8765\r\n" + headers +
        "Content-Length: " + std::to_string(body.size()) + "\r\n\r\n" + body;
    wirePosition = 0; dispatches = enqueues = responseStatus = 0; responseBody.clear(); Client(1, 8765);
}
static void Rejected(const std::string& method, const std::string& path, const std::string& headers) {
    Request(method, path, headers);
    assert(responseStatus == 409 && dispatches == 0 && enqueues == 0);
    assert(responseBody == "{\"error\":\"Game process session mismatch\",\"sessionMismatch\":true,\"instanceId\":" + Quote(InstanceId()) + "}");
}
static int checks = 0;
static void Pass(const char* name) { ++checks; std::cout << "PASS " << name << std::endl; }
int main(int argc, char** argv) {
    if (argc == 2) {
        if (std::string(argv[1]) == "--identity-unavailable") identityAvailable = false;
        else if (std::string(argv[1]) == "--zero-creation") fixtureCreation = 0;
        else return 2;
        assert(InstanceId().empty());
        Request("GET", "/api/status");
        assert(responseStatus == 200 && responseBody.find("\"instanceId\":\"\"") != std::string::npos &&
               responseBody.find("\"sessionPreconditions\":false") != std::string::npos);
        for (auto route : {std::pair{"POST", "/api/objects"}, {"POST", "/api/objects/1/project"}, {"DELETE", "/api/objects/1"}}) {
            Rejected(route.first, route.second, "X-CrimsonMC-Session:\r\n");
            Rejected(route.first, route.second, "X-CrimsonMC-Session: 4321:134357748895555000\r\n");
        }
        Pass("missing self identity disables capability and rejects supplied preconditions");
        return 0;
    }
    const std::string token = "4321:134357748895555000";
    assert(InstanceId() == token && InstanceId() == token && identityReads == 1);
    Pass("fixed token contains full-width creation FILETIME and PID");
    Request("GET", "/api/status");
    assert(responseStatus == 200 && responseBody.find("\"instanceId\":" + Quote(token)) != std::string::npos &&
           responseBody.find("\"sessionPreconditions\":true") != std::string::npos &&
           responseBody.find("\"objectPreconditions\":true") != std::string::npos && enqueues == 0);
    Pass("exact production status advertises the current token and capability");
    for (auto route : {std::pair{"POST", "/api/objects"}, {"POST", "/api/objects/1/project"}, {"DELETE", "/api/objects/1"}}) {
        Rejected(route.first, route.second, "X-CrimsonMC-Session: 4322:134357748895555000\r\n");
        Rejected(route.first, route.second, "X-CrimsonMC-Session: 4321:134357748895555001\r\n");
        Rejected(route.first, route.second, "X-CrimsonMC-Session:\r\n");
        Rejected(route.first, route.second, "X-CrimsonMC-Session: \t \r\n");
        Request(route.first, route.second, "X-CrimsonMC-Session: " + token + "\r\n");
        assert(responseStatus == 202 && dispatches == 1 && enqueues == 1);
        Request(route.first, route.second);
        assert(responseStatus == 202 && dispatches == 1 && enqueues == 1);
    }
    Pass("all three write routes reject other PID, reused PID, empty and whitespace tokens before dispatch");
    Pass("all three write routes admit matching tokens once and retain old-client compatibility");
    for (auto route : {std::pair{"POST", "/api/objects/1/project"}, {"DELETE", "/api/objects/1"}}) {
        Request(route.first, route.second, "X-CrimsonMC-Session: " + token + "\r\n", false);
        assert(responseStatus == 400 && dispatches == 0 && enqueues == 0);
    }
    Pass("session-bound project and delete require a complete object snapshot before dispatch");
    Request("POST", "/api/objects/1/project", "x-CrImSoNmC-sEsSiOn: \t" + token + " \t\r\n");
    assert(responseStatus == 202 && enqueues == 1);
    Pass("header casing and HTTP optional whitespace are handled");
    Request("DELETE", "/api/objects/1", "X-CrimsonMC-Session: " + token + "\r\nx-crimsonmc-session: " + token + "\r\n");
    assert(responseStatus == 400 && dispatches == 0 && enqueues == 0);
    Pass("duplicate preconditions cannot bypass the gate");
    Rejected("DELETE", "/api/objects/1?anything=1", "X-CrimsonMC-Session: stale\r\n");
    Rejected("POST", "/api/objects/+1/project", "X-CrimsonMC-Session: stale\r\n");
    Rejected("DELETE", "/api/objects/1/", "X-CrimsonMC-Session: stale\r\n");
    Pass("query suffixes and legacy UID spellings cannot evade protected route classification");
    chunkSize = 3;
    Rejected("POST", "/api/objects", "X-CrimsonMC-Session: stale\r\n");
    Request("POST", "/api/objects", "X-CrimsonMC-Session: " + token + "\r\n");
    assert(responseStatus == 202 && enqueues == 1);
    chunkSize = 4096;
    Pass("fragmented request headers preserve the session gate");
    for (const char* path : {"/api/status", "/api/objects", "/api/objects/1"}) {
        Request("GET", path, "X-CrimsonMC-Session: stale\r\n");
        assert(responseStatus == 200 && dispatches == 1 && enqueues == 0);
    }
    Pass("read-only object and status routes retain compatibility");
    std::cout << checks << " isolated session checks passed" << std::endl;
}
'''


def run(args, cwd=ROOT):
    result = subprocess.run([str(arg) for arg in args], cwd=cwd, capture_output=True,
                            text=True, encoding="utf-8", errors="replace", timeout=180)
    if result.returncode:
        raise RuntimeError(f"Command failed: {args[0]}\n{result.stdout}\n{result.stderr}")
    return result.stdout


def main():
    assert run(["git", "rev-parse", "HEAD"], VENDOR).strip() == "4dcedc8dfe1592fdee0528894389221291900b8d"
    run(["git", "apply", "--reverse", "--check", PATCH], VENDOR)
    source = SOURCE.read_text(encoding="utf-8")
    helpers = source[source.index("static std::string Quote("):source.index("static std::string ObjectJson(")]
    client = source[source.index("static void Client("):source.index("// The listener is owned")]
    status = source[source.index('if (method == "GET" && path == "/api/status")'):source.index('if (method == "GET" && path == "/api/player")')]
    assert client.index("CheckSession(") < client.index("Handle(method, path, fields, status)")
    folder = ROOT / "build/native-session-host"
    folder.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="isolated-", dir=folder) as temporary:
        stage = Path(temporary)
        rebuilt = stage / "source-rebuild"
        for name in ("cdmodkit.cpp", "core.h", "core_internal.h", "editor.cpp", "http_api.cpp", "overlay.cpp"):
            relative = "asi/cdmodkit/" + name
            baseline = run(["git", "show", "HEAD:" + relative], VENDOR)
            target = rebuilt / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(baseline, encoding="utf-8", newline="\n")
        run(["git", "init", "--quiet"], rebuilt)
        run(["git", "apply", "--check", PATCH], rebuilt)
        run(["git", "apply", PATCH], rebuilt)
        for name in ("cdmodkit.cpp", "core.h", "core_internal.h", "editor.cpp", "http_api.cpp", "overlay.cpp"):
            relative = "asi/cdmodkit/" + name
            assert (rebuilt / relative).read_text(encoding="utf-8") == (VENDOR / relative).read_text(encoding="utf-8"), name
        print("PASS all six patched native sources reconstruct from the pinned commit", flush=True)
        harness = stage / "harness.cpp"
        harness.write_text(HARNESS.replace("__PRODUCTION_HELPERS__", helpers)
                           .replace("__PRODUCTION_CLIENT__", client).replace("__PRODUCTION_STATUS__", status), encoding="utf-8")
        executable = stage / "check.exe"
        patches = ROOT / "red-side-patches"
        run([COMPILER, "-std=c++17", "-O1", "-Wall", "-Wextra", "-Werror", "-Wno-unused-function", "-static",
             "-I" + str(patches), harness, patches / "mc_resource_probe.cpp", "-o", executable])
        print(run([executable]), end="")
        print(run([executable, "--identity-unavailable"]), end="")
        print(run([executable, "--zero-creation"]), end="")


if __name__ == "__main__":
    main()
