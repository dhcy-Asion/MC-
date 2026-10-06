"""Host-check nine-slot layout, confirmation rules and the actual ImGui renderer.

No game, bridge, inventory mutation or installation is used. The C++ harness
intercepts WinHttpSendRequest before it can send anything, including UI clicks.
"""
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
COMPILER = Path("C:/msys64/ucrt64/bin/g++.exe")
IMGUI = ROOT / "vendor/world-builder/tools/imgui"
UPSTREAM = ROOT / "vendor/world-builder/asi/cdmodkit"
SOURCE = r'''
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <winhttp.h>
#include <cassert>
#include <cmath>
#include <iostream>
#include <mutex>
#include <vector>
#include <limits>
#include <imgui.h>
#include <imgui_internal.h>
std::mutex sentMutex;
std::vector<std::string> sentBodies, thumbs;
BOOL WINAPI InterceptSend(HINTERNET, LPCWSTR, DWORD, LPVOID body, DWORD length, DWORD, DWORD_PTR) {
    std::lock_guard<std::mutex> lock(sentMutex);
    sentBodies.emplace_back(length ? std::string(static_cast<char*>(body),length) : "");
    return FALSE; // No request leaves this process, even if a real bridge is running.
}
#define WinHttpSendRequest InterceptSend
#include "mc_inventory_ui.cpp"
#include "mc_panel.cpp"
#undef WinHttpSendRequest
namespace core {
    std::string ModDir() { return "test-icons"; }
    int g_keyToggle = VK_F8;
    const char* KeyName(int) { return "F8"; }
}
namespace editor { bool IsOpen() { return false; } bool PlayMode() { return false; } }
namespace i18n { void AddGlyphText(const std::string&) {} }
namespace overlay {
    ImTextureID Thumb(const std::string& file, int*, int*) { thumbs.push_back(file); return 2; }
}
namespace mc_inventory_ui {
void Load(int selected = 5) {
    mc_inventory::Inventory next;
    next.selected = selected; next.revision = 42;
    for (int n = 0; n < 36; ++n) next.slots[n] = {
        "minecraft:item_" + std::to_string(n), "测试物品", n < 9 ? n + 1 : 64, 64};
    snapshot.Accept(std::move(next),GetTickCount64());
    refreshInventory = false; lastInventoryPoll = GetTickCount64();
}
std::string InventoryText(int selected) {
    std::string text = "inventory\t43\t" + std::to_string(selected) + "\n";
    for (int n=0;n<36;++n) text += "slot\t" + std::to_string(n) + "\t-\t0\t0\t\n";
    return text;
}
void Deliver(Reply reply) {
    assert(!pending.valid());
    std::promise<Reply> completed;
    pending = completed.get_future(); completed.set_value(std::move(reply));
    CollectReply();
}
}

int highlightVertices() {
    int count = 0;
    const auto* data = ImGui::GetDrawData();
    for (int n=0; n<data->CmdListsCount; ++n)
        for (const auto& vertex : data->CmdLists[n]->VtxBuffer)
            if (vertex.col == IM_COL32(242,248,219,255)) ++count;
    return count;
}
void Frame(bool interactive, float width = 1280, float height = 720) {
    auto& io = ImGui::GetIO();
    io.DisplaySize = ImVec2(width,height); io.DeltaTime = 1.0f / 60;
    thumbs.clear();
    ImGui::NewFrame(); mc_inventory_ui::DrawHotbar(interactive); ImGui::Render();
    const auto* data = ImGui::GetDrawData();
    assert(data->Valid && data->CmdListsCount > 0 && data->TotalVtxCount > 0);
    const auto layout = mc_hotbar::Measure(width,height);
    const auto* window = ImGui::FindWindowByName("MC Hotbar###crimsonmc-hotbar");
    assert(window && window->Active);
    assert(window->Pos.x == layout.x && window->Pos.y == layout.y);
    assert(window->Size.x == layout.width && window->Size.y == layout.height);
    assert(((window->Flags & ImGuiWindowFlags_NoInputs) == ImGuiWindowFlags_NoInputs) == !interactive);
    assert(window->Flags & ImGuiWindowFlags_NoNavInputs);
    assert(window->Flags & ImGuiWindowFlags_NoNavFocus);
    for (int n=0; n<data->CmdListsCount; ++n) {
        const auto* list = data->CmdLists[n];
        for (const auto& vertex : list->VtxBuffer) assert(std::isfinite(vertex.pos.x) && std::isfinite(vertex.pos.y));
        for (const auto& command : list->CmdBuffer) {
            assert(command.ClipRect.x >= 0 && command.ClipRect.y >= 0);
            assert(command.ClipRect.z <= width && command.ClipRect.w <= height);
        }
    }
}
int main() {
    using namespace mc_hotbar;
    for (const auto size : {ImVec2(96,64),ImVec2(160,100),ImVec2(320,240),ImVec2(1280,720),
                            ImVec2(1920,1080),ImVec2(2560,1440),ImVec2(3840,2160),ImVec2(5120,1440)}) {
        const auto layout = Measure(size.x,size.y);
        assert(layout.visible && layout.cell >= 8);
        assert(layout.width == layout.cell * 9 + layout.border * 2);
        assert(layout.x >= 0 && layout.y >= 0);
        assert(layout.x + layout.width <= size.x && layout.y + layout.height <= size.y);
        assert(std::fabs(layout.x + layout.width/2 - size.x/2) <= 1);
    }
    assert(!Measure(80,40).visible);
    assert(!Measure(std::numeric_limits<float>::quiet_NaN(),720).visible);
    assert(!Measure(1280,std::numeric_limits<float>::infinity()).visible);

    Snapshot state;
    assert(state.State(100) == Status::Connecting && state.Highlight(100) == -1);
    state.Fail(); assert(state.State(100) == Status::Offline);
    mc_inventory::Inventory sample;
    sample.selected = 8; state.Accept(sample,100);
    assert(state.Current(100) && state.Highlight(100) == 8);
    assert(state.Current(100+kFreshForMs) && !state.Current(101+kFreshForMs));
    assert(state.State(101+kFreshForMs) == Status::Stale && state.Highlight(101+kFreshForMs) == -1);
    assert(!state.Current(99)); // A clock anomaly cannot make an old value current.
    state.RequireConfirmation(); assert(state.State(101) == Status::Confirming && state.Highlight(101) == -1);
    state.Fail(); assert(state.State(101) == Status::Offline && state.known && state.value.selected == 8);
    for (int n=0;n<36;++n) {
        sample.selected = n; state.Accept(sample,200);
        assert(state.Highlight(200) == (n < 9 ? n : -1));
    }

    ImGui::CreateContext();
    auto& io = ImGui::GetIO(); io.IniFilename = nullptr; io.LogFilename = nullptr;
    unsigned char* pixels; int width,height;
    io.Fonts->GetTexDataAsRGBA32(&pixels,&width,&height); io.Fonts->SetTexID(1);
    using namespace mc_inventory_ui;
    Load(); Frame(false);
    assert(thumbs.size() == 9 && highlightVertices() > 0);
    for (int n=0;n<9;++n) assert(thumbs[n] == "test-icons\\mc-icons\\item_" + std::to_string(n) + ".png");
    Load(13); Frame(true); assert(thumbs.size() == 9 && highlightVertices() == 0);
    snapshot.Fail(); Frame(true); assert(thumbs.size() == 9 && highlightVertices() == 0);
    Load(); snapshot.confirmedAt -= kFreshForMs+1;
    Frame(true); assert(highlightVertices() == 0);
    snapshot = {}; Frame(true); assert(thumbs.empty() && highlightVertices() == 0);
    Load();
    for (const auto size : {ImVec2(96,64),ImVec2(320,240),ImVec2(1920,1080),ImVec2(3840,2160)}) Frame(false,size.x,size.y);

    const auto layout = Measure(1280,720);
    io.AddMousePosEvent(layout.x + layout.border + 2.5f * layout.cell,
                        layout.y + layout.labelHeight + layout.border + layout.cell / 2);
    Frame(false); io.AddMouseButtonEvent(0,true); Frame(false);
    io.AddMouseButtonEvent(0,false); Frame(false);
    assert(!pending.valid() && sentBodies.empty() && !io.WantCaptureMouse);

    Frame(true); Frame(true);
    io.AddMouseButtonEvent(0,true); Frame(true);
    io.AddMouseButtonEvent(0,false); Frame(true);
    assert(pending.valid()); pending.wait(); CollectReply();
    assert(sentBodies.size() == 1 && sentBodies[0] == "{\"slot\":2}");
    assert(inventory.selected == 5 && snapshot.Highlight(GetTickCount64()) == -1);
    Frame(true); assert(!pending.valid() && sentBodies.size() == 1); // A failed mutation never retries.
    Deliver({Kind::Inventory,true,InventoryText(2)});
    assert(inventory.selected == 2 && snapshot.Highlight(GetTickCount64()) == 2);
    Deliver({Kind::Inventory,true,"inventory\t43\t2\n"});
    assert(snapshot.known && inventory.selected == 2 && !snapshot.Current(GetTickCount64()));
    Frame(true); assert(highlightVertices() == 0);

    Load(); catalogRequested = true;
    Tick(false); assert(!pending.valid()); // Closing F8 leaves catalog requests queued for later.
    Tick(true); assert(pending.valid()); assert(pending.get().kind == Kind::Catalog);
    lastInventoryPoll = 0;
    Tick(false); assert(pending.valid()); assert(pending.get().kind == Kind::Inventory);
    Load(); Tick(false,true); assert(!pending.valid() && refreshInventory && !snapshot.Current(GetTickCount64()));
    Tick(false); assert(pending.valid()); assert(pending.get().kind == Kind::Inventory);
    Load();
    mc_panel::Queue(L"/ui/break-last","{}");
    assert(!snapshot.Current(GetTickCount64()) && refreshInventory);
    mc_panel::pending.wait(); // A bridge mutation may finish before the next rendered frame.
    ImGui::NewFrame(); mc_panel::Draw(); ImGui::Render();
    assert(!mc_panel::pending.valid() && pending.valid());
    assert(pending.get().kind == Kind::Inventory);
    assert(!snapshot.Current(GetTickCount64())); // Must read again even when Tick never saw the builder busy.
    Load();
    std::promise<Reply> unfinished;
    pending = unfinished.get_future();
    Tick(false); Frame(false); assert(pending.valid()); // A not-ready worker never blocks drawing.
    unfinished.set_value({Kind::Inventory,false,"test-offline"}); CollectReply();
    assert(!pending.valid() && snapshot.State(GetTickCount64()) == Status::Offline);
    ImGui::DestroyContext();
    std::cout << "Hotbar checks passed: 9-slot viewport layout, authoritative selection/freshness, offline rejection, "
                 "actual ImGui offscreen drawing, F8 mouse gating, async polling, catalog gating, "
                 "fast builder mutation confirmation and no mutation retry\n";
}
'''


def main():
    if not COMPILER.is_file() or not (IMGUI / "imgui.cpp").is_file():
        raise RuntimeError("Prepare the project's fixed upstream and MSYS2 UCRT64 compiler first")
    (ROOT / "build").mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="hotbar-ui-check-", dir=ROOT / "build") as directory:
        directory = Path(directory)
        source, output = directory / "check.cpp", directory / "check.exe"
        source.write_text(SOURCE, encoding="utf-8")
        subprocess.run([
            str(COMPILER), "-std=c++17", "-O1", "-static", "-Wall", "-Wextra", "-Werror",
            "-I", str(ROOT / "red-side-patches"), "-I", str(UPSTREAM), "-I", str(IMGUI),
            str(source), *[str(IMGUI / name) for name in (
                "imgui.cpp", "imgui_draw.cpp", "imgui_tables.cpp", "imgui_widgets.cpp")],
            "-lwinhttp", "-limm32", "-o", str(output),
        ], check=True)
        subprocess.run([str(output)], check=True, timeout=30)


if __name__ == "__main__":
    main()
