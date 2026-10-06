// MC inventory UI. Reads and mutations run on one worker; the render thread never waits.
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <winhttp.h>
#include <imgui.h>
#include <future>
#include <chrono>
#include <string>
#include <algorithm>
#include <cstdio>
#include "mc_inventory_ui.h"
#include "mc_inventory_protocol.h"
#include "mc_hotbar_layout.h"
#include "i18n.h"
#include "core.h"
#include "overlay.h"

namespace mc_inventory_ui {
namespace {
struct InternetHandle {
    HINTERNET value;
    explicit InternetHandle(HINTERNET h) : value(h) {}
    ~InternetHandle() { if (value) WinHttpCloseHandle(value); }
    InternetHandle(const InternetHandle&) = delete;
    InternetHandle& operator=(const InternetHandle&) = delete;
};
enum class Kind { Inventory, Catalog, Mutation };
struct Reply { Kind kind; bool ok = false; std::string text; };
std::future<Reply> pending;
mc_hotbar::Snapshot snapshot;
mc_inventory::Inventory& inventory = snapshot.value;
mc_inventory::Catalog catalog;
bool haveCatalog = false, refreshInventory = true;
bool catalogRequested = true;
ULONGLONG lastInventoryPoll = 0;
char search[256] = {};
std::string fetchSearch, appliedSearch;
int fetchOffset = 0, cell[3] = {0,0,0};
// Direct addition to the MC experiment inventory, by ID or exact name.
char addId[128] = {};
int addCount = 1;
std::string message = "正在连接 MC 实验背包……";
std::string details;
bool lastMutationFailed = false;

std::string PercentEncode(const std::string& input) {
    const char digits[] = "0123456789ABCDEF";
    std::string encoded;
    for (unsigned char ch : input) {
        if ((ch >= 'a' && ch <= 'z') || (ch >= 'A' && ch <= 'Z') ||
            (ch >= '0' && ch <= '9') || ch == '-' || ch == '_' || ch == '.' || ch == '~') encoded += char(ch);
        else { encoded += '%'; encoded += digits[ch >> 4]; encoded += digits[ch & 15]; }
    }
    return encoded;
}
Reply Request(Kind kind, const std::wstring& path, const std::string& body) {
    Reply reply{kind, false, {}};
    const bool mutation = kind == Kind::Mutation;
    InternetHandle session(WinHttpOpen(L"CrimsonMC-Inventory/0.1", WINHTTP_ACCESS_TYPE_NO_PROXY,
                                      WINHTTP_NO_PROXY_NAME, WINHTTP_NO_PROXY_BYPASS, 0));
    if (!session.value) { reply.text = "网络初始化失败。"; return reply; }
    WinHttpSetTimeouts(session.value, 1000, 1000, 3000, 15000);
    InternetHandle connection(WinHttpConnect(session.value, L"127.0.0.1", 8767, 0));
    if (!connection.value) { reply.text = "无法连接本机桥接，请启动 Start Prototype。"; return reply; }
    InternetHandle request(WinHttpOpenRequest(connection.value, mutation ? L"POST" : L"GET", path.c_str(),
        nullptr, WINHTTP_NO_REFERER, WINHTTP_DEFAULT_ACCEPT_TYPES, 0));
    if (!request.value) { reply.text = "无法创建背包请求。"; return reply; }
    const wchar_t* headers = mutation ? L"Content-Type: application/json\r\n" : L"";
    if (!WinHttpSendRequest(request.value, headers, (DWORD)-1,
        mutation ? (LPVOID)body.data() : WINHTTP_NO_REQUEST_DATA,
        (DWORD)body.size(), (DWORD)body.size(), 0) || !WinHttpReceiveResponse(request.value, nullptr)) {
        reply.text = mutation ? "操作响应未确认。正在刷新库存；不会自动重复这次操作。" :
                                "未连接 MC 桥接，请运行 Start Prototype 后重试。";
        return reply;
    }
    DWORD status = 0, size = sizeof status;
    if (!WinHttpQueryHeaders(request.value, WINHTTP_QUERY_STATUS_CODE | WINHTTP_QUERY_FLAG_NUMBER,
                            WINHTTP_HEADER_NAME_BY_INDEX, &status, &size, WINHTTP_NO_HEADER_INDEX)) {
        reply.text = "无法读取操作状态。请刷新库存核对结果。"; return reply;
    }
    char bytes[4096];
    for (;;) {
        DWORD read = 0;
        if (!WinHttpReadData(request.value, bytes, sizeof bytes, &read)) {
            reply.text = "响应读取失败。请刷新库存核对结果。"; return reply;
        }
        if (!read) break;
        if (reply.text.size() + read > 65536) { reply.text = "响应超过 64 KB，已拒绝。"; return reply; }
        reply.text.append(bytes, read);
    }
    reply.ok = status == 200;
    if (!reply.ok) reply.text = "操作未完成（HTTP " + std::to_string(status) + "）：" + reply.text;
    return reply;
}
bool Queue(Kind kind, const std::wstring& path, std::string body = "") {
    if (pending.valid()) return false;
    try {
        pending = std::async(std::launch::async, [kind, path, body=std::move(body)] { return Request(kind, path, body); });
        return true;
    } catch (...) { message = "无法启动背包工作线程。请稍后刷新。"; return false; }
}
void Mutation(const wchar_t* path, std::string body) {
    if (pending.valid() || refreshInventory || !snapshot.Current(GetTickCount64())) return;
    lastMutationFailed = false;
    message = "正在等待 MC 确认操作……";
    snapshot.RequireConfirmation();
    if (!Queue(Kind::Mutation, path, std::move(body))) refreshInventory = true;
}
void QueueCatalog(int offset, const std::string& text) {
    fetchOffset = offset; fetchSearch = text; catalogRequested = true;
}
bool Placeable(const std::string& id) {
    return id == "minecraft:oak_log" || id == "minecraft:oak_planks" || id == "minecraft:cobblestone" ||
           id == "minecraft:dirt" || id == "minecraft:stone" || id == "minecraft:crafting_table";
}
ImTextureID ItemTexture(const std::string& id) {
    // IDs from MC are identifiers, never filenames supplied by a user.
    if (id.rfind("minecraft:",0) == 0 && id.size() > 10 &&
        id.find_first_not_of("abcdefghijklmnopqrstuvwxyz0123456789_",10) == std::string::npos) {
        const std::string file = core::ModDir() + "\\mc-icons\\" + id.substr(10) + ".png";
        return overlay::Thumb(file);
    }
    return 0;
}
bool IconButton(const std::string& id, int count, int slot = -1) {
    const float width = std::max(32.0f, ImGui::GetContentRegionAvail().x);
    const bool clicked = ImGui::Button("##MCItemIcon", ImVec2(width,60));
    const ImVec2 top = ImGui::GetItemRectMin(), bottom = ImGui::GetItemRectMax();
    auto* draw = ImGui::GetWindowDrawList();
    const ImTextureID texture = ItemTexture(id);
    if (texture) {
        const float side = std::min(44.0f,width-8);
        const ImVec2 center((top.x+bottom.x)*0.5f,(top.y+bottom.y)*0.5f-3);
        draw->AddImage(texture, ImVec2(center.x-side/2,center.y-side/2),
                       ImVec2(center.x+side/2,center.y+side/2));
    } else if (!id.empty()) {
        const auto size = ImGui::CalcTextSize("?");
        draw->AddText(ImVec2((top.x+bottom.x-size.x)/2,(top.y+bottom.y-size.y)/2),
                      IM_COL32(210,210,210,255),"?");
    }
    if (slot >= 0) {
        const auto label = std::to_string(slot+1);
        draw->AddText(ImVec2(top.x+3,top.y+2),IM_COL32(190,190,190,255),label.c_str());
    }
    if (count > 0) {
        const auto label = std::to_string(count);
        const auto size = ImGui::CalcTextSize(label.c_str());
        const ImVec2 position(bottom.x-size.x-4,bottom.y-size.y-2);
        draw->AddText(ImVec2(position.x+1,position.y+1),IM_COL32(0,0,0,255),label.c_str());
        draw->AddText(position,IM_COL32(255,255,255,255),label.c_str());
    }
    return clicked;
}
void IconTooltip(const std::string& id, const std::string& name, int count, int maxCount,
                 bool catalogItem, bool unsupportedBlock = false, int slot = -1, bool selected = false) {
    if (!ImGui::IsItemHovered(ImGuiHoveredFlags_AllowWhenDisabled)) return;
    ImGui::BeginTooltip();
    if (slot >= 0) ImGui::Text("第 %d 槽%s",slot+1,selected ? "（已选中）" : "");
    if (id.empty()) ImGui::TextUnformatted("空槽位也可以选择");
    else {
        ImGui::TextUnformatted(name.c_str());
        ImGui::TextDisabled("%s",id.c_str());
        if (catalogItem) ImGui::Text("点击获取一组：%d 件",maxCount);
        else ImGui::Text("数量 %d，最大堆叠 %d",count,maxCount);
        if (unsupportedBlock) ImGui::TextUnformatted("方块：放置待接入");
        ImGui::TextDisabled("图标为物品类型预览，属性外观尚未同步。");
    }
    ImGui::EndTooltip();
}
std::string JsonString(const std::string& value) {
    std::string quoted = "\"";
    for (char ch : value) {
        const unsigned char byte = (unsigned char)ch;
        if (ch == '"' || ch == '\\') { quoted += '\\'; quoted += ch; }
        else if (byte < 0x20) { char escape[8]; std::snprintf(escape, sizeof escape, "\\u%04X", byte); quoted += escape; }
        else quoted += ch;
    }
    return quoted + "\"";
}
void CollectReply() {
    if (!pending.valid() || pending.wait_for(std::chrono::seconds(0)) != std::future_status::ready) return;
    Reply reply{Kind::Inventory, false, {}};
    try { reply = pending.get(); }
    catch (...) {
        message = "背包请求失败。请刷新核对库存。";
        snapshot.Fail(); refreshInventory = true; return;
    }
    if (reply.kind == Kind::Mutation) {
        details = reply.text;
        i18n::AddGlyphText(details);
        lastMutationFailed = !reply.ok;
        message = reply.ok ? "MC 已回应，正在读取最新库存。" : reply.text;
        refreshInventory = true;
        return;
    }
    if (reply.kind == Kind::Inventory) {
        lastInventoryPoll = GetTickCount64();
        refreshInventory = false;
        mc_inventory::Inventory parsed;
        if (!reply.ok || !mc_inventory::ParseInventory(reply.text, parsed)) {
            message = reply.ok ? "背包响应格式错误，保留上次显示；请刷新核对。" : reply.text;
            snapshot.Fail(); // Keep the last snapshot visibly stale; never allow mutations against it.
            return;
        }
        snapshot.Accept(std::move(parsed), lastInventoryPoll);
        if (!haveCatalog) catalogRequested = true;
        for (const auto& slot : inventory.slots) i18n::AddGlyphText(slot.name);
        if (!lastMutationFailed) message = "库存已更新。";
        return;
    }
    catalogRequested = false;
    mc_inventory::Catalog parsed;
    if (!reply.ok || !mc_inventory::ParseCatalog(reply.text, parsed)) {
        message = reply.ok ? "物品目录格式错误，请重新搜索。" : reply.text;
        haveCatalog = false; return;
    }
    catalog = std::move(parsed); haveCatalog = true; appliedSearch = fetchSearch;
    for (const auto& item : catalog.items) i18n::AddGlyphText(item.name);
}
void Glyphs() {
    static bool registered = false;
    if (registered) return;
    registered = true;
    i18n::AddGlyphText("MC 实验背包：当前为库存槽位选择，原生手持模型尚未接入。正在等待本机服务……刷新库存"
        "当前选中：第槽空槽位（已选中）空槽位也可以选择数量最大堆叠"
        "消耗一个非方块物品（功能待接入）方块使用下面的放置操作，其他用途逐步接入。"
        "放置选中方块（指定坐标／旧前方方式）目前可放置原木、木板、圆石、泥土、石头和工作台。"
        "需要先建立实验原点；放置方式尚非准星。相对方块坐标到一格约一米，最多方块。"
        "库存尚未读取，操作暂不可用。物品目录：自由领取，使用时消耗搜索支持名称或物品ID搜索"
        "共项，当前筛选：上一页下一页没有匹配的物品。方块：放置待接入获取一组最近操作信息建造操作…×—"
        "直接添加物品（控制台方式）输入物品或中文／英文名称与数量，直接放入背包。无需合成。"
        "添加到背包方块、工具与食物均可添加。"
        "物品ID名称钻石剑支持中文名搜索重名物品请使用无需合成。"
        "点击图标获取一组，悬停查看中文名称。图标为物品类型预览，属性外观尚未同步。"
        "点击获取一组：件图标未安装或正在加载时显示问号。"
        "MC 实验快捷栏已连接正在连接离线库存过期正在核对库存显示上次库存"
        "操作已停用尚未确认库存按打开菜单后点击选择不在快捷栏当前服务端选择第槽"
        "这是MC实验背包的前九格，红沙原角色界面保留。最近一次确认秒前库存确认中");
}
}

bool Busy() { return pending.valid() || refreshInventory; }

void RequireConfirmation() {
    snapshot.RequireConfirmation();
    refreshInventory = true;
}

void Tick(bool pollCatalog, bool otherBusy) {
    Glyphs();
    CollectReply();
    const ULONGLONG now = GetTickCount64();
    // Builder actions may also change inventory. Confirm again before enabling either UI.
    if (otherBusy) {
        RequireConfirmation();
        return;
    }
    if (!pending.valid()) {
        if (refreshInventory || now-lastInventoryPoll > 1800) {
            if (!Queue(Kind::Inventory, L"/ui/inventory")) {
                snapshot.Fail(); refreshInventory = false; lastInventoryPoll = now;
            }
        } else if (pollCatalog && catalogRequested) {
            const std::string path = "/ui/catalog?search=" + PercentEncode(fetchSearch) +
                                     "&offset=" + std::to_string(fetchOffset) + "&limit=50";
            Queue(Kind::Catalog, std::wstring(path.begin(), path.end()));
        }
    }
}

void DrawHotbar(bool interactive, bool otherBusy) {
    Glyphs();
    const ImVec2 display = ImGui::GetIO().DisplaySize;
    const auto layout = mc_hotbar::Measure(display.x, display.y);
    if (!layout.visible) return;
    const ULONGLONG now = GetTickCount64();
    const auto state = snapshot.State(now);
    const bool current = state == mc_hotbar::Status::Current;
    const bool canSelect = interactive && current && !Busy() && !otherBusy;
    std::string label = "MC 实验快捷栏 · ";
    switch (state) {
    case mc_hotbar::Status::Connecting: label += "正在连接…"; break;
    case mc_hotbar::Status::Offline: label += snapshot.known ? "离线：显示上次库存" : "离线：尚未确认库存"; break;
    case mc_hotbar::Status::Confirming: label += "正在核对库存…"; break;
    case mc_hotbar::Status::Stale: label += "库存过期：显示上次库存"; break;
    case mc_hotbar::Status::Current:
        label += "第 " + std::to_string(inventory.selected + 1) + " 槽";
        if (inventory.selected >= mc_hotbar::kSlots) label += "（不在快捷栏）";
        break;
    }
    i18n::AddGlyphText(label);
    ImGuiWindowFlags flags = ImGuiWindowFlags_NoDecoration | ImGuiWindowFlags_NoMove |
        ImGuiWindowFlags_NoSavedSettings | ImGuiWindowFlags_NoScrollbar | ImGuiWindowFlags_NoScrollWithMouse |
        ImGuiWindowFlags_NoNav | ImGuiWindowFlags_NoFocusOnAppearing | ImGuiWindowFlags_NoBringToFrontOnFocus;
    if (!interactive) flags |= ImGuiWindowFlags_NoInputs;
    ImGui::SetNextWindowPos(ImVec2(layout.x, layout.y), ImGuiCond_Always);
    ImGui::SetNextWindowSize(ImVec2(layout.width, layout.height), ImGuiCond_Always);
    ImGui::SetNextWindowBgAlpha(0);
    ImGui::PushStyleVar(ImGuiStyleVar_WindowPadding, ImVec2(0,0));
    ImGui::PushStyleVar(ImGuiStyleVar_WindowBorderSize, 0);
    if (ImGui::Begin("MC Hotbar###crimsonmc-hotbar", nullptr, flags)) {
        auto* draw = ImGui::GetWindowDrawList();
        const ImVec2 origin = ImGui::GetWindowPos();
        const ImVec2 frame(origin.x, origin.y + layout.labelHeight);
        const ImVec2 end(frame.x + layout.width, origin.y + layout.height);
        const auto textSize = ImGui::CalcTextSize(label.c_str());
        draw->PushClipRect(origin, ImVec2(origin.x + layout.width, frame.y), true);
        const ImVec2 textPos(origin.x + std::max(2.0f, (layout.width - textSize.x) / 2), origin.y + 2);
        draw->AddText(ImVec2(textPos.x + 1,textPos.y + 1),IM_COL32(0,0,0,230),label.c_str());
        draw->AddText(textPos,current ? IM_COL32(235,240,230,255) : IM_COL32(245,193,100,255),label.c_str());
        draw->PopClipRect();
        draw->AddRectFilled(frame,end,IM_COL32(18,20,17,235));
        draw->AddRect(frame,end,IM_COL32(115,119,107,255),0,0,2);
        const int highlighted = snapshot.Highlight(now);
        for (int index = 0; index < mc_hotbar::kSlots; ++index) {
            const ImVec2 top(frame.x + layout.border + index * layout.cell, frame.y + layout.border);
            const ImVec2 bottom(top.x + layout.cell, top.y + layout.cell);
            ImGui::SetCursorScreenPos(top);
            ImGui::PushID(index);
            ImGui::BeginDisabled(!canSelect);
            const bool clicked = ImGui::InvisibleButton("##MCHotbarSlot",ImVec2(layout.cell,layout.cell));
            ImGui::EndDisabled();
            const bool hovered = interactive && ImGui::IsItemHovered(ImGuiHoveredFlags_AllowWhenDisabled);
            draw->AddRectFilled(ImVec2(top.x + 2,top.y + 2),ImVec2(bottom.x - 2,bottom.y - 2),
                                hovered ? IM_COL32(86,92,76,230) : IM_COL32(49,54,45,230));
            draw->AddRect(ImVec2(top.x + 1,top.y + 1),ImVec2(bottom.x - 1,bottom.y - 1),IM_COL32(10,13,9,255),0,0,2);
            draw->AddLine(ImVec2(top.x + 3,top.y + 3),ImVec2(bottom.x - 3,top.y + 3),IM_COL32(112,117,104,255),1);
            draw->AddLine(ImVec2(top.x + 3,top.y + 3),ImVec2(top.x + 3,bottom.y - 3),IM_COL32(112,117,104,255),1);
            const auto& slot = inventory.slots[index];
            if (snapshot.known) {
                const ImTextureID texture = ItemTexture(slot.id);
                const float side = std::max(4.0f,layout.cell - 12);
                const ImVec2 center((top.x + bottom.x)/2,(top.y + bottom.y)/2);
                if (texture) draw->AddImage(texture,ImVec2(center.x-side/2,center.y-side/2),
                                            ImVec2(center.x+side/2,center.y+side/2),ImVec2(0,0),ImVec2(1,1),
                                            current ? IM_COL32_WHITE : IM_COL32(170,170,170,190));
                else if (!slot.id.empty()) {
                    const auto size = ImGui::CalcTextSize("?");
                    draw->AddText(ImVec2(center.x-size.x/2,center.y-size.y/2),IM_COL32(205,205,195,255),"?");
                }
                if (slot.count > 0) {
                    const std::string count = std::to_string(slot.count);
                    const auto size = ImGui::CalcTextSize(count.c_str());
                    const ImVec2 position(bottom.x-size.x-4,bottom.y-size.y-2);
                    draw->AddText(ImVec2(position.x+1,position.y+1),IM_COL32(0,0,0,255),count.c_str());
                    draw->AddText(position,current ? IM_COL32_WHITE : IM_COL32(190,190,180,255),count.c_str());
                }
            } else {
                const auto size = ImGui::CalcTextSize("?");
                draw->AddText(ImVec2((top.x+bottom.x-size.x)/2,(top.y+bottom.y-size.y)/2),IM_COL32(155,155,145,255),"?");
            }
            if (index == highlighted) {
                draw->AddRect(ImVec2(top.x,top.y),bottom,IM_COL32(242,248,219,255),0,0,3);
                draw->AddRect(ImVec2(top.x+4,top.y+4),ImVec2(bottom.x-4,bottom.y-4),IM_COL32(162,176,131,255),0,0,1);
            }
            if (clicked && canSelect) Mutation(L"/ui/select","{\"slot\":" + std::to_string(index) + "}");
            if (hovered) {
                ImGui::BeginTooltip();
                ImGui::Text("第 %d 槽%s",index+1,index == highlighted ? "（已选中）" : "");
                if (!snapshot.known) ImGui::TextUnformatted("尚未确认库存，操作已停用。");
                else {
                    if (slot.id.empty()) ImGui::TextUnformatted("空槽位");
                    else { ImGui::TextUnformatted(slot.name.c_str()); ImGui::TextDisabled("%s",slot.id.c_str());
                           ImGui::Text("数量 %d，最大堆叠 %d",slot.count,slot.maxCount); }
                    if (!current) ImGui::TextUnformatted("显示上次库存；操作已停用，等待重新确认。");
                    else if (Busy() || otherBusy) ImGui::TextUnformatted("正在等待本机服务……");
                    else ImGui::TextUnformatted("点击选择此槽位。");
                    ImGui::TextDisabled("图标为物品类型预览，属性外观尚未同步。");
                }
                ImGui::EndTooltip();
            }
            ImGui::PopID();
        }
    }
    ImGui::End();
    ImGui::PopStyleVar(2);
}

void Draw(bool otherBusy) {
    const bool haveInventory = snapshot.Current(GetTickCount64());
    const bool busy = Busy() || otherBusy;
    i18n::AddGlyphText(message);
    ImGui::TextWrapped("MC 实验背包：当前为库存槽位选择，原生手持模型尚未接入。");
    ImGui::TextWrapped("%s", message.c_str());
    if (pending.valid()) ImGui::TextDisabled("正在等待本机服务……");
    ImGui::BeginDisabled(busy);
    if (ImGui::Button("刷新库存")) { lastMutationFailed = false; refreshInventory = true; }
    ImGui::EndDisabled();
    ImGui::Separator();

    if (haveInventory) {
        const auto& held = inventory.slots[inventory.selected];
        ImGui::Text("当前选中：第 %d 槽", inventory.selected+1);
        if (held.id.empty()) ImGui::TextDisabled("空槽位");
        else ImGui::TextWrapped("%s × %d / %d", held.name.c_str(), held.count, held.maxCount);
        const int columns = std::clamp((int)(ImGui::GetContentRegionAvail().x / 64.0f), 1, 6);
        if (ImGui::BeginTable("MCInventorySlots", columns, ImGuiTableFlags_SizingStretchSame)) {
            for (int index = 0; index < 36; ++index) {
                ImGui::TableNextColumn(); ImGui::PushID(index);
                const auto& slot = inventory.slots[index];
                const bool chosen = index == inventory.selected;
                if (chosen) {
                    ImGui::PushStyleColor(ImGuiCol_Button, ImVec4(0.24f,0.47f,0.22f,1));
                    ImGui::PushStyleColor(ImGuiCol_ButtonHovered, ImVec4(0.30f,0.57f,0.28f,1));
                }
                ImGui::BeginDisabled(busy);
                if (IconButton(slot.id,slot.count,index))
                    Mutation(L"/ui/select", "{\"slot\":" + std::to_string(index) + "}");
                ImGui::EndDisabled();
                if (chosen) ImGui::PopStyleColor(2);
                IconTooltip(slot.id,slot.name,slot.count,slot.maxCount,false,false,index,chosen);
                ImGui::PopID();
            }
            ImGui::EndTable();
        }
        ImGui::BeginDisabled(busy || held.id.empty());
        if (ImGui::Button("消耗一个非方块物品（功能待接入）")) Mutation(L"/ui/consume", "{}");
        ImGui::EndDisabled();
        ImGui::TextDisabled("方块使用下面的放置操作，其他用途逐步接入。");
        if (ImGui::CollapsingHeader("放置选中方块（指定坐标／旧前方方式）")) {
            ImGui::TextWrapped("目前可放置原木、木板、圆石、泥土、石头和工作台。需要先建立实验原点；放置方式尚非准星。");
            ImGui::InputInt3("相对方块坐标", cell);
            ImGui::TextWrapped("X/Z -16 到 16，Y 0 到 31；一格约一米，最多 128 方块。");
            ImGui::BeginDisabled(busy || !Placeable(held.id));
            if (ImGui::Button("放置选中方块")) {
                char body[160];
                std::snprintf(body,sizeof body,"{\"x\":%d,\"y\":%d,\"z\":%d}",cell[0],cell[1],cell[2]);
                Mutation(L"/ui/place-selected", body);
            }
            ImGui::SameLine();
            if (ImGui::Button("前方放置（旧方式）")) Mutation(L"/ui/front-selected", "{}");
            ImGui::EndDisabled();
        }
        if (ImGui::CollapsingHeader("直接添加物品（控制台方式）")) {
            ImGui::TextWrapped("输入物品 ID 或中文／英文名称与数量，直接放入背包。重名物品请使用 ID。无需合成。");
            ImGui::SetNextItemWidth(std::max(120.0f, ImGui::GetContentRegionAvail().x-90));
            ImGui::InputTextWithHint("##MCAddItem", "minecraft:diamond_sword 或 钻石剑", addId, sizeof addId);
            ImGui::SetNextItemWidth(90);
            ImGui::InputInt("数量", &addCount);
            if (addCount < 1) addCount = 1;
            if (addCount > 6400) addCount = 6400;
            ImGui::BeginDisabled(busy || addId[0] == '\0');
            if (ImGui::Button("添加到背包")) {
                const std::string body = "{\"item\":" + JsonString(addId) + ",\"count\":" +
                    std::to_string(addCount) + "}";
                Mutation(L"/ui/add-item", body);
            }
            ImGui::EndDisabled();
            ImGui::SameLine();
            ImGui::TextDisabled("方块、工具与食物均可添加。");
        }
    } else ImGui::TextDisabled("库存尚未读取，操作暂不可用。");
    ImGui::Separator();
    ImGui::TextUnformatted("物品目录：自由领取，使用时消耗");
    ImGui::TextWrapped("点击图标获取一组，悬停查看中文名称。图标未安装或正在加载时显示问号。");
    ImGui::SetNextItemWidth(std::max(100.0f, ImGui::GetContentRegionAvail().x-70));
    const bool enter = ImGui::InputText("##MCItemSearch", search, sizeof search, ImGuiInputTextFlags_EnterReturnsTrue);
    ImGui::SameLine();
    ImGui::BeginDisabled(busy);
    const bool clicked = ImGui::Button("搜索");
    if ((enter || clicked) && !busy) QueueCatalog(0, search);
    ImGui::EndDisabled();
    ImGui::TextDisabled("支持中文名称或 minecraft:物品ID 搜索");
    if (haveCatalog) {
        ImGui::Text("共 %d 项，当前 %d—%d", catalog.total, catalog.total ? catalog.offset+1 : 0,
                    catalog.offset+(int)catalog.items.size());
        if (!appliedSearch.empty()) ImGui::TextWrapped("筛选：%s",appliedSearch.c_str());
        ImGui::BeginDisabled(busy || catalog.offset == 0);
        if (ImGui::Button("上一页")) QueueCatalog(std::max(0,catalog.offset-50),appliedSearch);
        ImGui::EndDisabled(); ImGui::SameLine();
        ImGui::BeginDisabled(busy || catalog.next < 0);
        if (ImGui::Button("下一页")) QueueCatalog(catalog.next,appliedSearch);
        ImGui::EndDisabled();
        if (ImGui::BeginChild("MCItemCatalog",ImVec2(0,230),true)) {
            if (catalog.items.empty()) ImGui::TextUnformatted("没有匹配的物品。");
            const int columns = std::clamp((int)(ImGui::GetContentRegionAvail().x/64.0f),1,8);
            if (ImGui::BeginTable("MCItemIcons",columns,ImGuiTableFlags_SizingStretchSame)) {
                for (const auto& item : catalog.items) {
                    ImGui::TableNextColumn();
                    ImGui::PushID(item.id.c_str());
                    ImGui::BeginDisabled(busy || !haveInventory);
                    if (IconButton(item.id,item.maxCount))
                        Mutation(L"/ui/grant", "{\"item\":"+JsonString(item.id)+"}");
                    ImGui::EndDisabled();
                    IconTooltip(item.id,item.name,0,item.maxCount,true,item.isBlock && !item.placeSupported);
                    ImGui::PopID();
                }
                ImGui::EndTable();
            }
        }
        ImGui::EndChild();
    }
    if (!details.empty() && ImGui::CollapsingHeader("最近操作信息")) ImGui::TextWrapped("%s",details.c_str());
}
}
