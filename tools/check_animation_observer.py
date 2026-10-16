"""Compile the real PAA forwarding observer with fake memory; no game or network."""

from pathlib import Path
import subprocess
import tempfile


ROOT = Path(__file__).resolve().parents[1]
COMPILER = Path("C:/msys64/ucrt64/bin/g++.exe")

HARNESS = r'''
#include "mc_animation_observer.h"
#include <cassert>
#include <iostream>

using mc_motion_observer::Observer;
using mc_motion_observer::Snapshot;
using mc_motion_observer::State;
static int checks = 0;
static void Pass(const char* name) { ++checks; std::cout << "PASS " << name << '\n'; }

struct ReaderError {};
struct NativeError {};

struct Memory {
    static constexpr uintptr_t OBJECT = 0x10000, HOLDER = 0x20000, CHARS = 0x30000;
    std::array<uint8_t, 8> object{}, holder{};
    std::array<uint8_t, 199> chars{};
    std::array<uintptr_t, 3> addresses{};
    std::array<std::size_t, 3> sizes{};
    unsigned calls = 0, throwAt = 0;
    std::size_t copied = 0;
    bool readable = true;

    explicit Memory(const char* text) {
        const uintptr_t h = HOLDER, c = CHARS;
        std::memcpy(object.data(), &h, sizeof h);
        std::memcpy(holder.data(), &c, sizeof c);
        assert(std::strlen(text) < chars.size());
        std::memcpy(chars.data(), text, std::strlen(text) + 1);
    }
    auto Reader() {
        return [this](uintptr_t address, void* out, std::size_t size) {
            if (calls < addresses.size()) { addresses[calls] = address; sizes[calls] = size; }
            ++calls;
            if (calls == throwAt) throw ReaderError{};
            if (!readable) return false;
            const void* source = nullptr;
            if (address == OBJECT && size == object.size()) source = object.data();
            if (address == HOLDER && size == holder.size()) source = holder.data();
            if (address == CHARS && size == chars.size()) source = chars.data();
            if (!source) return false;
            std::memcpy(out, source, size);
            copied += size;
            return true;
        };
    }
};

// The original owns its output mutation. All three pointers and all three bytes
// are checked before that mutation; the return token deliberately differs from it.
struct Call {
    uint8_t selfToken = 0, beforeToken = 0, afterToken = 0, returnToken = 0;
    void* output = &beforeToken;
    uint8_t fourth = 0x80, fifth = 0xff, sixth = 0;
    unsigned calls = 0;
    bool throws = false;
    NativeError error;

    void* Invoke(Observer& observer, Memory& memory, uint64_t now = 1,
                 uint32_t tid = 7, uint32_t callerRva = 0, bool contaminated = false) {
        auto original = [this](void* self, void** out, void* path,
                               uint8_t a, uint8_t b, uint8_t c) -> void* {
            ++calls;
            assert(self == &selfToken && out == &output);
            assert(path == reinterpret_cast<void*>(Memory::OBJECT));
            assert(a == fourth && b == fifth && c == sixth);
            assert(*out == &beforeToken);
            *out = &afterToken;
            if (throws) throw &error;
            return &returnToken;
        };
        return mc_animation_observer::Forward(observer, now, tid, callerRva, contaminated,
            original, memory.Reader(), &selfToken, &output,
            reinterpret_cast<void*>(Memory::OBJECT), fourth, fifth, sixth);
    }
    void Complete(void* result) const {
        assert(calls == 1 && result == &returnToken && output == &afterToken);
    }
};

static void Settled(const Snapshot& s) {
    assert(!s.inFlight);
    assert(s.entries == s.dropped + s.readFailures + s.invalidPaths + s.unmatched + s.matched);
    uint64_t hits = 0;
    for (const auto& path : s.paths) hits += path.count;
    assert(hits == s.matched);
    // The reused snapshot has six slots, but this observer may populate only two.
    for (std::size_t i = 2; i < s.paths.size(); ++i) assert(s.paths[i].count == 0);
}

int main() {
    static_assert(sizeof(uintptr_t) == 8);
    static_assert(sizeof(mc_animation_observer::PATHS) / sizeof(mc_animation_observer::PATHS[0]) == 2);
    {
        assert(std::strcmp(mc_animation_observer::PATHS[0],
            "character/motion/1_pc/1_phm/cd_phm_00_00_nor_move_walk_f_00.paa") == 0);
        assert(std::strcmp(mc_animation_observer::PATHS[1],
            "character/motion/1_pc/1_phm/cd_phm_basic_00_00_nor_move_walk_ing_00.paa") == 0);
        Observer observer(mc_animation_observer::PATHS); assert(observer.Start(100));
        for (std::size_t i = 0; i < 2; ++i) {
            Memory memory(mc_animation_observer::PATHS[i]);
            const auto object = memory.object, holder = memory.holder;
            const auto chars = memory.chars;
            Call call;
            call.Complete(call.Invoke(observer, memory, 110 + i, uint32_t(20 + i), uint32_t(0x100 + i)));
            assert(memory.calls == 3 && memory.copied == 215);
            assert((memory.addresses == std::array<uintptr_t, 3>{Memory::OBJECT, Memory::HOLDER, Memory::CHARS}));
            assert((memory.sizes == std::array<std::size_t, 3>{8, 8, 199}));
            assert(memory.object == object && memory.holder == holder && memory.chars == chars);
        }
        const auto s = observer.GetSnapshot(120); Settled(s);
        assert(s.entries == 2 && s.matched == 2 && !s.unmatched);
        for (std::size_t i = 0; i < 2; ++i) {
            const auto& p = s.paths[i];
            assert(p.count == 1 && p.firstMs == 10 + i && p.lastMs == p.firstMs);
            assert(p.firstFlags == 0x00ff80 && p.lastFlags == p.firstFlags);
            assert(p.firstThread == 20 + i && p.lastThread == p.firstThread);
            assert(p.firstCallerRva == 0x100 + i && p.lastCallerRva == p.firstCallerRva);
        }
        Pass("two exact PAA paths map to slots 0/1; bounded two-hop reads leave source bytes unchanged");
    }
    {
        Observer observer(mc_animation_observer::PATHS); observer.Start(0);
        const char* rejected[] = {
            "character/binary/motionblending/phm_locomotion/walk.motionblending",
            "character/binary/motionblending/phm_locomotion/basic_move_walk.motionblending",
            "character/binary/motionblending/phm_locomotion/basic_stride_walk.motionblending",
            "actionchart/bin__/loweraction/1_pc/1_phm/basic_lower.paac",
        };
        for (const auto* text : rejected) { Memory memory(text); Call call; call.Complete(call.Invoke(observer, memory)); }
        const auto s = observer.GetSnapshot(2); Settled(s);
        assert(s.entries == 4 && s.unmatched == 4 && !s.matched);
        Pass("the other four ResourceLoader paths are excluded from the PAA observer");
    }
    {
        Observer observer(mc_animation_observer::PATHS); observer.Start(0);
        const char* rejected[] = {
            "cd_phm_00_00_nor_move_walk_f_00.paa",
            "Character/motion/1_pc/1_phm/cd_phm_00_00_nor_move_walk_f_00.paa",
            "character\\motion/1_pc/1_phm/cd_phm_00_00_nor_move_walk_f_00.paa",
            "prefix/character/motion/1_pc/1_phm/cd_phm_00_00_nor_move_walk_f_00.paa",
            "character/motion/1_pc/1_phm/cd_phm_basic_00_00_nor_move_walk_ing_00.paa.extra",
            "character/motion/1_pc/1_phm/cd_phm_basic_00_00_nor_move_walk_f_ing2_00.paa",
        };
        for (const auto* text : rejected) { Memory memory(text); Call call; call.Complete(call.Invoke(observer, memory)); }
        const auto s = observer.GetSnapshot(2); Settled(s);
        assert(s.entries == 6 && s.unmatched == 6 && !s.matched);
        Pass("basename, case, slash, prefix, suffix and unapproved PAA variants do not match");
    }
    {
        struct Bytes { uint8_t a, b, c; uint32_t packed; };
        const Bytes values[] = {
            {0x80, 0xff, 0x00, 0x00ff80}, {0xff, 0x00, 0x80, 0x8000ff},
            {0x00, 0x80, 0xff, 0xff8000}, {0x01, 0x02, 0x04, 0x040201},
            {0x7f, 0xfe, 0x81, 0x81fe7f},
        };
        for (const auto& bytes : values) {
            Observer observer(mc_animation_observer::PATHS); observer.Start(0);
            Memory memory(mc_animation_observer::PATHS[0]); Call call;
            call.fourth = bytes.a; call.fifth = bytes.b; call.sixth = bytes.c;
            call.Complete(call.Invoke(observer, memory));
            const auto s = observer.GetSnapshot(2); Settled(s);
            assert(s.matched == 1 && s.paths[0].firstFlags == bytes.packed && s.paths[0].lastFlags == bytes.packed);
        }
        Pass("six arguments, unsigned request bytes, one original call, distinct return and output mutation survive forwarding");
    }
    {
        Observer observer(mc_animation_observer::PATHS); observer.Start(0);
        Memory memory(mc_animation_observer::PATHS[0]); Call call; call.throws = true;
        bool caught = false;
        try { call.Invoke(observer, memory); }
        catch (NativeError* error) { assert(error == &call.error); caught = true; }
        assert(caught && call.calls == 1 && call.output == &call.afterToken);
        const auto s = observer.GetSnapshot(2); Settled(s); assert(s.matched == 1);
        Pass("the exact original exception escapes; no retry or rollback of its output mutation");
    }
    {
        for (unsigned hop = 1; hop <= 3; ++hop) {
            Observer observer(mc_animation_observer::PATHS); observer.Start(0);
            Memory memory(mc_animation_observer::PATHS[0]); memory.throwAt = hop; Call call;
            call.Complete(call.Invoke(observer, memory));
            const auto s = observer.GetSnapshot(2); Settled(s);
            assert(memory.calls == hop && s.readFailures == 1 && !s.matched);
        }
        Pass("a Reader exception at any of the three reads still calls the original exactly once");
    }
    {
        Observer observer(mc_animation_observer::PATHS); observer.Start(0);
        Memory memory(mc_animation_observer::PATHS[0]); memory.readable = false; Call call;
        call.Complete(call.Invoke(observer, memory));
        const auto s = observer.GetSnapshot(2); Settled(s);
        assert(memory.calls == 1 && s.readFailures == 1 && !s.matched);
        Pass("unreadable path remains a request-read failure while original result and output pass through");
    }
    {
        Observer observer(mc_animation_observer::PATHS); Memory memory(mc_animation_observer::PATHS[0]); Call call;
        call.Complete(call.Invoke(observer, memory));
        const auto s = observer.GetSnapshot(2); Settled(s);
        assert(s.state == State::Inactive && !s.entries && !memory.calls);
        Pass("inactive observation performs no reads and still calls the original");
    }
    {
        Observer observer(mc_animation_observer::PATHS); observer.Start(100);
        Memory memory(mc_animation_observer::PATHS[0]); Call call;
        call.Complete(call.Invoke(observer, memory, 600100));
        const auto s = observer.GetSnapshot(600101); Settled(s);
        assert(s.state == State::Expired && !s.entries && !memory.calls);
        assert(!observer.Start(600102));
        Pass("deadline stops observation without suppressing the original or allowing another Start");
    }
    {
        Observer observer(mc_animation_observer::PATHS); observer.Start(100);
        Memory memory(mc_animation_observer::PATHS[0]); Call call;
        call.Complete(call.Invoke(observer, memory, 101, 7, 0, true));
        Call later; later.Complete(later.Invoke(observer, memory, 102));
        const auto s = observer.GetSnapshot(103); Settled(s);
        assert(s.state == State::Contaminated && !s.entries && !memory.calls);
        Pass("contamination and later stopped requests each forward once without reading paths");
    }
    {
        Observer observer(mc_animation_observer::PATHS); observer.Start(100);
        Memory memory(mc_animation_observer::PATHS[1]);
        Call late; late.fourth = 3; late.Complete(late.Invoke(observer, memory, 130, 30, 0x3030));
        Call early; early.fourth = 1; early.Complete(early.Invoke(observer, memory, 110, 10, 0x1010));
        Call middle; middle.fourth = 2; middle.Complete(middle.Invoke(observer, memory, 120, 20, 0x2020));
        auto s = observer.GetSnapshot(140); Settled(s);
        const auto& p = s.paths[1];
        assert(p.count == 3 && p.firstMs == 10 && p.lastMs == 30);
        assert(p.firstCallerRva == 0x1010 && p.lastCallerRva == 0x3030);
        assert(p.firstThread == 10 && p.lastThread == 30 && p.firstFlags == 0xff01 && p.lastFlags == 0xff03);
        Call equal; equal.fourth = 4; equal.Complete(equal.Invoke(observer, memory, 130, 31, 0));
        s = observer.GetSnapshot(140); Settled(s);
        assert(s.paths[1].firstCallerRva == 0x1010 && s.paths[1].lastCallerRva == 0);
        assert(s.paths[1].lastMs == 30 && s.paths[1].lastThread == 31 && s.paths[1].lastFlags == 0xff04);
        Pass("caller RVA stays with chronological first/last metadata; equal last time and unknown zero remain explicit");
    }
    {
        Observer observer(mc_animation_observer::PATHS); observer.Start(0);
        Memory memory(mc_animation_observer::PATHS[0]);
        for (uint64_t i = 0; i < mc_motion_observer::MAX_MATCHES; ++i) { Call call; call.Complete(call.Invoke(observer, memory)); }
        const auto reads = memory.calls;
        Call stopped; stopped.Complete(stopped.Invoke(observer, memory));
        const auto s = observer.GetSnapshot(2); Settled(s);
        assert(s.state == State::MatchLimit && s.matched == mc_motion_observer::MAX_MATCHES && memory.calls == reads);
        Pass("the request reaching the match cap and subsequent requests still call the original");
    }
    {
        Observer observer(mc_animation_observer::PATHS); observer.Start(0);
        Memory memory(mc_animation_observer::PATHS[0]);
        unsigned calls = 0;
        void* expectedPath = reinterpret_cast<void*>(Memory::OBJECT);
        auto original = [&](void* self, void** output, void* path, uint8_t a, uint8_t b, uint8_t c) -> void* {
            ++calls; assert(!self && !output && path == expectedPath && a == 0x80 && b == 0 && c == 0xff); return nullptr;
        };
        assert(mc_animation_observer::Forward(observer, 1, 0, 0, false,
            original, memory.Reader(), nullptr, nullptr, expectedPath, 0x80, 0, 0xff) == nullptr);
        assert(calls == 1 && memory.calls == 3);
        expectedPath = nullptr;
        assert(mc_animation_observer::Forward(observer, 1, 0, 0, false,
            original, memory.Reader(), nullptr, nullptr, nullptr, 0x80, 0, 0xff) == nullptr);
        assert(calls == 2 && memory.calls == 3);
        const auto s = observer.GetSnapshot(2); Settled(s);
        assert(s.matched == 1 && s.readFailures == 1);
        Pass("active observation forwards opaque null pointers and null return without dereferencing output");
    }
    assert(checks == 13);
    std::cout << checks << "/13 animation observer host checks passed\n";
}
'''


def run(args):
    result = subprocess.run(
        [str(arg) for arg in args], cwd=ROOT, capture_output=True, text=True, errors="replace"
    )
    if result.returncode:
        raise RuntimeError(f"Command failed: {args[0]}\n{result.stdout}\n{result.stderr}")
    return result.stdout


def main():
    build = ROOT / "build/animation-observer-host"
    build.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="isolated-", dir=build) as temp:
        folder = Path(temp)
        harness = folder / "harness.cpp"
        harness.write_text(HARNESS, encoding="utf-8")
        executable = folder / "check.exe"
        print(run([
            COMPILER, "-std=c++17", "-O1", "-Wall", "-Wextra", "-Werror", "-static", "-pthread",
            "-I" + str(ROOT / "red-side-patches"), harness, "-o", executable,
        ]), end="")
        print(run([executable]), end="")


if __name__ == "__main__":
    main()
