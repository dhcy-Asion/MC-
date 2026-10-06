#pragma once
// Fixed-resource diagnostics only. The checksum is evidence for byte comparison,
// never a cryptographic integrity check or proof that a prefab renders.
#include <cstdint>
#include <functional>
#include <map>
#include <mutex>
#include <string>
#include <utility>
#include <vector>

namespace mc_resource_probe {
constexpr uint32_t MAX_BYTES = 16384;
constexpr uint64_t TTL_MS = 30000;
constexpr unsigned MAX_TICKETS = 16;
enum class State { Pending, Read, NotFound, EmptyBuffer, ReadFailed, TooLarge, Unavailable, Expired };
struct ReadResult {
    State state = State::ReadFailed;
    uint32_t storedSize = 0, decodedSize = 0, storageFlags = 0;
    bool handlerPresent = false, handlerReleased = false;
    std::vector<uint8_t> bytes;
};
// Backend operations return failure instead of raising native faults. Release is
// attempted exactly once on every exit after the backend captured a handler.
template<class Backend> ReadResult ReadBounded(Backend& backend) {
    ReadResult out;
    auto read = [&]() {
        if (!backend.Load()) return State::ReadFailed;
        if (!backend.HasHandler()) return State::NotFound;
        if (!backend.Metadata(out.storedSize, out.decodedSize, out.storageFlags))
            return State::ReadFailed;
        const uint32_t need = (out.storageFlags & 15) == 1 ? out.storedSize : out.decodedSize;
        const uint32_t cap = out.storedSize > out.decodedSize ? out.storedSize : out.decodedSize;
        // Check BOTH native sizes before any resize or worker invocation, even
        // when partial storage chooses only one of them as the returned length.
        if (out.storedSize > MAX_BYTES || out.decodedSize > MAX_BYTES)
            return State::TooLarge;
        if (!need || !cap) return State::ReadFailed;
        out.bytes.resize(cap);
        if (!backend.Read(out.bytes.data(), cap)) return State::ReadFailed;
        out.bytes.resize(need);
        bool filled = false;
        const size_t head = out.bytes.size() < 64 ? out.bytes.size() : 64;
        for (size_t i = 0; i < head; ++i) if (out.bytes[i]) { filled = true; break; }
        return filled ? State::Read : State::EmptyBuffer;
    };
    try { out.state = read(); } catch (...) { out.state = State::ReadFailed; }
    // Release is outside the read's exception scope, never re-entered on failure.
    out.handlerPresent = backend.HasHandler();
    if (out.handlerPresent) {
        try { out.handlerReleased = backend.Release(); } catch (...) { out.handlerReleased = false; }
        if (!out.handlerReleased) out.state = State::ReadFailed;
    }
    if (out.state != State::Read) out.bytes.clear();
    return out;
}
const char* StateName(State state);
std::string ResourcePath(const std::string& resource);
bool ParseBody(const std::string& body, std::string& resource);
bool ParseTicket(const std::string& text, int& ticket);
uint64_t Fnv1a64(const std::vector<uint8_t>& bytes);
struct Snapshot {
    int ticket = 0;
    std::string resource, path, head16hex, fnv1a64;
    State state = State::Pending;
    unsigned attempts = 0;
    uint32_t length = 0, storedSize = 0, decodedSize = 0, storageFlags = 0;
    bool handlerPresent = false, handlerReleased = false;
};
enum class Admission { Accepted, UnknownResource, Unavailable, Busy };
struct Hooks {
    std::function<bool()> ready;
    std::function<uint64_t()> now;
    std::function<void(std::function<void()>)> queue;
    std::function<ReadResult(const std::string&)> read;
};
class Service {
public:
    explicit Service(Hooks hooks) : hooks_(std::move(hooks)) {}
    Admission Submit(const std::string& resource, Snapshot& out);
    bool Lookup(int ticket, Snapshot& out);
private:
    struct Record { Snapshot snapshot; uint64_t born = 0; bool queued = true, running = false; };
    void Attempt(int ticket);
    void Queue(int ticket);
    Hooks hooks_;
    std::mutex mutex_;
    std::map<int, Record> records_;
    int next_ = 1;
};
}
