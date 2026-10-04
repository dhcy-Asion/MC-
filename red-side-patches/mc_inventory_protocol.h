// Bounded bridge text decoding, independent of Windows/ImGui for host checks.
#pragma once
#include <array>
#include <string>
#include <vector>
#include <cstdint>

namespace mc_inventory {
struct Item {
    std::string id, name;
    int maxCount = 0;
    bool placeSupported = false, isBlock = false;
};
struct Catalog {
    int total = 0, offset = 0, next = -1;
    std::vector<Item> items;
};
struct Slot { std::string id, name; int count = 0, maxCount = 0; };
struct Inventory { uint64_t revision = 0; int selected = 0; std::array<Slot,36> slots{}; };

inline bool Number(const std::string& text, uint64_t max, uint64_t& value) {
    if (text.empty() || text.size() > 20) return false;
    value = 0;
    for (char ch : text) {
        if (ch < '0' || ch > '9') return false;
        const unsigned digit = ch - '0';
        if (value > max / 10 || (value == max / 10 && digit > max % 10)) return false;
        value = value * 10 + digit;
    }
    return true;
}
inline bool Lines(const std::string& text, std::vector<std::vector<std::string>>& rows) {
    if (text.empty() || text.size() > 65536) return false;
    size_t start = 0;
    while (start < text.size()) {
        size_t end = text.find('\n', start);
        if (end == std::string::npos) end = text.size();
        if (end > start && text[end-1] == '\r') --end;
        if (end == start || rows.size() >= 101) return false;
        std::vector<std::string> fields;
        size_t col = start;
        while (col <= end) {
            size_t tab = text.find('\t', col);
            if (tab == std::string::npos || tab > end) tab = end;
            if (fields.size() >= 6) return false;
            fields.push_back(text.substr(col, tab-col));
            if (tab == end) break;
            col = tab+1;
        }
        rows.push_back(std::move(fields));
        size_t newline = text.find('\n', start);
        start = newline == std::string::npos ? text.size() : newline+1;
    }
    return !rows.empty();
}
inline bool Id(const std::string& value) {
    if (value.empty() || value.size() > 256) return false;
    bool colon = false;
    for (char ch : value) {
        if (ch == ':') { if (colon) return false; colon = true; }
        else if (!((ch >= 'a' && ch <= 'z') || (ch >= '0' && ch <= '9') ||
                   ch == '_' || ch == '-' || ch == '.' || ch == '/')) return false;
    }
    return colon && value.front() != ':' && value.back() != ':';
}
inline bool ParseCatalog(const std::string& text, Catalog& output) {
    std::vector<std::vector<std::string>> rows;
    if (!Lines(text, rows) || rows[0].size() != 4 || rows[0][0] != "catalog") return false;
    Catalog parsed; uint64_t total, offset, next;
    if (!Number(rows[0][1],65535,total) || !Number(rows[0][2],65535,offset) || offset > total) return false;
    parsed.total = (int)total; parsed.offset = (int)offset;
    if (rows[0][3] != "-1") {
        if (!Number(rows[0][3],65535,next) || next <= offset || next >= total) return false;
        parsed.next = (int)next;
    }
    for (size_t n = 1; n < rows.size(); ++n) {
        const auto& row = rows[n]; uint64_t maxCount;
        if (row.size() != 6 || row[0] != "item" || !Id(row[1]) || row[2].size() > 2048 ||
            !Number(row[3],999,maxCount) || !maxCount ||
            (row[4] != "0" && row[4] != "1") || (row[5] != "0" && row[5] != "1")) return false;
        for (const auto& item : parsed.items) if (item.id == row[1]) return false;
        parsed.items.push_back({row[1],row[2],(int)maxCount,row[4]=="1",row[5]=="1"});
    }
    const auto end = offset + parsed.items.size();
    if (end > total || (parsed.next != -1 && (uint64_t)parsed.next != end) ||
        (parsed.next == -1 && end != total)) return false;
    output = std::move(parsed); return true;
}
inline bool ParseInventory(const std::string& text, Inventory& output) {
    std::vector<std::vector<std::string>> rows;
    if (!Lines(text,rows) || rows.size() != 37 || rows[0].size() != 3 || rows[0][0] != "inventory") return false;
    Inventory parsed; uint64_t revision, selected;
    if (!Number(rows[0][1],INT64_MAX,revision) || !Number(rows[0][2],35,selected)) return false;
    parsed.revision = revision; parsed.selected = (int)selected;
    std::array<bool,36> seen{};
    for (size_t n=1; n<rows.size(); ++n) {
        const auto& row=rows[n]; uint64_t index,count,maxCount;
        if (row.size()!=6 || row[0]!="slot" || !Number(row[1],35,index) || seen[index] ||
            !Number(row[3],999,count) || !Number(row[4],999,maxCount) || row[5].size()>2048) return false;
        if (row[2]=="-") { if (count || maxCount || !row[5].empty()) return false; }
        else if (!Id(row[2]) || !count || !maxCount || count>maxCount) return false;
        seen[index]=true;
        parsed.slots[index]={row[2]=="-"?"":row[2],row[5],(int)count,(int)maxCount};
    }
    output=std::move(parsed); return true;
}
}
