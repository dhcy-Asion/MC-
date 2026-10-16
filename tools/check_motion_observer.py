"""Compile the real fixed-path observer with fake memory; no game or network."""

from pathlib import Path
import subprocess
import tempfile


ROOT = Path(__file__).resolve().parents[1]
COMPILER = Path("C:/msys64/ucrt64/bin/g++.exe")

HARNESS = r'''
#include "mc_motion_observer.h"
#include <algorithm>
#include <cassert>
#include <cstdlib>
#include <iostream>
#include <new>
#include <stdexcept>
#include <thread>
#include <vector>

static std::atomic<uint64_t> allocations{0};
void* operator new(std::size_t n) {
    allocations.fetch_add(1);
    if (void* p = std::malloc(n ? n : 1)) return p;
    throw std::bad_alloc();
}
void* operator new[](std::size_t n) { return ::operator new(n); }
// Keep the replacement deallocators opaque to GCC's caller-side pairing check.
[[gnu::noinline]] void operator delete(void* p) noexcept { std::free(p); }
[[gnu::noinline]] void operator delete[](void* p) noexcept { std::free(p); }
[[gnu::noinline]] void operator delete(void* p, std::size_t) noexcept { std::free(p); }
[[gnu::noinline]] void operator delete[](void* p, std::size_t) noexcept { std::free(p); }

using namespace mc_motion_observer;
static int checks = 0;
static void Pass(const char* name) { ++checks; std::cout << "PASS " << name << '\n'; }

struct Memory {
    struct Region { uintptr_t base; std::array<uint8_t, 256> bytes{}; };
    std::array<Region, 3> regions{{{0x10000, {}}, {0x20000, {}}, {0x30000, {}}}};
    std::atomic<uint64_t> calls{0}, copied{0};
    bool readable = true, throws = false;

    explicit Memory(const char* text, bool indirect = false) {
        const uintptr_t data = regions[1].base;
        const uintptr_t first = indirect ? regions[2].base : data;
        std::memcpy(regions[0].bytes.data(), &first, sizeof first);
        std::memcpy(regions[2].bytes.data(), &data, sizeof data);
        assert(std::strlen(text) < regions[1].bytes.size());
        std::memcpy(regions[1].bytes.data(), text, std::strlen(text) + 1);
    }
    bool Read(uintptr_t address, void* out, std::size_t size) {
        ++calls;
        if (throws) throw std::runtime_error("fake reader fault");
        if (!readable) return false;
        for (const auto& region : regions) {
            if (address >= region.base && address - region.base <= region.bytes.size() &&
                size <= region.bytes.size() - (address - region.base)) {
                std::memcpy(out, region.bytes.data() + (address - region.base), size);
                copied += size;
                return true;
            }
        }
        return false;
    }
    auto Reader() {
        return [this](uintptr_t address, void* out, std::size_t size) {
            return Read(address, out, size);
        };
    }
};

static void Settled(const Snapshot& s) {
    assert(!s.inFlight);
    assert(s.entries == s.dropped + s.readFailures + s.invalidPaths + s.unmatched + s.matched);
    uint64_t hits = 0;
    for (const auto& path : s.paths) hits += path.count;
    assert(hits == s.matched && hits <= MAX_MATCHES && s.entries <= MAX_ENTRIES);
}

int main() {
    static_assert(PATH_COUNT == 4 && DURATION_MS == 600000 && MAX_ENTRIES == 3000000 && MAX_MATCHES == 128);
    {
        Observer observer; Memory memory(Path(0));
        observer.Observe(10, 0, 1, 0x10000, false, memory.Reader());
        assert(observer.GetSnapshot(10).state == State::Inactive && memory.calls == 0);
        assert(observer.Start(10) && !observer.Start(20));
        auto s = observer.GetSnapshot(20);
        assert(s.state == State::Observing && s.startedAtMs == 10 && s.entries == 0);
        Pass("default inactive; exactly one Start");
    }
    {
        Observer observer; assert(observer.Start(100));
        for (std::size_t i = 0; i < PATH_COUNT; ++i) {
            Memory memory(Path(i)); const auto before = memory.regions;
            const auto allocated = allocations.load();
            observer.Observe(110 + i, uint32_t(40 + i), uint32_t(50 + i), 0x10000, false, memory.Reader());
            assert(allocations == allocated && memory.calls == 2 && memory.copied == 207);
            assert(std::memcmp(before.data(), memory.regions.data(), sizeof before) == 0);
        }
        auto s = observer.GetSnapshot(120); Settled(s);
        assert(s.matched == 4 && s.entries == 4);
        for (std::size_t i = 0; i < PATH_COUNT; ++i) {
            const auto& item = s.paths[i];
            assert(item.count == 1 && item.firstMs == 10 + i && item.lastMs == item.firstMs);
            assert(item.firstFlags == 40 + i && item.lastFlags == item.firstFlags);
            assert(item.firstThread == 50 + i && item.lastThread == item.firstThread);
        }
        Pass("four exact requests; flags/thread/time; no allocation or source writes");
    }
    {
        Observer observer; observer.Start(100); Memory memory(Path(3), true);
        observer.Observe(130, 3, 30, 0x10000, false, memory.Reader());
        assert(memory.calls == 4 && memory.copied == 414);
        observer.Observe(110, 1, 10, 0x10000, false, memory.Reader());
        observer.Observe(120, 2, 20, 0x10000, false, memory.Reader());
        const auto s = observer.GetSnapshot(140); Settled(s);
        const auto& item = s.paths[3];
        assert(item.count == 3 && item.firstMs == 10 && item.lastMs == 30);
        assert(item.firstFlags == 1 && item.firstThread == 10 && item.lastFlags == 3 && item.lastThread == 30);
        Pass("two-hop path and chronological first/last under reordered callbacks");
    }
    {
        Observer observer; observer.Start(0);
        const char* unknown[] = {
            "walk.motionblending", "character/binary/motionblending/phm_locomotion/walk.motionblending.extra",
            "prefix/character/binary/motionblending/phm_locomotion/walk.motionblending",
            "Character/binary/motionblending/phm_locomotion/walk.motionblending",
            "character/motion/1_pc/1_phm/cd_phm_basic_00_00_nor_move_walk_f_ing2_00.paa"
        };
        for (auto text : unknown) {
            Memory memory(text); observer.Observe(1, 0, 1, 0x10000, false, memory.Reader());
        }
        const auto s = observer.GetSnapshot(2); Settled(s);
        assert(s.unmatched == 5 && !s.matched);
        Pass("no substring, basename, case-folding or unapproved forward PAA matches");
    }
    {
        Observer observer; observer.Start(0); Memory memory(Path(0));
        memory.readable = false;
        observer.Observe(1, 0, 1, 0x10000, false, memory.Reader());
        memory.readable = true; memory.throws = true;
        observer.Observe(2, 0, 1, 0x10000, false, memory.Reader());
        memory.throws = false;
        observer.Observe(3, 0, 1, 1, false, memory.Reader());
        const auto s = observer.GetSnapshot(4); Settled(s);
        assert(s.readFailures == 3 && !s.matched);
        Pass("unreadable, thrown Reader exception and invalid pointer fail closed");
    }
    {
        Observer observer; observer.Start(0); Memory memory(Path(0));
        std::fill(memory.regions[1].bytes.begin(), memory.regions[1].bytes.end(), uint8_t('a'));
        observer.Observe(1, 0, 1, 0x10000, false, memory.Reader());
        memory.regions[1].bytes[199] = 0;
        observer.Observe(2, 0, 1, 0x10000, false, memory.Reader());
        memory.regions[1].bytes[0] = 0x7f;
        memory.regions[1].bytes[1] = 0;
        observer.Observe(3, 0, 1, 0x10000, false, memory.Reader());
        const auto s = observer.GetSnapshot(4); Settled(s);
        assert(s.invalidPaths == 3 && !s.matched);
        Pass("requires native NUL within 199 bytes and printable ASCII");
    }
    {
        Observer observer; observer.Start(10); Memory memory(Path(0));
        observer.Observe(10 + DURATION_MS - 1, 0, 1, 0x10000, false, memory.Reader());
        const auto calls = memory.calls.load();
        observer.Observe(10 + DURATION_MS, 0, 1, 0x10000, false, memory.Reader());
        const auto s = observer.GetSnapshot(10 + DURATION_MS + 1); Settled(s);
        assert(s.state == State::Expired && s.endedAtMs == 10 + DURATION_MS);
        assert(s.matched == 1 && memory.calls == calls && !observer.Start(999999));
        Observer idle; idle.Start(10);
        assert(idle.GetSnapshot(10 + DURATION_MS).state == State::Expired);
        Pass("exact deadline stops before path reads; idle snapshot expires; no rearm");
    }
    {
        Observer observer; observer.Start(10); Memory memory(Path(0));
        observer.Observe(20, 0, 1, 0x10000, true, memory.Reader());
        observer.Observe(21, 0, 1, 0x10000, false, memory.Reader());
        const auto s = observer.GetSnapshot(22); Settled(s);
        assert(s.state == State::Contaminated && s.endedAtMs == 20 && !s.entries && !memory.calls);
        assert(!observer.Start(30));
        Pass("contamination is terminal and never reads a path");
    }
    {
        Observer observer; observer.Start(0); Memory memory(Path(0));
        for (uint64_t i = 0; i < MAX_MATCHES + 10; ++i)
            observer.Observe(i + 1, 0, 1, 0x10000, false, memory.Reader());
        const auto s = observer.GetSnapshot(1000); Settled(s);
        assert(s.state == State::MatchLimit && s.matched == MAX_MATCHES && s.entries == MAX_MATCHES);
        assert(memory.calls == MAX_MATCHES * 2);
        Pass("128 total matched requests stop capture without extra reads");
    }
    {
        Observer observer; observer.Start(0); Memory memory("unknown/path.paa");
        for (uint64_t i = 0; i < MAX_ENTRIES + 10; ++i)
            observer.Observe(1, 0, 1, 0x10000, false, memory.Reader());
        const auto s = observer.GetSnapshot(2); Settled(s);
        assert(s.state == State::EntryLimit && s.unmatched == MAX_ENTRIES && s.entries == MAX_ENTRIES);
        assert(memory.calls == MAX_ENTRIES * 2);
        Pass("3000000 admitted entries is a hard path-read budget");
    }
    {
        Observer observer; observer.Start(0); Memory memory(Path(0));
        std::atomic<bool> entered{false}, release{false};
        std::thread reader([&]() {
            observer.Observe(1, 0, 1, 0x10000, false,
                [&](uintptr_t address, void* out, std::size_t size) {
                    entered.store(true); while (!release.load()) std::this_thread::yield();
                    return memory.Read(address, out, size);
                });
        });
        while (!entered.load()) std::this_thread::yield();
        observer.Observe(2, 0, 2, 0x10000, false, memory.Reader());
        release.store(true); reader.join();
        const auto s = observer.GetSnapshot(3); Settled(s);
        assert(s.entries == 2 && s.dropped == 1 && s.matched == 1 && memory.calls == 2);
        Pass("contended callback returns immediately and accounts for dropped request");
    }
    {
        Observer observer; observer.Start(0); Memory memory(Path(0));
        std::atomic<bool> entered{false}, release{false};
        std::thread reader([&]() {
            observer.Observe(1, 0, 1, 0x10000, false,
                [&](uintptr_t address, void* out, std::size_t size) {
                    entered.store(true); while (!release.load()) std::this_thread::yield();
                    return memory.Read(address, out, size);
                });
        });
        while (!entered.load()) std::this_thread::yield();
        observer.Observe(2, 0, 2, 0x10000, true, memory.Reader());
        release.store(true); reader.join();
        const auto s = observer.GetSnapshot(3); Settled(s);
        assert(s.state == State::Contaminated && s.dropped == 1 && !s.matched);
        Pass("concurrent stop suppresses an in-flight match without touching native lifecycle");
    }
    {
        Observer observer; observer.Start(0); Memory memory("unknown/path.paa");
        std::vector<std::thread> threads;
        for (uint32_t thread = 0; thread < 8; ++thread) threads.emplace_back([&, thread]() {
            for (uint64_t i = 0; i < MAX_ENTRIES / 8 + 1; ++i)
                observer.Observe(1, thread, thread, 0x10000, false, memory.Reader());
        });
        for (auto& thread : threads) thread.join();
        const auto s = observer.GetSnapshot(2); Settled(s);
        assert(s.state == State::EntryLimit && s.entries == MAX_ENTRIES && !s.matched);
        assert(memory.calls <= MAX_ENTRIES * 2 && memory.copied <= MAX_ENTRIES * 207);
        Pass("eight loader threads preserve hard budget and complete counter accounting");
    }
    {
        Observer observer; observer.Start(0); Memory memory("unknown/path.paa");
        std::atomic<int> finished{0};
        std::vector<std::thread> threads;
        for (uint32_t thread = 0; thread < 4; ++thread) threads.emplace_back([&, thread]() {
            for (int i = 0; i < 2000; ++i)
                observer.Observe(1, thread, thread, 0x10000, false, memory.Reader());
            ++finished;
        });
        do {
            const auto s = observer.GetSnapshot(2);
            assert(s.inFlight <= s.entries && s.entries <= MAX_ENTRIES);
            assert(s.entries == s.dropped + s.unmatched + s.inFlight);
            std::this_thread::yield();
        } while (finished.load() < 4);
        for (auto& thread : threads) thread.join();
        const auto s = observer.GetSnapshot(3); Settled(s);
        assert(s.entries == 8000 && s.state == State::Observing);
        Pass("concurrent snapshot exports keep partial accounting bounded and settled totals exact");
    }
    {
        Observer observer; observer.Start(0); Memory startup("unknown/startup/path.paa");
        for (uint64_t i = 0; i < 100000; ++i)
            observer.Observe(26859, 0, 1, 0x10000, false, startup.Reader());
        const auto before = observer.GetSnapshot(120000); Settled(before);
        assert(before.state == State::Observing && before.entries == 100000 && !before.matched);
        Memory target(Path(3));
        observer.Observe(130000, 50, 7, 0x10000, false, target.Reader());
        const auto after = observer.GetSnapshot(130001); Settled(after);
        assert(after.state == State::Observing && after.entries == 100001 && after.unmatched == 100000);
        assert(after.matched == 1 && after.paths[3].count == 1 && after.paths[3].firstMs == 130000);
        assert(target.calls == 2);
        Pass("startup regression: original 100000 entries do not prevent a later target request");
    }
    std::cout << checks << " isolated motion observer checks passed\n";
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
    build = ROOT / "build/motion-observer-host"
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
