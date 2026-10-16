# Steve 动画消费入口：固定 EXE 静态证据（2026-10-16）

本轮把已知 PAA 路径推进到动画资源请求入口的静态候选，供后续原生采集审阅。
已经建立两种 FromAction 异步 task 的磁盘 RTTI 链、一个 task 方法中的三个路径循环、
`0x2e91250` 的六参数使用和路径二跳解引用。尚未证明受控 actor 归属、选中的 clip、
播放时刻、混合权重或 MC 动作应用。资源请求和异步加载任务均不能替代这些验收。

本文件只整理已有报告和源码；编写时没有重新运行静态研究、读取游戏进程或扩展二进制范围。
不记录安装或实机结果。前置资源路径证据见 [动作路由记录](steve-motion-routing-20261016.md)。

## 固定来源与摘要

四份报告固定同一磁盘 `CrimsonDesert.exe`，SHA256 为
`57da440d72f4db974f25fef047cf84c4dadd999a88cb2a3c5af4c9bd67fde1e7`，
首选 ImageBase 为 `0x140000000`。下文均使用 RVA，区间均为半开区间；不把它们当作可跨会话复用的进程地址。

| 报告 | 报告文件 SHA256 | 生成脚本 SHA256 |
| --- | --- | --- |
| [consumer-anchors.json](../build/steve-motion-consumer-20261016/consumer-anchors.json) | `a9a5d16340beae629a7e27d185800fdcf1e0d65930956549ae9b65b17aed4903` | `4b5ce227b19657b37f2b19c5e2f788eca16e21ba2cbbb5239fcefdd900908781` |
| [motion-types.json](../build/steve-motion-consumer-20261016/motion-types.json) | `3984538970bccbe5e653622e2bff4f1b38aeaa3d4d77bddbfdf7061bf72c3933` | `e9575ed9059e14fde2ea58f1575aaa82df3c88fbc888ce8c8d9a9c39b34a7295` |
| [consumer-callee.json](../build/steve-motion-consumer-20261016/consumer-callee.json) | `04e61bc08d38a7c641265986d4db67faa6811d50842a2fa8bbfd2f4e3c375aed` | `c4dbb7f88a1967bd1c78436fd22b354720261d9342dfdb059fd12aa2b1dd51f6` |
| [consumer-children.json](../build/steve-motion-consumer-20261016/consumer-children.json) | `50a453bc87aadd07e0bdecc9bb22961d930d14cf36c1d7ba10b688a55b241c8a` | `908f6c854dc280c96c72094c3a7000e57f0290a7f4f1fb11f0b2ac72b836f44e` |

同目录四个 `.py` 是这些报告的生成入口。它们只读固定 EXE，拒绝覆盖报告，结束时回读来源。
anchors 报告记录 Capstone `5.0.7`，来源为项目已有
`vendor/research/native-f1/packages/capstone/__init__.py`；该记录是版本和加载路径证据，未记录 Capstone 模块文件摘要。
所有报告均声明 `nativeCalls=false`、`processOpened=false`；callee/children 仍为
`runtimeAbiVerified=false`、`actualClipSelectionVerified=false`。

## 字符串扫描能证明什么

[consumer-anchors.py](../build/steve-motion-consumer-20261016/consumer-anchors.py)
只查三个 ASCII 字面量：`.paac`、`.paa` 和固定 PHM idle PAA 完整路径。
每字面量最多 32 个命中、最多 12 个 `.pdata` 片段、每片段最多 64 KiB；
字符串上下文每侧最多 1,024 字节。代码引用只从可执行 section 的常见 RIP-relative MOV/LEA
字节形状生成候选，再用完整片段反汇编核对指令边界。

- `.paac` 为 0 个 ASCII 命中。这不能证明没有 PAAC 消费逻辑：未查 UTF-16、字符串表间接引用、构造出的路径或其他表示。
- `.paa` 为 13 个原始子串命中，其中 7 个在该字面量后立即 NUL 终止，9 个处于可打印 NUL 字符串内。
  这些集合不能等同 13 条 PAA 路径；结果包括格式字符串、`.paasmt` 后缀内的子串和非可打印区域。
