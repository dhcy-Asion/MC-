// Prototype controls. HTTP is off the render/game thread; the bridge owns state.
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <winhttp.h>
#include <imgui.h>
#include <future>
#include <chrono>
#include <string>
#include <cstdio>
#include "mc_panel.h"
#include "mc_inventory_ui.h"
#include "i18n.h"
#include "core.h"
namespace editor { bool IsOpen(); bool PlayMode(); }

namespace mc_panel {
namespace {
struct InternetHandle {
    HINTERNET value = nullptr;
    explicit InternetHandle(HINTERNET h) : value(h) {}
    ~InternetHandle() { if (value) WinHttpCloseHandle(value); }
};
std::future<std::string> pending;
std::string summary = "Connecting to the local Minecraft bridge...";
ULONGLONG lastPoll = 0;
int selected = 0;
int cell[3] = {0, 0, 0};
bool showWorldBuilder = false;
const char* ids[] = {"minecraft:oak_planks", "minecraft:oak_log", "minecraft:cobblestone", "minecraft:dirt", "minecraft:crafting_table"};
const char* labels[] = {"橡木木板", "橡木原木", "圆石", "泥土", "工作台"};

std::string Request(const std::wstring& path, const std::string& body) {
    InternetHandle session(WinHttpOpen(L"CrimsonMC-Prototype/0.1", WINHTTP_ACCESS_TYPE_NO_PROXY,
                                      WINHTTP_NO_PROXY_NAME, WINHTTP_NO_PROXY_BYPASS, 0));
    if (!session.value) return "Local bridge: WinHTTP initialization failed";
    WinHttpSetTimeouts(session.value, 1000, 1000, 3000, 15000);
    InternetHandle connection(WinHttpConnect(session.value, L"127.0.0.1", 8767, 0));
    if (!connection.value) return "Local bridge: connection failed";
    InternetHandle request(WinHttpOpenRequest(connection.value, body.empty()? L"GET":L"POST", path.c_str(),
        nullptr, WINHTTP_NO_REFERER, WINHTTP_DEFAULT_ACCEPT_TYPES, 0));
    if (!request.value) return "Local bridge: request creation failed";
    const wchar_t* headers = L"Content-Type: application/json\r\n";
    if (!WinHttpSendRequest(request.value, headers, (DWORD)-1, body.empty()? WINHTTP_NO_REQUEST_DATA:(LPVOID)body.data(),
        (DWORD)body.size(), (DWORD)body.size(), 0) || !WinHttpReceiveResponse(request.value, nullptr))
        return "Local bridge is not running. Start the prototype launcher.";
    DWORD status = 0, size = sizeof(status);
    WinHttpQueryHeaders(request.value, WINHTTP_QUERY_STATUS_CODE | WINHTTP_QUERY_FLAG_NUMBER,
                        WINHTTP_HEADER_NAME_BY_INDEX, &status, &size, WINHTTP_NO_HEADER_INDEX);
    std::string result;
    char buffer[4096]; DWORD read = 0;
    while (WinHttpReadData(request.value, buffer, sizeof(buffer), &read) && read) {
        if (result.size()+read > 65536) return "Bridge response too large";
        result.append(buffer, read);
    }
    if (status != 200) return "Action rejected (HTTP "+std::to_string(status)+"): "+result;
    return result;
}
void Queue(const wchar_t* path, std::string body = "") {
    if (pending.valid()) return;
    lastPoll = GetTickCount64();
    pending = std::async(std::launch::async, [p=std::wstring(path),b=std::move(body)] {return Request(p,b);});
}
std::string BlockBody() {
    char buffer[240]; std::snprintf(buffer,sizeof(buffer),"{\"block\":\"%s\",\"x\":%d,\"y\":%d,\"z\":%d}",
                                   ids[selected],cell[0],cell[1],cell[2]);
    return buffer;
}
}
bool ShowWorldBuilder() { return showWorldBuilder; }
void Draw() {
    if (pending.valid() && pending.wait_for(std::chrono::seconds(0)) == std::future_status::ready) {
        try {summary=pending.get();} catch (...) {summary="Bridge worker failed";}
        lastPoll = GetTickCount64();
    }
    if (!editor::IsOpen() || editor::PlayMode()) return;
    i18n::AddGlyphText(summary);
    i18n::AddGlyphText("真实我的世界版显示红沙世界构建器红沙场景资源；下方目录用于领取物品。");
    i18n::AddGlyphText("MC 物品控制台与建造建造操作无需合成直接添加物品获取一组真实规则蓝色方块为碰撞测试模型材质尚未接入材料橡木木板原木圆石泥土石头工作台在角色前方建立实验原点恢复放置指定拆除最后一块方块坐标相对到原型最多关闭菜单后继续红沙战斗实验背包由服务端保存与原有独立请在上方目录取得物品。");
    ImGui::SetNextWindowSize(ImVec2(460,650),ImGuiCond_FirstUseEver);
    ImGui::SetNextWindowPos(ImVec2(ImGui::GetIO().DisplaySize.x-490,65),ImGuiCond_FirstUseEver);
    if (ImGui::Begin("MC 物品控制台与建造###crimsonmc")) {
        ImGui::TextWrapped("真实《我的世界》Java 版 1.21.1；场景中的蓝色方块为碰撞测试模型，尚未接入 MC 材质。");
        ImGui::Checkbox("显示红沙世界构建器", &showWorldBuilder);
        if (showWorldBuilder) ImGui::TextWrapped("世界构建器列出红沙场景资源；下方目录用于领取 MC 物品。");
        ImGui::Separator();
        mc_inventory_ui::Draw(pending.valid());
        if (ImGui::CollapsingHeader("建造操作")) {
        if (!pending.valid() && !mc_inventory_ui::Busy() && GetTickCount64()-lastPoll>1500) Queue(L"/ui/state");
        ImGui::TextWrapped("%s",summary.c_str());
        ImGui::Separator();
        ImGui::BeginDisabled(pending.valid() || mc_inventory_ui::Busy());
        if (ImGui::Button("在角色前方建立实验原点")) Queue(L"/ui/anchor","{}");
        ImGui::SameLine();
        if (ImGui::Button("恢复方块")) Queue(L"/ui/reconnect","{}");
        ImGui::Combo("材料",&selected,labels,5);
        ImGui::InputInt3("方块坐标",cell);
        ImGui::TextWrapped("坐标相对实验原点：X/Z -16 到 16，Y 0 到 31。原型最多 128 方块。");
        if (ImGui::Button("放置指定方块")) Queue(L"/ui/place",BlockBody());
        ImGui::SameLine();
        if (ImGui::Button("拆除指定方块")) Queue(L"/ui/break",BlockBody());
        if (ImGui::Button("在角色前方放置")) Queue(L"/ui/front",BlockBody());
        ImGui::SameLine();
        if (ImGui::Button("拆除最后一块")) Queue(L"/ui/break-last","{}");
        ImGui::TextWrapped("无需合成；请在上方用“直接添加物品（控制台方式）”或“获取一组”取得物品。");
        ImGui::EndDisabled();
        }
        ImGui::TextWrapped("按 %s 关闭菜单后继续红沙战斗。实验背包由 MC 服务端保存，与红沙原有背包独立。", core::KeyName(core::g_keyToggle));
    }
    ImGui::End();
}
}
