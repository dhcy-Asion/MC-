#include "mc_resource_probe.h"
#include <cstdio>
#include <limits>
#include <utility>

namespace mc_resource_probe {
const char* StateName(State state) {
    switch (state) {
    case State::Pending: return "pending";
    case State::Read: return "read";
    case State::NotFound: return "notFound";
    case State::EmptyBuffer: return "emptyBuffer";
    case State::TooLarge: return "tooLarge";
    case State::Unavailable: return "unavailable";
    case State::Expired: return "expired";
    default: return "readFailed";
    }
}
std::string ResourcePath(const std::string& resource) {
    const char* suffixes[] = { "prefab", "meshinfo", "pam", "pamlod", "pami", "hkx" };
    const char* axes[] = { "x", "y", "z" };
    for (const char* suffix : suffixes) {
        const std::string prefix = std::string(suffix) == "prefab" || std::string(suffix) == "meshinfo"
            ? "object/bin__/00_common/system/" : "object/00_common/system/";
        if (resource == std::string("blue_") + suffix)
            return prefix + "cd_testfield_grid_box_1m." + suffix;
        for (const char* axis : axes)
            if (resource == std::string("oak_") + axis + "_" + suffix)
                return prefix + "crimsonmc_oak_log_" + axis + "." + suffix;
    }
    if (resource == "oak_atlas") return "object/texture/crimsonmc_oak_log_atlas.dds";
    if (resource == "oak_atlas_n") return "object/texture/crimsonmc_oak_log_atlas_n.dds";
    if (resource == "oak_atlas_sp") return "object/texture/crimsonmc_oak_log_atlas_sp.dds";
    return "";
}
// One literal string field. No duplicate keys, escapes, arrays, path or query
// substitute: identifiers are the fixed ASCII names above, not arbitrary JSON.
bool ParseBody(const std::string& body, std::string& resource) {
    resource.clear();
    if (body.size() > 128) return false;
    size_t p = 0;
    auto space = [&]() { while (p < body.size() && (body[p] == ' ' || body[p] == '\n' || body[p] == '\r' || body[p] == '\t')) ++p; };
    auto take = [&](char ch) { space(); return p < body.size() && body[p++] == ch; };
    auto quoted = [&](std::string& text) {
        if (!take('"')) return false;
        while (p < body.size()) {
            const unsigned char ch = body[p++];
            if (ch == '"') return true;
            if (ch < 32 || ch > 126 || ch == '\\') return false;
            text += (char)ch;
        }
        return false;
    };
    std::string key;
    if (!take('{') || !quoted(key) || key != "resource" || !take(':') || !quoted(resource) || !take('}')) return false;
    space(); return p == body.size() && !resource.empty();
}
bool ParseTicket(const std::string& text, int& ticket) {
    ticket = 0;
    if (text.empty() || text.size() > 10) return false;
    uint64_t value = 0;
    for (char ch : text) {
        if (ch < '0' || ch > '9') return false;
        value = value * 10 + (unsigned)(ch - '0');
        if (value > 2147483646u) return false;
    }
    if (!value) return false;
    ticket = (int)value; return true;
}
uint64_t Fnv1a64(const std::vector<uint8_t>& bytes) {
    uint64_t value = UINT64_C(14695981039346656037);
    for (uint8_t ch : bytes) { value ^= ch; value *= UINT64_C(1099511628211); }
    return value;
}
Admission Service::Submit(const std::string& resource, Snapshot& out) {
    const std::string path = ResourcePath(resource);
    if (path.empty()) return Admission::UnknownResource;
    if (!hooks_.ready()) return Admission::Unavailable;
    const uint64_t now = hooks_.now();
    int ticket = 0;
    {
        std::lock_guard<std::mutex> lock(mutex_);
        for (auto it = records_.begin(); it != records_.end();) {
            if (now - it->second.born >= TTL_MS && !it->second.queued && !it->second.running) it = records_.erase(it); else ++it;
        }
        // A paused game pump must retain every unexecuted lambda's slot even
        // after TTL. Completed receipts may be evicted for sequential --all.
        if (records_.size() >= MAX_TICKETS) {
            for (auto it = records_.begin(); it != records_.end(); ++it)
                if (!it->second.queued && !it->second.running) { records_.erase(it); break; }
        }
        if (records_.size() >= MAX_TICKETS || next_ >= std::numeric_limits<int>::max()) return Admission::Busy;
        ticket = next_++;
        Record row; row.snapshot.ticket = ticket; row.snapshot.resource = resource; row.snapshot.path = path; row.born = now;
        out = row.snapshot; records_.emplace(ticket, std::move(row));
    }
    Queue(ticket);
    return Admission::Accepted;
}
bool Service::Lookup(int ticket, Snapshot& out) {
    const uint64_t now = hooks_.now();
    std::lock_guard<std::mutex> lock(mutex_);
    auto it = records_.find(ticket); if (it == records_.end()) return false;
    if (now - it->second.born >= TTL_MS) it->second.snapshot.state = State::Expired;
    out = it->second.snapshot; return true;
}
void Service::Queue(int ticket) {
    try { hooks_.queue([this, ticket]() { Attempt(ticket); }); }
    catch (...) {
        std::lock_guard<std::mutex> lock(mutex_);
        auto it = records_.find(ticket);
        if (it != records_.end()) { it->second.queued = false; it->second.snapshot.state = State::ReadFailed; }
    }
}
void Service::Attempt(int ticket) {
    const uint64_t now = hooks_.now();
    std::string path;
    {
        std::lock_guard<std::mutex> lock(mutex_);
        auto it = records_.find(ticket); if (it == records_.end()) return;
        auto& row = it->second;
        row.queued = false; // This lambda now occupies the executing game tick.
        if (now - row.born >= TTL_MS) { row.snapshot.state = State::Expired; return; }
        if (row.running || row.snapshot.state != State::Pending) return;
        row.running = true; path = row.snapshot.path; ++row.snapshot.attempts;
    }
    ReadResult result;
    try { if (hooks_.ready()) result = hooks_.read(path); else result.state = State::Unavailable; }
    catch (...) { result.state = State::ReadFailed; }
    if (result.bytes.size() > MAX_BYTES) { result.state = State::TooLarge; result.bytes.clear(); }
    Snapshot measured;
    measured.length = (uint32_t)result.bytes.size(); measured.storedSize = result.storedSize;
    measured.decodedSize = result.decodedSize; measured.storageFlags = result.storageFlags;
    measured.handlerPresent = result.handlerPresent; measured.handlerReleased = result.handlerReleased;
    measured.state = result.state;
    if (result.state == State::Read) {
        const char* hex = "0123456789abcdef";
        for (size_t i = 0; i < result.bytes.size() && i < 16; ++i) {
            measured.head16hex += hex[result.bytes[i] >> 4]; measured.head16hex += hex[result.bytes[i] & 15];
        }
        char value[17]; std::snprintf(value, sizeof value, "%016llx", (unsigned long long)Fnv1a64(result.bytes)); measured.fnv1a64 = value;
    }
    bool retry = false;
    const uint64_t finished = hooks_.now();
    {
        std::lock_guard<std::mutex> lock(mutex_);
        auto it = records_.find(ticket); if (it == records_.end()) return;
        auto& row = it->second; row.running = false;
        measured.ticket = ticket; measured.resource = row.snapshot.resource; measured.path = path; measured.attempts = row.snapshot.attempts;
        if (finished - row.born >= TTL_MS || row.snapshot.state == State::Expired) measured.state = State::Expired;
        retry = measured.state == State::EmptyBuffer && measured.attempts < 3;
        if (retry) { measured.state = State::Pending; row.queued = true; }
        if (measured.state == State::Expired) { measured.length = 0; measured.head16hex.clear(); measured.fnv1a64.clear(); }
        row.snapshot = std::move(measured);
    }
    if (retry) Queue(ticket);
}
}