- 只有整个 NUL 字符串等于目标时才建立锚点。独立 `.paa` 锚点在 `0x571c190`，
  固定 idle 完整路径在 `0x55cdfe0`。最终为 6 个经指令边界确认的引用、4 个完整解码片段，未触发片段上限。
- 6 个引用分别为 `0x12be96`、`0x12becd` → idle；
  `0x260cd7a`、`0x2cca2ac`、`0x2e8ebe0`、`0x2e8ec57` → `.paa`。
  这 4 个片段没有命中脚本固定的三个既有 ResourceLoader/PathNormalize 直接调用目标；
  不能由此排除间接或更深层调用。

`0x2cc9ff0` 片段在 `0x2cca2b3` 起逐字比较末尾 `.paa`，并在
`0x2cca34a`、`0x2ccab4e` 直接调用 `0x2e91250`。callee 脚本独立核对这两个 call 的目标，
才将研究范围推进到该入口；不是从名字相似推断调用关系。

## 两种 task 的磁盘 RTTI 链

motion-types 仅列出 192 个名称候选，预算 256，原报告明确没有验证 TypeDescriptor 或活实例。
consumer-callee 随后只对以下两个精确修饰名验证 TypeDescriptor、COL、类层次、基类名和 vtable 引用。

| 项目 | AnimationSetFromActionAsyncLoadingTask | AnimationSetGroupFromActionAsyncLoadingTask |
| --- | --- | --- |
| 精确修饰名 | `.?AVAnimationSetFromActionAsyncLoadingTask@pa@@` | `.?AVAnimationSetGroupFromActionAsyncLoadingTask@pa@@` |
| 名称 RVA | `0x6aa5150` | `0x6aa5390` |
| TypeDescriptor RVA | `0x6aa5140` | `0x6aa5380` |
| COL RVA | `0x5da7da0` | `0x5da7dc8` |
| COL offset / cdOffset | `0 / 0` | `0 / 0` |
| ClassHierarchy RVA | `0x5da78f8` | `0x5da7970` |
| vtable RVA | `0x557dd80` | `0x557dd30` |
| slot 0..7 的代码 RVA | `46a0d0, 1289fd0, 128a090, 3600c0, 359b50, 4697f0, 466120, 466120` | `46a7d0, 46a270, 128a090, 3600c0, 359b50, 46a350, 46a660, 466120` |

两条有序基类链分别为“精确 task 自身 → `.?AVIContainerManagedResourceTask@pa@@`
→ `.?AVOwnedByTask@pa@@`”。脚本校验 COL signature=1、self RVA 回链、TypeDescriptor 指向、
hierarchy signature=0 及第一个基类的精确名称，再从对齐的 COL 绝对地址引用取 vtable；最多读前 8 个代码槽。
这确认的是固定磁盘映像中的链，不能证明某活对象就是这两个 task，也没有建立到受控 actor 的 owner 回链。

FromAction 的 slot 5 为 `0x4697f0`。Group 的 slot 5 为 `0x46a350`，其中
`0x46a46d` 引用 `AnimationSetFromActionAsyncLoadingTask` 名称，`0x46a4e7` 调用 `0x1289e00`；
该调用的构造语义未在当前子报告继续展开。

## 完整 `.pdata` 片段边界

下列是报告实际读完并解码的整条 `.pdata` 区间及其原始代码字节摘要。
**完整 unwind 片段不自动等于完整逻辑函数**，也不证明间接跳转目标、异常路径或更远调用已全部解释。

