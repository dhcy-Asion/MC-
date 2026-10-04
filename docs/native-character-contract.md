# 原生角色契约：静态线索与待验证条件

2026-10-04，仅针对 EXE `1.0.0.2976`、SHA256
`57da440d72f4db974f25fef047cf84c4dadd999a88cb2a3c5af4c9bd67fde1e7`。
本页是磁盘只读反汇编的交接记录；没有执行原生请求、生成人物或登记第四身份。
RVA 是此 SHA 的定位入口，不是跨版本接口或可复用堆地址。

## 切换请求与身份命名空间

`TrocTrStartChangeFocusActorReq` RTTI 的 vtable 为 `0x5B244F8`，slot 2
handler 为 `0x298D940`。静态 ABI 为
`uint32_t* __fastcall(void* handler, uint32_t* result, const void* envelope)`，
handler 返回原结果指针；不能套通用八参数 thunk，也不能仅凭类名主动发送。

envelope `+0` 为发送者，`+0x10` 为 u16 总长度，`+0x18` 为缓冲指针。
封包头长 5，头 `+3` 的 u16 payload 长度须等于总长减 5；payload 必须恰好 5 字节，
包含 u32 CharacterInfo key 和 u8 选项。业务进入 `0x294D5B0`。
u8 非零会跳过部分可用性门槛，尚不知道正常 F1 用值；不绕过这些门槛。

**外层结果 0 只代表请求派发完成，不能证明切换成功。** handler `+0x21` 禁用时也
返回 0，业务错误另行 ACK。必须同时记录用户 F1 操作、请求 key 及实际受控身份变化。

owned lookup `0x214E7A0 → 0xE4B8080` 遍历发送者组件表 `+0x110` 中的记录：
候选 pointer array `+0x18`、u32 count `+0x20`。每条记录：

| 字段 | 静态含义／限制 |
| --- | --- |
| u16 `+0x20` | **CharacterInfo 目录行号**，不是 MercenaryInfo No；`0xFFFF` 无效 |
| i64 `+0x28` | owned Mercenary No 候选，`-1` 无效 |
| u32 `+0x50` | Actor handle 候选，不是角色 key |

getter `0x389570` 按零起始行号读取 CharacterInfo global `0x6D69A48`；目录候选
count `+8`、record-pointer array `+0x58`。记录首 u32 与切换请求 key 比较，记录
`+0xBE` 是另外的 MercenaryInfo 目录引用候选；禁止混用三个命名空间。

StatusActorComponent 的 u16 `+0x30` 同样进入这个 CharacterInfo getter。
旧快照的 0／3 因而是**行号线索**，不能直接叫角色 key。
固定 World Builder 的 `notes/characterinfo.tsv` 顺序含 key 1 Kliff、两个 Kliff
变体、key 4 Damian、Damian 变体、key 6 Oongka；仍需实际加载目录的 key／RTTI／
状态 owner 回链确认，不能靠静态表加一推导所有 key。

## 创建与保存尚未解决

World Builder 的 `TrocTrSpawnCharacterCheatReq` 产生场景 NPC／编辑器 UID。
它不提供 owned 状态、F1 名单或 MercenarySaveData 生命周期。AI ownership 切换
也不是主角控制权。生成 NPC 或修改已有三人模型都不能通过第四角色验收。

当前 SHA 的三个 cheat handler 只解析有效参数并返回 0，没有业务创建调用：
Hire `0x2A302D0`、ChangeHiredWithSummon `0x2A195E0`、Discharge `0x2A304D0`。
`FrameEventRegistMercenaryReq → 0x2C49EA0 → 0x2BACCD0` 有真实业务，但要求
ServerMercenaryClanActorComponent `+0x150` 的近期登记条件记录匹配及有效时限，
不是任意角色 ID 的通用注册 API。

MercenarySaveData vtable `0x58B3520`，ctor `0x18AE8C0` 至少初始化 `0x2E0` 字节。
字段 setter 的静态线索：mercenaryNo u64 `+0x30`（`0x18A3380`）、ownedCharacterKey
u32 `+0x38`（`0x18A38B0`）、IndexedString name `+0x40`（`0x18A3CD0`），装备和库存
是带 dirty 追踪的容器。没有验证实例、插入 ABI 或保存回读；不能裸追加 owned 指针。

## 回到 M2 时的具体步骤

1. 先重新检查 EXE SHA、进程、精确 RTTI 和稳定目录边界；旧堆地址无效。
2. 外部只读采样目录 key、Status 行号、owned No 和 Actor handle，用回链关联当前身体。
3. 需要记录请求时，先审核独立三参数被动 thunk，版本／SHA／vtable／序言全部门禁，
   最多 32 条定长记录；原函数仅调用一次、原返回值透传，不主动发送请求。
4. 对一次实际 F1 切换与回切关联控制身份；翁卡不可切时记录提示，不强行解除限制。
5. 继续定位生产角色创建、owned 保存入库和 F1 列表构建；全部验证后才开始 M3。

被动观察候选与原始反汇编留在忽略的 `vendor/research/`，尚未集成或安装。
新聊天按本页重建必要探针；不把存在本机的研究候选当作已经发布的功能。
