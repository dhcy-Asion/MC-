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
#include "i18n.h"

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
mc_inventory::Inventory inventory;
mc_inventory::Catalog catalog;
bool haveInventory = false, haveCatalog = false, refreshInventory = true;
bool catalogRequested = true;
ULONGLONG lastInventoryPoll = 0;
char search[256] = {};
std::string fetchSearch, appliedSearch;
int fetchOffset = 0, cell[3] = {0,0,0};
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
void Queue(Kind kind, const std::wstring& path, std::string body = "") {
    if (pending.valid()) return;
    try {
        pending = std::async(std::launch::async, [kind, path, body=std::move(body)] { return Request(kind, path, body); });
    } catch (...) { message = "无法启动背包工作线程。请稍后刷新。"; }
}
void Mutation(const wchar_t* path, std::string body) {
    if (pending.valid() || refreshInventory) return;
    lastMutationFailed = false;
    message = "正在等待 MC 确认操作……";
    Queue(Kind::Mutation, path, std::move(body));
}
void QueueCatalog(int offset, const std::string& text) {
    fetchOffset = offset; fetchSearch = text; catalogRequested = true;
}
bool Placeable(const std::string& id) {
    return id == "minecraft:oak_log" || id == "minecraft:oak_planks" || id == "minecraft:cobblestone" ||
           id == "minecraft:dirt" || id == "minecraft:stone" || id == "minecraft:crafting_table";
}
std::string ShortName(const std::string& text) {
    size_t end = 0;
    int characters = 0;
    while (end < text.size() && characters < 4) {
        const unsigned char ch = (unsigned char)text[end];
        size_t length = ch < 0x80 ? 1 : ch < 0xE0 ? 2 : ch < 0xF0 ? 3 : 4;
        if (length > text.size() - end) break;
        end += length; ++characters;
    }
    return text.substr(0,end) + (end < text.size() ? "…" : "");
}
void CollectReply() {
    if (!pending.valid() || pending.wait_for(std::chrono::seconds(0)) != std::future_status::ready) return;
    Reply reply{Kind::Inventory, false, {}};
    try { reply = pending.get(); }
    catch (...) { message = "背包请求失败。请刷新核对库存。"; refreshInventory = true; return; }
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
            haveInventory = false; // Prevent mutations against a stale selection.
            return;
        }
        inventory = std::move(parsed); haveInventory = true;
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
        "共项，当前筛选：上一页下一页没有匹配的物品。方块：放置待接入获取一组最近操作信息原有建造与合成操作…×—");
}
}

bool Busy() { return pending.valid() || refreshInventory; }

void Draw(bool otherBusy) {
    Glyphs();
    CollectReply();
    const ULONGLONG now = GetTickCount64();
    if (!pending.valid()) {
        if (refreshInventory || now-lastInventoryPoll > 1800) Queue(Kind::Inventory, L"/ui/inventory");
        else if (catalogRequested) {
            const std::string path = "/ui/catalog?search=" + PercentEncode(fetchSearch) +
                                     "&offset=" + std::to_string(fetchOffset) + "&limit=50";
            Queue(Kind::Catalog, std::wstring(path.begin(), path.end()));
        }
    }
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
        if (ImGui::BeginTable("MCInventorySlots", 6, ImGuiTableFlags_SizingStretchSame)) {
            for (int index = 0; index < 36; ++index) {
                ImGui::TableNextColumn(); ImGui::PushID(index);
                const auto& slot = inventory.slots[index];
                const bool chosen = index == inventory.selected;
                if (chosen) {
                    ImGui::PushStyleColor(ImGuiCol_Button, ImVec4(0.24f,0.47f,0.22f,1));
                    ImGui::PushStyleColor(ImGuiCol_ButtonHovered, ImVec4(0.30f,0.57f,0.28f,1));
                }
                char count[64];
                std::snprintf(count, sizeof count, "%02d: ", index+1);
                std::string label = count + (slot.id.empty() ? std::string("空") : ShortName(slot.name));
                label += "\n" + (slot.id.empty() ? std::string("—") : std::to_string(slot.count));
                ImGui::BeginDisabled(busy);
                if (ImGui::Button(label.c_str(), ImVec2(-1,45)))
                    Mutation(L"/ui/select", "{\"slot\":" + std::to_string(index) + "}");
                ImGui::EndDisabled();
                if (chosen) ImGui::PopStyleColor(2);
                if (ImGui::IsItemHovered(ImGuiHoveredFlags_AllowWhenDisabled)) {
                    ImGui::BeginTooltip();
                    ImGui::Text("第 %d 槽%s", index+1, chosen ? "（已选中）" : "");
                    if (slot.id.empty()) ImGui::TextUnformatted("空槽位也可以选择");
                    else { ImGui::TextUnformatted(slot.name.c_str()); ImGui::TextUnformatted(slot.id.c_str());
                           ImGui::Text("数量 %d，最大堆叠 %d",slot.count,slot.maxCount); }
                    ImGui::EndTooltip();
                }
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
    } else ImGui::TextDisabled("库存尚未读取，操作暂不可用。");
    ImGui::Separator();
    ImGui::TextUnformatted("物品目录：自由领取，使用时消耗");
    ImGui::SetNextItemWidth(std::max(100.0f, ImGui::GetContentRegionAvail().x-70));
    const bool enter = ImGui::InputText("##MCItemSearch", search, sizeof search, ImGuiInputTextFlags_EnterReturnsTrue);
    ImGui::SameLine();
    ImGui::BeginDisabled(busy);
    const bool clicked = ImGui::Button("搜索");
    if ((enter || clicked) && !busy) QueueCatalog(0, search);
    ImGui::EndDisabled();
    ImGui::TextDisabled("支持名称或 minecraft:物品ID 搜索");
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
            for (const auto& item : catalog.items) {
                ImGui::PushID(item.id.c_str());
                if (ImGui::BeginTable("row",2,ImGuiTableFlags_SizingStretchProp)) {
                    ImGui::TableSetupColumn("物品",ImGuiTableColumnFlags_WidthStretch);
                    ImGui::TableSetupColumn("领取",ImGuiTableColumnFlags_WidthFixed,140);
                    ImGui::TableNextColumn();
                    ImGui::TextWrapped("%s",item.name.c_str());
                    if (ImGui::IsItemHovered()) { ImGui::BeginTooltip(); ImGui::TextUnformatted(item.id.c_str()); ImGui::EndTooltip(); }
                    if (item.isBlock && !item.placeSupported) ImGui::TextDisabled("方块：放置待接入");
                    ImGui::TableNextColumn();
                    char label[96]; std::snprintf(label,sizeof label,"获取一组（%d）",item.maxCount);
                    ImGui::BeginDisabled(busy || !haveInventory);
                    if (ImGui::Button(label,ImVec2(-1,0))) Mutation(L"/ui/grant", "{\"item\":\""+item.id+"\"}");
                    ImGui::EndDisabled(); ImGui::EndTable();
                }
                ImGui::Separator(); ImGui::PopID();
            }
        }
        ImGui::EndChild();
    }
    if (!details.empty() && ImGui::CollapsingHeader("最近操作信息")) ImGui::TextWrapped("%s",details.c_str());
}
}
