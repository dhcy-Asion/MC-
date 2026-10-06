// Viewport layout and confirmed inventory state, shared by the UI and host checks.
#pragma once
#include <algorithm>
#include <cmath>
#include <cstdint>
#include <utility>
#include "mc_inventory_protocol.h"

namespace mc_hotbar {
constexpr int kSlots = 9;
constexpr uint64_t kFreshForMs = 6000;

struct Layout {
    float x = 0, y = 0, width = 0, height = 0;
    float cell = 0, border = 2, labelHeight = 22;
    bool visible = false;
};
inline Layout Measure(float width, float height) {
    Layout out;
    if (!std::isfinite(width) || !std::isfinite(height) || width < 96 || height < 64) return out;
    const float margin = std::floor(std::clamp(height * 0.025f, 4.0f, 24.0f));
    out.cell = std::floor(std::min(std::clamp(height / 18.0f, 28.0f, 58.0f),
                                  (width - margin * 2 - out.border * 2) / kSlots));
    out.width = out.cell * kSlots + out.border * 2;
    out.height = out.cell + out.border * 2 + out.labelHeight;
    out.x = std::floor((width - out.width) / 2);
    out.y = std::floor(height - margin - out.height);
    out.visible = out.cell >= 8 && out.y >= 0;
    return out;
}

enum class Status { Connecting, Offline, Confirming, Stale, Current };
struct Snapshot {
    mc_inventory::Inventory value;
    bool known = false, failed = false, confirmationRequired = false;
    uint64_t confirmedAt = 0;

    void Accept(mc_inventory::Inventory next, uint64_t now) {
        value = std::move(next);
        known = true; failed = false; confirmationRequired = false; confirmedAt = now;
    }
    void Fail() { failed = true; }
    void RequireConfirmation() { confirmationRequired = true; }
    Status State(uint64_t now) const {
        if (failed) return Status::Offline;
        if (!known) return Status::Connecting;
        if (confirmationRequired) return Status::Confirming;
        if (now < confirmedAt || now - confirmedAt > kFreshForMs) return Status::Stale;
        return Status::Current;
    }
    bool Current(uint64_t now) const { return State(now) == Status::Current; }
    // Never invent a hotbar selection when the server selects one of slots 9..35.
    int Highlight(uint64_t now) const {
        return Current(now) && value.selected >= 0 && value.selected < kSlots ? value.selected : -1;
    }
};
}
