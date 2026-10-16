#pragma once

#include <array>
#include <atomic>
#include <cstddef>
#include <cstdint>
#include <cstring>
#include <mutex>

// Observes requests at the existing ResourceLoader.load entry only. A match is
// not evidence of file reads, selected archive bytes, actor use or playback.
namespace mc_motion_observer {

inline constexpr std::size_t PATH_COUNT = 4;
inline constexpr uint64_t DURATION_MS = 600000;
inline constexpr uint64_t MAX_ENTRIES = 3000000;
inline constexpr uint64_t MAX_MATCHES = 128;
inline constexpr const char* PATHS[PATH_COUNT] = {
    "character/binary/motionblending/phm_locomotion/walk.motionblending",
    "character/binary/motionblending/phm_locomotion/basic_move_walk.motionblending",
    "character/binary/motionblending/phm_locomotion/basic_stride_walk.motionblending",
    "character/motion/1_pc/1_phm/cd_phm_00_00_nor_move_walk_f_00.paa",
};

inline const char* Path(std::size_t index) noexcept {
    return index < PATH_COUNT ? PATHS[index] : "";
}

enum class State : uint8_t {
    Inactive, Observing, Expired, EntryLimit, MatchLimit, Contaminated
};

inline const char* StateName(State state) noexcept {
    switch (state) {
    case State::Inactive: return "inactive";
    case State::Observing: return "observing";
    case State::Expired: return "expired";
    case State::EntryLimit: return "entry_limit";
    case State::MatchLimit: return "match_limit";
    case State::Contaminated: return "contaminated";
    }
    return "unknown";
}

struct PathSnapshot {
    uint64_t count = 0, firstMs = 0, lastMs = 0;
    uint32_t firstFlags = 0, lastFlags = 0, firstThread = 0, lastThread = 0;
};

struct Snapshot {
    State state = State::Inactive;
    uint64_t startedAtMs = 0, endedAtMs = 0;
    uint64_t entries = 0, dropped = 0, readFailures = 0, invalidPaths = 0;
    uint64_t unmatched = 0, matched = 0, inFlight = 0;
    std::array<PathSnapshot, PATH_COUNT> paths{};
};

class Observer {
public:
    // Control-thread operation, before the existing loader hook is enabled.
    // The process owns one capture; stopping never permits another Start.
    bool Start(uint64_t now) {
        std::lock_guard<std::mutex> lock(mutex_);
        if (started_.load(std::memory_order_relaxed)) return false;
        startedAtMs_ = now;
        started_.store(true, std::memory_order_release);
        return true;
    }

    template<class Reader>
    void Observe(uint64_t now, uint32_t flags, uint32_t tid, uintptr_t path,
                 bool contaminated, Reader read) noexcept {
        if (!Active()) return;
        if (contaminated) { Stop(State::Contaminated, now); return; }
        if (Expired(now)) { Stop(State::Expired, now); return; }

        uint64_t entry = entries_.load(std::memory_order_relaxed);
        do {
            if (entry == MAX_ENTRIES) { Stop(State::EntryLimit, now); return; }
        } while (!entries_.compare_exchange_weak(entry, entry + 1,
                    std::memory_order_relaxed));
        ++entry;

        // try_lock never waits for a loader thread or the snapshot exporter.
        // The only reads under this lock are the bounded, caught Reader calls;
        // the original loader call is outside this entire method.
        std::unique_lock<std::mutex> lock(mutex_, std::try_to_lock);
        if (!lock.owns_lock() || !Active()) {
            dropped_.fetch_add(1, std::memory_order_release);
        } else {
            char text[200] = {};
            const auto result = ReadPath(path, text, read);
            if (!Active()) {
                dropped_.fetch_add(1, std::memory_order_release);
            } else if (result == PathResult::ReadFailed) {
                ++totals_.readFailures;
            } else if (result == PathResult::Invalid) {
                ++totals_.invalidPaths;
            } else {
                std::size_t index = 0;
                while (index < PATH_COUNT && std::strcmp(text, PATHS[index])) ++index;
                if (index == PATH_COUNT) {
                    ++totals_.unmatched;
                } else {
                    auto& item = totals_.paths[index];
                    const uint64_t relative = now - startedAtMs_;
                    if (!item.count || relative < item.firstMs) {
                        item.firstMs = relative;
                        item.firstFlags = flags;
                        item.firstThread = tid;
                    }
                    if (!item.count || relative >= item.lastMs) {
                        item.lastMs = relative;
                        item.lastFlags = flags;
                        item.lastThread = tid;
                    }
                    ++item.count;
                    if (++totals_.matched == MAX_MATCHES) Stop(State::MatchLimit, now);
                }
            }
        }
        if (entry == MAX_ENTRIES) Stop(State::EntryLimit, now);
    }