| 来源 / 用途 | RVA 半开区间 | 字节 | SHA256 |
| --- | --- | ---: | --- |
| anchors：idle 引用 | `[0x12be20,0x12bf4c)` | 300 | `a35cb2cdad920e1ba7f552a19d41f7ab3498c067af3b6733794d7cf5859b4f83` |
| anchors：`.paa` 引用 | `[0x260cca0,0x260cf1d)` | 637 | `67e3347062b4a0df98adfda5c1cd6ce44cf533222a2055cc1a93a46378f9b1a0` |
| anchors：入口直接调用方 | `[0x2cc9ff0,0x2ccb2eb)` | 4859 | `2aa46f5b30dc833c65718907dd96ea12f222bbc910080a3f87543cd59890ba3f` |
| anchors：`.paa` 引用 | `[0x2e8ea80,0x2e8ecfd)` | 637 | `57fc407f451aae372b6376a31767566a4c28a0ae132760b2aab1b006345be61a` |
| callee：请求入口 | `[0x2e91250,0x2e913e4)` | 404 | `145d8b39b66cf8e14ba2be86ccf5d37441e39379c4d554443f35e772a7524197` |
| callee：FromAction slot 0 | `[0x46a0d0,0x46a168)` | 152 | `4aa6435eeb4fe713254d6bc0d0323a7b89636802e44d76c07d8fcb95bc6dafdd` |
| callee：FromAction slot 1 | `[0x1289fd0,0x128a08c)` | 188 | `08e37417e801dfba169df6b7560675cd6de2c6b1e8e7249ab1bd1e1ac11ecfcc` |
| callee：FromAction slot 5 | `[0x4697f0,0x46a0c1)` | 2257 | `02425ecf9d7395af2aa8c1b852d5b219948b13bbf18da343c785e75899f3832f` |
| callee：Group slot 0 | `[0x46a7d0,0x46a868)` | 152 | `8f41abf606dbcdb948d83e9d6fd7c4c2cc6f0a2591db8f4d36dc54404653a423` |
| callee：Group slot 1 | `[0x46a270,0x46a349)` | 217 | `cf388469bc14f33386a9d4f6e6d3cf2368d1012372217883686f976d98fa302d` |
| callee：Group slot 5 | `[0x46a350,0x46a65f)` | 783 | `b62288f9e88cd0495e9c5a1e6c9f74e03305d546d07dcd4c4283f8368d89a0cc` |
| callee：Group slot 6 | `[0x46a660,0x46a6bf)` | 95 | `7a4ca32ba7ddf08152821c3876e015d6d93ae982b39758c28df9140e5138dd02` |
| children：`0x2e912da` 的目标 | `[0x2e630b0,0x2e63281)` | 465 | `bf12c820d90a1e5e283367423e2bb1833ccd85e339ae1aeb592c0f3f024a83f9` |
| children：路径二跳 | `[0x2e63b70,0x2e63c85)` | 277 | `28f86904c6d30df686e997070dc07e2c7228885c658d25364ac86df1f060475c` |
| children：异步请求后继 | `[0x2e913f0,0x2e91de1)` | 2545 | `d47ff0391f69c4dcb59424094da8341b78200eca8e40fcfd96e4fef5a3812c58` |
| children：输出相关后继 | `[0x2e92cf0,0x2e92eca)` | 474 | `73593cd38e3c292677b960ac938ee312e5d18157dd1746aa13293aab96d3a1a1` |
| children：第一循环包装层 | `[0x2cc9ee0,0x2cc9fd9)` | 249 | `9b48e8ed6ccb2bddc9c9d5cab03d718e26837ad3ab9d8da6b1d6033e386b845c` |

槽目标 `0x128a090`、`0x3600c0`、`0x359b50`、`0x466120` 没有与入口完全相等的 `.pdata` 记录，
报告停止解码，没有猜测叶函数边界。anchors 另外记录四段 unwind RVA，依次为
`0x61e2754`、`0x64c6320`、`0x658ca90`、`0x64c6320`；callee/children 未在 JSON 中保存 unwind RVA，不能补造。

## FromAction 的三个循环

`0x4697f0` 保存入口 RCX 到 R13，取 `[task+0x10]` 到 R12；
随后取 `table=QWORD(task+0x40)`、`entryBase=QWORD(table+0x30)`，
得到 `R15=QWORD(entryBase+16*u32(task+0x48)+8)`。
这些是该方法实际访问的偏移，不为 R12/R15 命名 actor、clip 或状态机对象。

