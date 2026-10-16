#pragma once
#include "mc_motion_observer.h"

// Fixed EXE 1.0.0.2976, SHA256 57da440d72f4db974f25fef047cf84c4dadd999a88cb2a3c5af4c9bd67fde1e7.
// RVA 0x2e91250 takes three opaque pointers and three low-byte arguments;
// returns the original output pointer. No object ownership is transferred here.
namespace mc_animation_observer {
inline constexpr const char* PATHS[] = {
    "character/motion/1_pc/1_phm/cd_phm_00_00_nor_move_walk_f_00.paa",
    "character/motion/1_pc/1_phm/cd_phm_basic_00_00_nor_move_walk_ing_00.paa",
};

template<class Original, class Reader>
void* Forward(mc_motion_observer::Observer& observer, uint64_t now, uint32_t tid,
              uint32_t callerRva, bool contaminated, Original original, Reader read,
              void* self, void** output, void* path, uint8_t fourth, uint8_t fifth, uint8_t sixth) {
    // R8 -> holder -> chars is independently consumed at 0x2e63bee/0x2e63bf9.
    // These are opaque request bytes, not named loading flags or archive flags.
    const uint32_t requestBytes = fourth | (uint32_t(fifth) << 8) | (uint32_t(sixth) << 16);
    observer.Observe(now, requestBytes, tid, (uintptr_t)path, contaminated, read, callerRva);
    // Do not catch, retry, release, dereference output or change native results.
    return original(self, output, path, fourth, fifth, sixth);
}
} // namespace mc_animation_observer