    // Control/HTTP-thread operation only. No game memory or native calls.
    // A partial snapshot identifies admitted calls that have not settled yet.
    Snapshot GetSnapshot(uint64_t now) {
        if (Active() && Expired(now)) Stop(State::Expired, now);
        std::lock_guard<std::mutex> lock(mutex_);
        Snapshot result = totals_;
        if (started_.load(std::memory_order_acquire)) {
            result.startedAtMs = startedAtMs_;
            const uint64_t terminal = terminal_.load(std::memory_order_acquire);
            result.state = terminal ? static_cast<State>(terminal & 0xff) : State::Observing;
            if (terminal) result.endedAtMs = startedAtMs_ + (terminal >> 8);
        }
        // Read dropped before entries: every drop already reserved an entry.
        result.dropped = dropped_.load(std::memory_order_acquire);
        result.entries = entries_.load(std::memory_order_relaxed);
        result.inFlight = result.entries - result.dropped - result.readFailures -
            result.invalidPaths - result.unmatched - result.matched;
        return result;
    }

private:
    enum class PathResult { Text, ReadFailed, Invalid };

    bool Active() const noexcept {
        return started_.load(std::memory_order_acquire) &&
            !terminal_.load(std::memory_order_acquire);
    }
    bool Expired(uint64_t now) const noexcept {
        return now < startedAtMs_ || now - startedAtMs_ >= DURATION_MS;
    }
    void Stop(State state, uint64_t now) noexcept {
        uint64_t relative = now < startedAtMs_ ? 0 : now - startedAtMs_;
        if (relative > DURATION_MS) relative = DURATION_MS;
        // Publish reason and relative end time together; first stop wins.
        const uint64_t terminal = (relative << 8) | static_cast<uint8_t>(state);
        uint64_t expected = 0;
        terminal_.compare_exchange_strong(expected, terminal,
            std::memory_order_release, std::memory_order_relaxed);
    }
    static bool Pointer(uintptr_t value) noexcept {
        return value >= 0x10000 && (value >> 47) == 0;
    }
    template<class Reader>
    static bool Read(Reader& read, uintptr_t address, void* out, std::size_t size) noexcept {
        try { return read(address, out, size); }
        catch (...) { return false; }
    }
    template<class Reader>
    static PathResult ReadPath(uintptr_t path, char (&text)[200], Reader& read) noexcept {
        uintptr_t data = 0;
        if (!Pointer(path) || !Read(read, path, &data, sizeof data) || !Pointer(data))
            return PathResult::ReadFailed;
        bool failed = false;
        for (int hop = 0; hop < 2; ++hop) {
            if (Read(read, data, text, sizeof text - 1)) {
                std::size_t n = 0;
                while (n < sizeof text - 1 && text[n] >= 0x20 && text[n] < 0x7f) ++n;
                // text[199] is local padding, never evidence of a native NUL.
                if (n >= 4 && n < sizeof text - 1 && text[n] == 0) return PathResult::Text;
            } else {
                failed = true;
            }
            if (hop == 1) break;
            uintptr_t next = 0;
            if (!Read(read, data, &next, sizeof next)) { failed = true; break; }
            if (!Pointer(next)) break;
            data = next;
        }
        return failed ? PathResult::ReadFailed : PathResult::Invalid;
    }

    std::mutex mutex_;
    std::atomic<bool> started_{false};
    // Zero is active/unstarted; otherwise low byte is reason, high bits time.
    std::atomic<uint64_t> terminal_{0}, entries_{0}, dropped_{0};
    uint64_t startedAtMs_ = 0;
    Snapshot totals_{};
};

} // namespace mc_motion_observer