| 循环 | 计数与路径来源 | 已确认出口 |
| --- | --- | --- |
| 第一组，`0x469890` 回边至 `0x469b48` | task `+0x4c` 的 u16 上限；R15 `+0x48` 的 u32 数量，`+0x40` 的 u32 偏移表，`+0x38` 的字节基址 | `0x469b15 → 0x2cc9ee0`；包装层 `0x2cc9f28 → 0x2e91250`，入口看到的直接返回 RVA 为 `0x2cc9f2d` |
| 第二组，`0x469b60` 回边至 `0x469ea2` | task `+0x4e`；R15 数量 `+0x60`、偏移表 `+0x58`、字节基址 `+0x50` | `0x469e10 → 0x2e91250`，直接返回 RVA `0x469e15` |
| 第三组，`0x469ec0` 回边至 `0x46a089` | task `+0x50`；R15 数量 `+0xa8`、偏移表 `+0xa0`、字节基址 `+0x98` | `0x469f6e` 调用虚表 `+0x250`，当前未解析该实际目标 |

每组均有源数量检查和空串检查。前两组存在路径复制、`0x1328050` 调用及对
`character/motion` 常量的前缀比较／拼接分支；它们不保证所有输入始终都被加前缀。
第三组不能仅凭邻近位置或 task 名称被命名为 motionblending 的确定消费路径。
同样，观察到包装层返回地址 `0x2cc9f2d` 只确认直接调用者，不能排除该包装层还有其他上游。

固定常量字节为：`0x557cd68 = "paa"`、`0x557cd70 = "motionblending"`、
`0x5578e28 = "character/motion"`。常量存在不证明当前 actor 使用了某配置。

## `0x2e91250` 的六参数与路径二跳

以下是静态指令支持的观测用传参形状，尚未取得游戏中 ABI 验证：

```cpp
void* (__fastcall*)(void* context, void** output, void* pathObject,
                   uint8_t request4, uint8_t request5, uint8_t request6);
```

| 参数 | 静态证据 |
| --- | --- |
| 1：RCX | `0x2e91271` 保存到 R14；所见调用者从全局链的 `+0x1018` 取得此参数，不能当作 actor 指针 |
| 2：RDX | `0x2e9126e` 保存到 RDI；`0x2e9131e` 清零 `[RDI]`；`0x2e913cb` 将 RDI 返回到 RAX。它是输出地址，返回值不能被替换为输出内容 |
| 3：R8 | `0x2e9126b` 保存到 RSI；`0x2e91313` 转为 RDX，`0x2e91319` 调用 `0x2e63b70` |
| 4：R9B | `0x2e91267` 用 `movzx` 保存到 EBP；`0x2e91380` 取低字节继续传递 |
| 5：入口栈 `+0x28` | 三次 push 与 `sub rsp,0x50` 后，对应当前栈 `+0x90`；`0x2e91377` 按 byte 零扩展读取 |
| 6：入口栈 `+0x30` | 对应当前栈 `+0x98`；`0x2e9136b` 按 byte 零扩展读取 |

后三个参数保留为不解释含义的 unsigned byte，不能收窄成布尔值或擅自赋予“播放／同步”语义。
第二循环在调用前传 `0,0,0`；第一循环令包装层 R9B=1，包装层把第 4 参数置 0、
第 5 参数取原 R9B、第 6 参数取其非零测试结果。另两个静态调用点 `0x2cca34a/0x2ccab4e`
将第 5/6 参数置 1，第 4 参数来自调用者的一个 byte。不同值不能凭此解释动作选择。

路径二跳发生在已完整解码的 `0x2e63b70`：入口 RDX 保存到 RDI；
`0x2e63bee` 执行 `RCX=[RDI]`，`0x2e63bf9` 执行 `RCX=[RCX]`，
随后 `0x2e63bfc` 将该指针交给 `0x1422f90`。因此当前最小路径观测候选是
`pathObject → QWORD → char*`，不是把 R8 本身当字符串。后续局部字符串处理和 `+0xc8` 写入
仍不足以证明资源已经解码、选择或播放。

已确认请求入口的有限后继为 `0x2e912da → 0x2e630b0`、
`0x2e91319 → 0x2e63b70`、`0x2e9135c → 0x2e92cf0`、`0x2e9138a → 0x2e913f0`。
最后一段包含 `AnimationAsyncLoadingTask`、`RefCountedPtr<AnimationAsyncLoadingTask>`、
`AnimationAsyncLoading` 字符串引用，支持继续按请求／加载层审阅；不把名称当作播放完成事件。

## 已完成的离线检查与采集边界

当前 [请求转发头文件](../red-side-patches/mc_animation_observer.h) SHA256 为
`e6b4546ad02e16204aa060cfd059264f5d27a253fc0b94a4039767d580b1bf06`。
仅匹配两个完整路径：`character/motion/1_pc/1_phm/cd_phm_00_00_nor_move_walk_f_00.paa`
和 `character/motion/1_pc/1_phm/cd_phm_basic_00_00_nor_move_walk_ing_00.paa`；
三个 byte 按原值保存，观察后仍调用原函数，不解引用输出、不替换返回、不捕获后重试。
调用者范围已从 4 GiB 收紧为固定 EXE 的 `SizeOfImage=0x173ab000`：
只有返回地址在 `[moduleBase,moduleBase+0x173ab000)` 内才记录 RVA，其他情况记录 0，保持未知。

2026-10-16 主控执行固定 Python 3.12 的
`python.exe -B tools/check_animation_observer.py`，exit 0，末行为
`13/13 animation observer host checks passed`。没有独立保存 stdout 文件；这里记录主控本轮实际命令结果，
不是本文编写者重跑。检查源码 SHA256 为
`fa95d92bc24f3fe1717632fe36dd6d711735e03a8d4407459c23ef89185e066d`。
它用假内存检查两条精确路径、二跳读取、六参数和三个 byte 保真、原函数恰好调用一次、
独立返回值／输出修改、异常传播，以及停止／污染／不可读／上限下仍转发。

[真实 MinHook fixture 结果](../build/steve-motion-consumer-20261016/minhook-host/result.json)
文件 SHA256 为 `1762ae7163c565baf2017667a7329acf0c1d25d97efc4a4487d54f6ab9393167`，记录 exit 0。
[fixture 源码](../build/steve-motion-consumer-20261016/minhook-forward.cpp) SHA256 为
`0afb0184df535d1d810bdb039a0ada0a502294244f69fef4bdc02cc3eca73740`；
结果记录测试 EXE SHA256 `364d9c2194b33a82b0d09997e182607d2e1dd2142f99353c2eae64d54e3ee68e`，
并固定 MinHook 的 buffer/hook/trampoline/hde64 四个源码摘要。
fixture 对自己的合成 Native 函数安装真实 MinHook，使用假路径内存；六次调用覆盖三种
`0/0x80/0xff` byte 组合、两路径各三次、原函数恰好一次、输出与返回保真，禁用后第七次调用不再增加观察计数，
随后移除 hook。它不证明游戏目标的 ABI、活内存布局或播放行为。

主控另执行 `tools/build_worldbuilder.py --animation-observer`，exit 0。
[构建记录](../build/world-builder-animation-observer/build.json) 文件自身 SHA256 为
`9ab74ac39730f743d2a97daa6794d298bea38eb0dc062c253983edea0d3338f9`；
其中记录产物为 12,776,448 字节，产物 SHA256
`cbb62ec87276341e6dd019a29dbb78318009e2ad7cc648d7fd054f0bc086db09`，
`motion_observer=false`、`animation_observer=true`。此处仅确认独立构建完成。

[最终源码准入记录](../build/steve-motion-consumer-20261016/canonical-ready-check.json) SHA256 为
`cb488ebb8291b5dc594034fed187623d57e3f566060178b7fdab5c6d0be5eaae`，
固定上游提交 `4dcedc8dfe1592fdee0528894389221291900b8d`、691 行 patch；
patch SHA256 为 `ad8f1df87b5924875ff33448d5a87386a7f270e8cfdf24d483b62b265d4389fc`。
六个源文件是**按 Git LF 归一后逐字一致**，不是 raw 字节一致。
早期 `prepared-session.json` 保留的是修正换行前的 patch 摘要，不用它替代最终准入记录。

后续原生采集只能把固定目标入口、精确路径、直接 caller RVA、请求计数和时序当作请求侧证据。
仍须分别证明同会话的目标字节／类型与地址、受控 actor 的 owner 链、具体 clip 的选择和播放消费。
未命中不能排除缓存、其他表示或其他入口；命中也不能证明行走姿态已经由 MC 驱动。
