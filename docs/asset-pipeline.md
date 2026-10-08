# MC 与红沙原生资产：可复建的离线管线

更新：2026-10-08。离线准备工具已生成并检查真实资产，输出留在忽略上传的 `build/`。
后面的临时探针另有可恢复安装与实机步骤，当前验证结果见进度文件。正式桥接仍使用
蓝色方块代理，受控身份沿用原角色；临时外观对照已有MC块体人工观测，持续完整Steve
尚未完成。候选资产不等于全部 MC 内容或 Steve 模式已接通。

## Steve 的原版几何

```powershell
python tools/build_steve_asset.py
python tools/check_steve_asset.py
```

复用哈希固定的官方 MC Java 1.21.1 客户端，调用真实模型构造。输出
`build/steve-1.21.1/steve.gltf`、顶点二进制、64×64 皮肤及来源清单。
六个刚性关节、外层、UV、绕序、逆绑定矩阵和原版渲染比例经过 13 项检查。
官方资源缺失时可使用 `--download` 获取固定依赖，不能随意更换客户端版本。

### MC 动作的来源和运行时边界

2026-10-08 用户进一步要求整个动作系统使用 MC 的实际状态、时序与刚性四肢运动。
现有几何导出只执行模型构造，输出静态中立姿态；六个关节、固定皮肤、红沙neutral
补偿或合成旋转均不证明 MC 动作实现。后续姿态工具须以固定 MC 的实际模型方法和
状态为来源，保存可复核的输入／输出，再单独验收待机、移动、蹲伏、挥击与物品使用
的时序和状态转换。不能继续套用红沙人物动画、重命名动作或手写近似曲线冒充原版结果。

离线姿态准备与原生播放／控制接口分别记录。当前没有已验证的受控角色姿态应用合同，
准备离线姿态工具不代表原生运行时已接通。MC 单击挥击的显示、一次输入对应的动作、
实际伤害／击退和装备效果分别验收；整体要求见 [steve-character.md](steve-character.md)。

## 方块模型与纹理

```powershell
python tools/build_block_assets.py
python tools/check_block_assets.py
```

输出在 `build/block-assets-1.21.1/`。覆盖清单解析客户端的 1062 个 blockstate 资源文件、
6766 个模型选项、2071 个模型和 1012 个纹理依赖，缺失依赖为零。
这是资源清单，**不是已验证的全部注册方块或全部合法状态表**。

另用固定官方数据生成器导出实际 vanilla 注册表：

```powershell
python -B tools/build_block_registry.py
python -B tools/check_block_registry.py --rebuild
```

`build/block-registry-1.21.1/block-registry.json` 核对 **1060 种注册方块、26684 个合法
状态**；每类属性组合完整、全局状态 ID 唯一连续、默认状态唯一，客户端资源无缺失。
1062 份资源中额外两份为 item_frame/glow_item_frame，不是注册方块。10 项检查含真实
生成器重建通过。工具只运行 `net.minecraft.data.Main --reports`，输入客户端与 46 份
库均固定哈希，输出只在 ignored build；不启动世界、不访问运行中的 MC 权威服务。
这是 vanilla 注册表，不是 Fabric 服务的运行时注册表；尚未逐状态实现原生显示与碰撞。
自定义相对客户端/Java 路径在切换工作目录前固定，发布拒绝与输入同路径或同硬链接的
最终/临时输出，避免覆盖已验证的客户端或依赖。

此基线 glTF 工具导出六种已有基线：橡木原木、橡木木板、圆石、泥土、石头、工作台。
保留原木三轴、泥土四方向及石头四个普通/镜像选项，共 14 个 glTF、9 张原版纹理、84 个面。
顶点、默认 UV、UV 旋转及状态旋转通过固定官方 Java 模型类计算。
随机模型选项和权重都保留，没有假称执行了原版的位置随机选择；独立纹理不使用 atlas 的 UV 缩边。

7 组检查从客户端资源独立比对依赖、纹理字节、几何、UV、三轴端面、绕序及输出保护。
141 个资源 ID 的 158 个选项没有 JSON cuboid elements，包括流体、箱子、床、告示牌、
旗帜等特殊渲染类型；工具没有拿立方体或空模型冒充它们。
原生 PAC/材质、透明、动画、光照、碰撞和实际放置仍须逐类实现。

## 全部合法状态到模型的对应关系

```powershell
py -3.12 -B tools/build_block_state_models.py --download
py -3.12 -B tools/check_block_state_models.py --rebuild
```

需先生成上面的固定注册表与资源覆盖文件。新输出目录必须不存在；默认
`build/block-state-models-1.21.1/`，重复导出使用新的 `--output`，不覆盖已有结果。
`--download` 仅获取缺失且固定哈希的官方依赖／映射表。工具只初始化原版注册表，
不启动 MC 世界、客户端或后台服务。

`block-state-models.json` 记录全部 **1060 方块、26684 状态、6529 选择组、6762 模型
选项及 1921 唯一模型**。每个状态引用全部匹配组；multipart 组同时组合，每组内部
保留完整加权备选、旋转及 uvlock，不提前随机选择，也不以默认状态代替其他状态。
与固定客户端原版 `BlockStateModelLoader`／`Selector` 谓词逐状态核对零差异，原版
`BlockModelDefinition`／`Variant` 解析结果也逐选项一致。14 项独立检查通过，包含
21 个谓词边界案例和重新执行 Java 后五个输出文件逐字节相同。

`model-dependencies.json` 保留真实依赖，其中 1849 个模型含 JSON elements，72 个
为空。原版 RenderShape 按状态计为 MODEL 24334、INVISIBLE 1934、ENTITYBLOCK_ANIMATED
416；RenderShape 和是否含几何分别记录，合法空墙组合保留为空。流体、方块实体、
透明、染色和动画尚未接通，不用假立方体填补。注册方块映射与前述 1062 资源清单
数量不同，是因为后者还包含不属于注册方块的普通／发光展示框资源。

报告 SHA256 `e52b62c1e877232007db234bd5a58d3ffb8f354069d77a08cefa2056b76d19e3`；
选择表 SHA256 `574053e2d0a5d6bde2b3c72a4479420c2ea12375caac77debab46efee737f74e`。
全部原生集成标志保持 false。MC Authority 本轮另保存完整属性与运行 stateId，
但仍只开放六种基线方块，尚未将此离线映射接入原生渲染与碰撞。

## 全资源模型的真实面几何

```powershell
py -3.12 -B tools/build_block_model_geometry.py
py -3.12 -B tools/check_block_model_geometry.py --rebuild
```

默认输出 `build/block-model-geometry-1.21.1/`，必须是尚不存在的目录；再次导出用新的
`--output`。复用已校验的客户端与 Java 21 缓存，检查程序另外需要包含 Pillow 的
Python，默认取 PATH 的 `python`，可用 `--decoder-python` 指定。本机使用 Pillow
12.2.0 独立核对 Java ImageIO 的解码结果。工具不启动 MC 世界、游戏或后台服务，
没有安装步骤，六种基线 glTF 与原木候选输入保持原样。

`resource-models.json` 保留 1062 份资源的全部 6766 个选项及原有条件、顺序、权重；
`geometry.json` 按完整 `(model,x,y,uvlock)` 共用 **5163 项几何变体、51059 个真实面**。
其中 5091 项有面、72 项为空，引用 1925 个唯一模型；与合法状态表的 6762 个选项逐项
连接成功，资源清单额外含两个展示框。导出格式为可直接读取的四边形数据，包含顶点、
UV、原始面信息、变换后 cullface、三角绕序和每三角法线，不是新增 glTF 或游戏渲染器。

固定原版 `FaceBakery` 方法按实际顺序执行元素旋转／rescale、方块状态变换、朝向计算，
并仅在没有元素 rotation 对象时重排绕序。3852 个面带元素旋转、1218 个面使用 rescale；
反向坐标、零厚度和 160 个退化面均保留，退化三角的法线为 null，不补造法线或立方体。
原版脚手架中四处 `cullface:"bottom"` 也原样保留，并按原版 Direction 解析为 null，
不猜成 down。独立纹理 UV 不使用 atlas 位置或缩边，动画纹理 UV 为帧内坐标。

973 张面纹理 PNG 与对应 mcmeta 逐字保持，实际像素为 565 张全不透明、360 张二值
alpha、48 张分数 alpha；47 张带动画 metadata。403 个面保留 tintIndex，另保留 shade
与 ambient occlusion。像素 alpha **不能代替 MC render layer**：透明／裁切绘制策略、
生物群系染色、动画帧采样、邻面裁剪和光照均未实现；流体、方块实体及特殊渲染器也没有
补造几何。原生网格／材质／碰撞和游戏内显示仍未接通，所有集成标志为 false。

14 项检查通过：全部来源及权重、独立旋转／缩放数学核对全部 51059 面、未锁 UV 的
顶点关联、完整立方体 16 种旋转／96 个面的 UV lock 世界坐标投影、独立 Pillow 解码全部 973 张 PNG、
真实 Java 重建逐文件一致、首次 build 目录创建、相对客户端／JDK 路径及输出保护。
固定源中不存在会改变父模型继承结果的“空 elements 覆盖非空父级”情况；不将这一检查
推广到其它客户端或资源包。报告 SHA256
`917755b2d860950b82ab90ab1fa7268bf7ebbe07bcdaca26046cc16da6df16f3`；几何表 SHA256
`bf7da867191441a330a50445de22c4f608d002472180529c9d4d180e2f515df4`。

## 红沙真实模板和 Steve PAC 候选

需要已安装的 Python 3.12。依赖源码固定为 CDMW
[`787680f97502522e90ec3dd1ea1889ca86452985`](https://github.com/Ratty123/CDMW-Full/tree/787680f97502522e90ec3dd1ea1889ca86452985)，
校验 ZIP、1663 份 Python 源码的树哈希及 MIT 许可证。干净环境先准备独立依赖目录：

```powershell
py -3.12 -m pip install --target build/cdmw-deps lz4==4.4.5 cryptography==50.0.2
py -3.12 -B tools/prepare_native_steve.py --download-source --game-root "E:\SteamLibrary\steamapps\common\Crimson Desert"
py -3.12 -B tools/check_native_steve.py --rebuild
```

已有固定源目录时省略 `--download-source`；可显式传入 `--cdmw-source`、`--deps`。
本机也可省略 `--game-root`，从 ignored 安装清单读取。`--template-only` 只提取并检查原生模板。
未知 EXE SHA、源码哈希或模板内容会停止，不能用替换固定哈希的方法跳过兼容验证。

工具只读原生 `0009/0.pamt` 与相关 PAZ，导出选定男性 nude 模板的 PAB、PAC、prefab descriptor、
材质、PABC 与 PAPR。已验证真实 447 根骨、189 项 palette、13162 个模板顶点，
原 PAC 无编辑重建字节完全一致。所有读取项在发布前复读，拒绝混用不同快照。

`build/native-steve/steve-rig-candidate.pac` 为 288 顶点、144 三角的离线候选。
保留原生 palette、三个 draw descriptor 及其它运行 metadata；四个 LOD 都保留完整方块几何。
15 项检查包括真实模板重建、全部权重边界、候选顶点/UV/刚性权重回读、LOD 和输出链接拒绝。

候选使用真实 Head、Spine_Sub、UpArmTwist、Thigh 等骨名；辅助/扭转骨映射仍需动画、
贴合和变形验证。本节 PAC 保留原材质；下文另生成皮肤候选。外层透明、动态装备、手持点、受控身体
外观选择、重载持续应用和禁用恢复均未验证。报告的集成标志全部为 false。
**PAC 可以解析不等于模型可在红沙加载。**

## 原木静态 PAM 与原生材质候选

```powershell
py -3.12 -B tools/prepare_native_block.py
py -3.12 -B tools/check_native_block.py --rebuild
```

真实蓝色代理来自 `0000/0.pamt`，使用 **PAM 静态模型**，不是角色 PAC。
工具固定其 24 顶点/12 三角、Standard PAMI、PAMLOD、HKX、meshinfo 和 binary prefab 指纹。
无编辑重建字节相同；候选保留原立方体位置/绕序/不明确的压缩着色字段，按真实 MC
三轴端面与侧面更新 UV。低 LOD 由原来的 13 顶点/6 三角补全为 24/12，材质名与 PAMI
一致；prefab 由完整结构解析后替换 PAMI 引用并重定位指针。

当前默认 `build/native-block-declaration-fixed/native-block-report.json` 列出 21 个候选
资源：三张 DDS，以及三轴各六项
模型/材质/碰撞/描述资源。两张原版 16×16 纹理组成 32×16 atlas，最近邻放大到 128×64，
共八层 mip。独立 Pillow 12.2.0 逐层解码；底层最大 RGB 误差 4，低 mip 最大误差 21，
并非无损贴图。当前真实重建 **17/17 检查通过**，包含真实档案重建、MC 三轴映射、
材质一致性及输出保护。生成拒绝非空输出，保留历史 `build/native-block` 的原始候选；
重复生成请指定新的 `--output`，不要覆写 A/B/C 的已记录来源。

2026-10-07，C 单变量实测确认该版本下删除生成 PAMI 的固定 XML 声明后，Y 轴原木
可见且有碰撞，详见下文。普通生成器因此将三轴 PAMI 改为不带声明的 UTF-8，并记录
`materialSerialization="pami-utf8-no-declaration-v1"`。相较历史普通候选，仅三份
PAMI 从 760 变为 721 字节，另 18 项资源不变；Y PAMI 与已实测 C 字节完全相同。
报告 SHA256 `7fd02bb439f52738b829472c2fa7cdc658be3123ebb733252187eaac21287417`。

资源客户端要求该明确标记、普通候选身份和三轴 PAMI 与真实模板生成的预期字节全部
一致，不能只删去对照身份后冒充普通候选，也未放宽历史 C 来源保护。资源客户端
27 项、对照生成 27 项、实体探针 42 项检查通过。结论限于固定 EXE 和本生成器的精确
声明格式，不推广为原生解析器拒绝所有 XML 声明。修正后三轴包尚未安装验收；X/Z 未
实机显示，Y 轴全部面 UV、过滤、atlas 接缝与光照仍未验收，不能推广为全部方块支持。

## Steve 皮肤与材质候选

```powershell
py -3.12 -B tools/prepare_steve_material.py
py -3.12 -B tools/check_steve_material.py --rebuild
```

独立解码器默认是 PATH 上的 `python`，须安装 Pillow 12.2.0 并匹配工具固定的 DDS plugin
源码 SHA；也可传 `--decoder-python` 指定已有运行时。CDMW 仍在独立 Python 3.12 进程中使用。
自有编码器将真实 Steve 皮肤最近邻放大为 256×256 DXT5/BC3，保留 alpha；normal 为
BC5U，材质常量图为 DXT1，各九层 mip。底层最大 RGB 误差 4、平均 1.479367、alpha
误差 0；低 mip 仍有量化误差，透明裁切与采样未验证。

真实身体 sidecar 的 18 个包装/6 组变体由 SkinnedMeshSkin 改为 Plain PBR，参数形状
来自已核对的原生剑 SkinnedMeshStandard 模板（3 纹理参数及 renderSettingFlag=4）。
包装外的变体/运行属性保持原文本；未知的 morph/wrinkle/physics 依赖没有假称已解决。
`build/steve-material/steve-material-report.json` 含五项资源及全部模板 SHA。
14 项含真实重建检查通过。这些新资源没有 actor 引用；材质转换不等于受控 Steve 外观。

## Steve prefab 与骨骼依赖候选

```powershell
py -3.12 -B tools/prepare_steve_prefab.py
py -3.12 -B tools/check_steve_prefab.py --rebuild
py -3.12 -B tools/prepare_asset_overlay.py --report build/steve-prefab/steve-prefab-report.json --output build/steve-prefab-overlay
py -3.12 -B tools/check_asset_overlay.py --output build/steve-prefab-overlay --verify-game
```

输出报告含 PAC、材质、三张 DDS、binary prefab 与 descriptor 共七项。
新逻辑路径为 `/character/prefab/1_pc/01_phm/nude/crimsonmc_steve_1_21_1.prefab`。
完整解析真实 prefab 的 CD_Nude/CD_Underwear 两对象，仅替换前者的 `_skinnedMeshFile`；
等长路径改动、六处指针重定位、其它字节不变，逆向改回与真实模板完全一致。
内衣资源和 descriptor 原文保留，PAB/PABC/PAPR 三依赖从真实归档复读校验。
16 项检查含真实重建通过，七资源 overlay 的 13 项预演也通过，PAZ 为 334976 字节。
这次预演以仍装原木 0041 的快照生成 0042；原木恢复后此快照已过期，安装前须重新生成，
不能复用旧计划。该阶段尚未安装 Steve；当时 prefab 未指向受控 actor，动画、贴合与装备未验收。

## 独立资源包与索引预演

```powershell
py -3.12 -B tools/prepare_asset_overlay.py --report build/native-block-declaration-fixed/native-block-report.json --output build/native-declaration-fixed-overlay
py -3.12 -B tools/check_asset_overlay.py --output build/native-declaration-fixed-overlay --verify-game
py -3.12 -B tools/prepare_asset_overlay.py --report build/steve-material/steve-material-report.json --output build/steve-overlay-rehearsal
py -3.12 -B tools/check_asset_overlay.py --output build/steve-overlay-rehearsal --verify-game
```

预演只写 `build/native-asset-overlay` 或显式输出，不修改游戏。独立 overlay PAMT/PAZ
包含新路径，拟议 PAPGT 将其排在原版目录前面，拟议 PATHC 注册三张完整 DDS。实际
PAPGT 有 39 项，0036～0040 是已保留的可选挂载记录（本机未安装这些 payload）；
分配器因此选空闲 0041，不能照搬 CDMW 分发容器默认 0036。

保留全部原目录的顺序/语言 flags/checksum，以及 PATHC 原 291531 项、654 份 header、
12 份碰撞与名字数据；新纹理分别增加三项。完整 DDS 显式使用 raw flags=0，不继承
PartialDDS 模板的分块存储；材料 XML 按原生 LZ4/ChaCha flags 回编码。包解码与输入
字节逐项一致，PAZ 边界/校验、PAMT 无编辑回建、完整 mip 长度及原 metadata 保留已检查。
只使用固定 CDMW Python checksum 算法，不下载/调用额外 checksum helper。

13 项检查还拒绝坏 DDS/损坏包/有效校验下的挂载或纹理记录篡改/路径和输出链接。
报告路径与所有临时路径在首个写入前统一检查，包先在 build staging 解包审核后发布。
离线预演报告的安装/显示/加载标志保持 false。挂载与卸载另有新鲜预检、所有权收据和恢复验证；
原版 PAZ/PAMT 无须被改写。

上面的普通候选命令使用新的独立输出，须在上一临时包恢复后按原始索引快照生成，
不复用历史 `build/native-asset-overlay` 或 A/B/C 计划。最新挂载/恢复状态以
[progress.md](progress.md) 为准；存在安装中收据时先完成其恢复，不把它收入新基线。

## 可恢复的原木实机探针

```powershell
py -3.12 -B tools/check_asset_probe.py --plan build/native-declaration-fixed-overlay
python tools/check_native_block_probe.py
# 关闭游戏后安装；只接受本项目 21 项固定资源及已校验的普通/对照报告
py -3.12 -B tools/install_asset_probe.py --install --plan build/native-declaration-fixed-overlay
# 启动并进入世界，等待原生 ready/buildOk，再生成一块诊断原木
python tools/probe_native_block.py --spawn --journal runtime/native-block-declaration-fixed-first.json
# 同一游戏进程内清理，随后正常退出游戏
python tools/probe_native_block.py --cleanup --journal runtime/native-block-declaration-fixed-first.json
py -3.12 -B tools/install_asset_probe.py --restore
```

安装器重新核对游戏版本、原索引、可选挂载和空闲目录，先备份 metadata 与存档，再写
自有目录、PATHC，最后挂载 PAPGT；收据记录每个文件的哈希与所有权。恢复先解除挂载，
恢复原 metadata，再删除自有文件。遇到其它修改或游戏仍运行时停止，不覆盖后来存档。
断电、发布失败和恢复中断的隔离测试通过；实际安装与恢复结果另记在进度文件。

对象探针只通过已验证的游戏线程 API 放置诊断对象，不请求 MC 放置或消费材料。
最多探测相机前方七个近处点，每点检查中心和四角；避开已有登记对象并拒绝陡坡。
所有候选都不合格时不写生成日志、不创建对象；有合格点时只提交一次生成。
登记受理、物理碰撞、实际画面分别验收；对象列表没有每 UID 原生 live 标志。
日志保存进程创建时间、UID、路径和变换，清理拒绝跨重启 UID 与外部对象。
红沙创建对象时会自动选择编辑项目，并可能创建空 Untitled 项目和更新设置；这项
上游行为不能称为完全无项目副作用。诊断不调用项目保存或修改 autoload，测试前要求
关闭项目自动保存，保留原有项目文件。临时资源验证不等于正式 MC ID 映射已接通。

2026-10-06 实机登记成功，但画面无原木、一米碰撞检查失败；对象已清理且 MC 状态
未变。游戏正常退出后临时包已恢复，38 个原始索引/元数据哈希一致。28 项隔离 HTTP
检查通过不改变这项实机失败结论。下一步定位资源加载失败，再验收显示/碰撞及桥接映射；
Steve 继续验证原生骨变换和安全可恢复的外观选择。

## 原生资源读取诊断

`probe_native_resources.py` 使用插件的固定资源读取接口。默认检查六项原版蓝块、
六项 Y 轴原木及三张原木 DDS；`--group blue` 只检查六项对照，`--group oak` 检查
九项 Y 轴/纹理资源，`--group all` 检查全部 27 项。读取前校验本地模板与报告来源，原生返回
长度、前 16 字节和 FNV-1a64；本地资源仍使用 SHA256 校验，FNV 不作为安全哈希。

```powershell
python -B tools/probe_native_resources.py --assets build/native-block-declaration-fixed/native-block-report.json --output runtime/native-resource-declaration-fixed-first.json
```

每项只提交一次；超时或失联保留已有 ticket，不重放。输出必须是 ignored runtime
中的新文件，已有报告不覆盖；前后核对支持版本、同一游戏实例和真实 MC 状态。
这个诊断不安装包、不生成实体、不修改库存；全部文件读取一致也不能代替画面和碰撞
验收。完整命令、检查与实机结果见 [progress.md](progress.md)。

客户端的 `--assets` 默认已跟随普通生成器，指向
`build/native-block-declaration-fixed/native-block-report.json`；上例保留显式参数以便
审阅。测试历史普通候选或 A/B/C 时须传实际已安装报告，不能混用不同文件身份。

2026-10-06 默认 15 项已实测全部首次读取成功，长度/头部/FNV 与本地资源一致，前后
游戏实例及 MC 状态保持。X/Z 两轴未在该次读取；未复试生成或验收显示/碰撞。之后
正常退出并恢复第二次临时包，38 个原始文件哈希一致，0041/active receipt 已移除。

全部原版/派生资源留在本机；Git 只发布转换代码、来源、许可证及检查摘要。
总体进度见 [progress.md](progress.md)，分发边界见 [workshop-distribution.md](workshop-distribution.md)。

## 蓝块别名对照与试验身份

`prepare_native_block_control.py` 从已核验的普通原木候选生成独立目录，只将
`oak_y.prefab` 换为完整原蓝块 prefab，仍引用原蓝块 PAMI；另 20 项候选保持字节一致。
报告固定为 `blue-template-alias`，记录原候选报告 SHA 和唯一改动，不继承原木几何结论。
第二种 `blue-material-alias` 保持正常原木 prefab，只换 Y 轴 PAMI 为完整原蓝块 PAMI，
仍引用原 PAM/DDS，其余 20 项不变。两种生成及来源保护检查最终 21/21 通过。

```powershell
py -3.12 -B tools/prepare_native_block_control.py --source build/native-block/native-block-report.json
py -3.12 -B tools/prepare_native_block_control.py --source build/native-block/native-block-report.json --variant blue-material-alias
py -3.12 -B tools/check_native_block_control.py
# 原木包恢复后，按新的游戏索引快照准备独立控制计划
py -3.12 -B tools/prepare_asset_overlay.py --report build/native-block-blue-alias/native-block-report.json --output build/native-blue-alias-overlay
```

生成器拒绝既有输出目录，重复运行须选新的 build 输出。安装器要求单一、完整校验的
候选报告，并将普通 `static-oak-log` 或两种对照身份及报告 SHA 写入
收据。资源读回日志记录该身份；实体生成前与实际已安装文件核对，对照仅允许 Y 轴。
旧实体日志仍可按其原进程/UID 清理；清理不依赖候选报告或当前安装收据继续存在。
蓝块别名的显示/碰撞结果只能解释对照，不能作为原木或 MC 材质验收。

实机普通原木在新进程中读回 15 项资源后仍不显示/无预期碰撞；A prefab 别名对照则
在同一逻辑路径显示蓝块，首次地面采样增量 1.1521 米、清理后回到 0，MC 状态保持。
因此新 prefab 路径可用；随后 B 新 PAMI 路径对照也实测蓝块可见且碰撞增量 1.1521 米，
清理后回到 0，MC 状态保持。正常 prefab/新 PAMI 路径可用，继续检查 PAMI 内容及
模型/纹理组合，最新恢复状态见进度文件。
对象探针最终 41 项隔离检查通过，碰撞循环现在保留首末采样、次数和 min/max 差值，
清理阶段失败也会保存。最新临时包是否恢复以 [progress.md](progress.md) 当前状态为准。

第三种 `oak-pami-no-declaration` 仅删除历史普通 Y PAMI 固定的 39 字节 XML 声明，文件
760→721 字节；保留剩余字节和其他 20 项资源，独立 XML 树语义相同。初始假设仅用于
区分序列化因素；下节记录后来的实际结果。生成时必须沿用历史普通候选来源：

```powershell
py -3.12 -B tools/prepare_native_block_control.py --source build/native-block/native-block-report.json --variant oak-pami-no-declaration
```

报告增加原资源 SHA、删除前缀与语义验证。已修正的普通三轴候选不能成为这个删除声明
对照的输入，否则不再是原来的单变量实验。
生成器 27 项检查、资源客户端 24 项检查通过；C 封装/隔离恢复通过后短暂安装，启动
接管时 Escape 停止，确认游戏未运行后已恢复，当时尚未实测。资源诊断预检失败
也保存实际状态响应，仍在 ready/buildOk 均成功后才提交读取。

### 2026-10-07 C 原木显示与碰撞实测

用户随后明确恢复游戏接管。本次 C 收据 `c2fb925c9d2b423996d764886408cf1a`，同一
游戏实例先读取 **15/15 项全部一致**，再只生成一块 Y 轴原木。日志
`runtime/native-block-oak-no-declaration-20261007.json` 的 runId 为
`6618070e-0a9a-4c2a-a307-e2dd1b23d252`、UID 1，实际碰撞增量 **1.151980 米**。
画面可见像素化棕色原木侧面及顶面，部分被当前角色遮挡；截图
`runtime/native-oak-no-declaration-visible-20261007.jpg`，独立视觉记录在
`runtime/native-oak-no-declaration-visual-20261007.json`。自动探针 visualVerified
仍为 false，实际显示结论来自独立画面观测；并未验收全部面 UV 或光照。

同进程清理后登记和实际碰撞均移除，地面增量为 0，画面对象消失；MC 状态保持
schema 2、revision 18，未消费材料。这为本固定版本、模板和精确序列化差异提供实机
证据，普通生成器已按上节修正。C 成功不表示修正后的 X/Z 已验收，也未接通正式方块映射。

退出确认的自动短按未生效，后续确认实际进程已退出再完成恢复；该 C 收据现为
restored，38 项原始索引／元数据哈希一致，0041 与 active receipt 已移除。
恢复保留后来存档，独立检查在 `runtime/asset-probe-restore-c-20261007-checks.json`，
最终收尾见 [progress.md](progress.md)。

修复后的完整三轴包随后在新进程读回 **27/27** 项，X/Y/Z 分别生成、碰撞和清理
通过，MC 状态保持。各轴画面可见部分像素纹理，角色仍遮挡多数面；完整朝向、
各面 UV／光照仍未验收。相对地面增量 1.15198 m 包含地面高差和放置偏移，相对
放置原点的碰撞顶面为 1.01163 m。该三轴试验使用新收据
`5c89c03dc0614c7ba5066598062c0711`，对象已清理；用户正常退出后包已 restored，
38 项原始哈希一致，无 0041／active receipt，MC 完整状态保持。这是独立于上一段
C 对照的三轴收据。确切日志、SHA 与收尾状态见进度文件。

## Steve 骨骼与朝向的离线证据

```powershell
py -3.12 -B tools/analyze_steve_rig.py
py -3.12 -B tools/check_steve_rig.py --rebuild
```

固定九项真实输入，独立读取 447 骨 PAB、423 条 PABC 并与固定 CDMW 对照；中立变形
最大偏移约 1.81 微米，真实重建检查 10/10 通过。六个 MC 关节与原生关节中心仍相差
约 0.231～0.356 米；MC 头/身体中心重合，原生两中心相距 0.602756 米，所以单一
全局仿射变换无法同时对齐。逐部位静态平移会破坏接缝并使脚底抬升，未用于资产。

眼/脚趾链及左右 X 坐标支持原生模型前方为 -Z，当前 MC 导出为 +Z。下一静态候选是
独立 Z 反射，同时反射法线、反转三角绕序并重新生成切线；这仍须验证 actor 父变换与
引擎渲染。报告内逐关节 30 度旋转只是合成数学检查。没有修改 PAC/PAB、安装 Steve、
取得实时姿态接口或验收动画/装备。

随后已生成独立 `build/steve-orientation`，原七资源链保持，只有 PAC 做 Z/法线反射、
一次三角绕序反转及原生 UV frame 重建。四级 LOD 每级 288 顶点/144 三角，骨权重、
palette、UV、元数据和其余六资源不变。使用原 15 位位置量化字段，未移动任何骨骼。

```powershell
py -3.12 -B tools/prepare_steve_orientation.py
py -3.12 -B tools/check_steve_orientation.py --rebuild
```

生成器拒绝已存在的输出，重复运行需指定新的 build 目录。13 项真实重建检查通过，
独立检查原始 frame/绕序/每级完整性及源输入不变。固定 donor 的 11476 条唯一强样本
支持 packed V 与 bit31 符号约定，但 shader ABI、实际光照/朝向仍待实测。报告的全部
集成标志保持 false；这项候选没有解决关节中心差异、控制身份、应用/恢复和装备。

## Steve 四肢分段蒙皮候选（2026-10-07）

旧候选每个逻辑部位为单骨权重，整个手臂／腿只跟随 UpArmTwist／Thigh；真实骨架的
Forearm／Hand 和 Calf／Foot 分支对这些顶点没有影响，因而不能跟随原生屈肘、屈膝
和手足旋转。新工具从固定朝向候选生成另一套资源，不改旧候选或安装游戏。

```powershell
py -3.12 -B tools/prepare_steve_segmented.py
py -3.12 -B tools/check_steve_segmented.py --rebuild
```

默认输出 `build/steve-segmented`；生成器拒绝已有目录。它要求前述固定原版几何、
PAB/PAC/PABC、prefab 和朝向候选已生成，读取过程中核对 SHA 与输入快照。四肢在
真实肘／腕／膝／踝的 bind 高度添加共面截面和一 MC 像素宽的两骨过渡，保持六个
逻辑部位的静态表面和 UV。原生 palette 仍为 189，PAB 仍为 447 骨；腕以下完全
跟随 Hand，踝以下完全跟随 Foot，中段使用实际 donor 已赋权的 Forearm_sub／Calf_Sub。

四个 LOD 每级 **1056 顶点／528 三角形**，原始 PAC byte 权重总和 255，混合节点
为 127/128。独立仿射 UV、面面积／绕序、重复位置一致权重、所有 LOD、CDMW 独立
inverseBind×pose 和真实重建逐字一致共 **12/12 通过**。24 个 30° 合成轴旋转
证明远端现在响应以前零影响的骨链。量化最大位置误差 `2.6676e-5 m`、UV 误差
`1.7468e-4`；PAB rest 位移 `4.699e-8 m`，旧 PABC neutral 位移 `2.008e-6 m`。

只有 PAC 改变，其余六项候选资源和所有模板逐字保持。报告 SHA256
`e7a879dfb26e38b64fe0d65322b89e98b792018ae1bd7762ad47c7367b4ae0fd`；PAC SHA256
`dd1143464bedc9b8aab9a5a39a3eaa9381753690497d2eda35cd8bb3edcfaf1a`。

该候选仍使用旧 **00_0001.pabc**，没有验证当前受控资源的 01_0002 描述符和 scale。
头／躯干／肩髋旋转中心、原头和内衣排除、独立 CD_Head 装备遮挡仍未解决。
Bip_Weapon_L/R 是 Hand 子骨且 bind 点处于手骨赋权区域，但实际装备是否使用该接点
未验证。合成弯曲不是原生动画或渲染验收；新候选改变四肢动态变形，不宣称保持原版
MC 刚体运动。所有安装、外观应用、动画和装备验收标记仍 false，资源留 ignored build。

## Steve 头身分件与当前角色配置（2026-10-07）

```powershell
py -3.12 -B tools/prepare_steve_parts.py
py -3.12 -B tools/check_steve_parts.py --rebuild
py -3.12 -B tools/prepare_steve_parts_prefab.py
py -3.12 -B tools/check_steve_parts_prefab.py --rebuild
```

分件默认输出 `build/steve-parts`，固定读取前一节的分段候选。头与帽层为独立 PAC，
每 LOD 48 顶点／24 三角；身体与四肢及外层为另一 PAC，每 LOD 1008 顶点／504 三角。
四 LOD 与合并源的几何、UV、权重及全部 40 字节顶点记录逐字一致，两部分的并集无
遗漏或重复。保留 447 骨／189 palette 和三个原生 draw descriptor，空 draw 不复活。
**7/7** 检查含真实独立重建通过，原候选文件保持。

每个 PAC 都有其同名 `modelproperty/...pac_xml` 材质；两份材质字节相同，保留原
三个 draw 名和六套 variant，引用同三份 DDS。因此这里有七项候选资源，不携带旧
合并 prefab 或旧 descriptor。材质路径遵循固定 CDMW 的
`appearance_model_sidecar_path`；这是静态依赖规则，尚未证明游戏实际加载。

组合工具单独输出 `build/steve-parts-prefab`：从真实当前 Macduff 身体与头部 prefab
保留首项 CD_Nude／CD_Head，删除该候选中的内衣和旧头部细件，引用上述两个新 PAC。
保留原部件名、Nude shrink tag、0.05 shrink distance、空骨架字段、原 owner token
与头部 `breath_effect_basic`。第三资源是当前 01_0002 身体 descriptor 的原字节副本。
二进制组件删除显式保留被留下的 name-pointee footer；不能使用 CDMW 通用数组删除
后表面 walk_complete 的结果，检查已复现该路径遗留错误 footer。
组合工具默认从 `runtime/installation.json` 或 `--game-root` 指定的原版安装只读提取
三份固定模板；先核对 EXE 与 0009 索引，再核对每个 payload SHA，不需要历史研究
目录。显式离线输入须同时给 `--inputs` 和 `--descriptor`。**16/16** 检查含真实索引
提取后独立重建、错误 footer／指针／计数／头部及输入变化拒绝通过。

这两份报告路径可以静态连接，但旧分件 PAC 使用 00_0001 neutral，不能与当前
01_0002 descriptor 直接称为已验收的角色。PAB、PABC、PAPR、ragdoll、原 wrinkle
描述符与动画 key 仍是外部依赖；原独立 Hair/Beard、appearance 的 head scale、
装备遮挡和受控身体绑定也仍未处理。全部安装、渲染、动画和装备标记保持 false。

当前配置的独立补偿候选：

```powershell
py -3.12 -B tools/prepare_steve_current_rig.py
py -3.12 -B tools/check_steve_current_rig.py --rebuild
```

工具默认输出 `build/steve-current-rig`，从固定 0009 索引提取实际 Macduff prefab、
327 字节 descriptor、420 记录的 01_0002 PABC 及共享 PAB/PAPR。descriptor 五字段
逐字保持，包括 `BaseCharacterScale=1.02571` 和尚未解析 payload 的 `macduff.hkt`。
直接使用旧 bind 几何会在该中立配置下偏移最多 0.088770 m，躯干顶面收缩约 4.38 cm。

对每个顶点按实际 byte 权重求混合矩阵 A，再用 `p_bind=p_target*inverse(A)` 做
独立预变形。只修改 PAC 的包围盒、位置、法线和 V frame，原拓扑、UV、权重字节与
四 LOD 保持。重新解码量化产物后，中立姿态回放误差最大 `2.705741e-5 m`；法线
协向量与 V 方向回放 dot 最低约 0.999594／0.999721。矩阵与 shader 解释尚须原生
验证；非均匀形变下运输的是目标中立表面的 frame，不宣称是预扭曲 bind 表面的导数。

这套显式候选仍使用合并 PAC，保留当前 prefab 的内衣；它与前述私有头身分件分别
验证，后续组合见下一节。原 scale 没有烘焙或抵消，实际 head scale、动态
关节接缝、原生 normals、全部装备和应用／恢复生命周期仍未验收。
**13/13** 检查通过，包括真实固定索引提取后的完整重建、独立非对称 shear／混合权重
反例、PABC 覆盖不足和未知 byte lane 修改拒绝。当前候选 PAC SHA256 为
`3632e1def16d851bf0038dc585ed0bc9a248dd799d462a9435f2816ae8677237`。

## 私有十资源组合与两属性外观候选

在上述分件、私有 prefab 和当前 neutral 候选完成后，分别生成独立输出：

```powershell
py -3.12 -B tools/prepare_steve_assembly.py
py -3.12 -B tools/check_steve_assembly.py --rebuild
py -3.12 -B tools/prepare_steve_appearance.py
py -3.12 -B tools/check_steve_appearance.py --rebuild
```

`build/steve-assembly/steve-assembly-report.json` 固定组合十项资源：两 PAC、各自同名
两 PAMI、三 DDS、两私有 prefab 和当前身体 descriptor。身体使用当前 01_0002
neutral 补偿，其四 LOD 顶点完整记录与 combined-current 的身体部分一致；头部 PAC
保持原 split 字节。实际 Head0001 PABC 有 207 条记录，却没有头部唯一加权骨
`Bip01 Head`（93）。工具分别计算 CDMW 单个 PABC 的 PAB bind 回退及继承身体
neutral 的假设误差，不把其中任何一种宣布为原生头身合并合同。

组合保留两 PAC 的拓扑、UV、byte 权重与 palette；独立 CD_Nude/CD_Head prefab
排除原内衣与头部细件。材质纹理路径在十项资源内闭合，PAB/PABC/PAPR、ragdoll、
wrinkle 和 `breath_effect_basic` 仍依赖原游戏。原生 HeadScale=0.92、身体 scale、
动态接缝、shader frame、装备和实际加载均未验收。**12/12** 检查含独立真实重建通过；
纯 `load_candidate` 固定整报告 SHA、三份来源报告、每个模板与 payload，不加载 CDMW
或以可改写的报告标记授予安装资格。

`build/steve-appearance/steve-appearance-report.json` 默认从固定 EXE/0009 索引
只读提取原版模板并复读校验。它只修改
`character/descriptors/customizationmeta/meshparam_example_kliff.xml` 中两个属性：

| 默认选项 | 原 MeshFileName | 私有 MeshFileName |
| --- | --- | --- |
| Body，组 0 / MeshSet 0 | `cd_phm_00_nude_01_0002_macduff` | `crimsonmc_steve_body_1_21_1` |
| Head，组 1 / MeshSet 0 | `cd_phm_00_head_00_0001_macduff` | `crimsonmc_steve_head_1_21_1` |

其余 XML 字节及语义保持，逆替换逐字还原模板；七组选项数、默认值、variation、
decoration 输入、Hair/Beard 和 scale 均未修改。报告的 `candidateResources` 为空，
唯一旧路径单列 `targetReplacements`，固定 loader 重新生成预期两属性替换并核对
全部字节。**12/12** 检查含真实提取重建、篡改拒绝与逆向还原通过。

固定 0009 的 5667 份 app_xml 和 5 份 meshparam 静态扫描中，该 meshparam 被
Macduff 00000/00002 引用；一份无关 NPC XML 解析失败，扫描也不覆盖其它归档和运行时
生成引用。因此替换会影响使用该共享路径的所有实例，不能称为只对当前 actor 生效。
直接替换共享身体 prefab 的消费者范围更大，本候选不这样做。原 Hair/Beard 与装备
保留，可能遮挡 Steve；FF 是默认回退，不能当作隐藏。配置候选不代表已应用外观。

## 独立十一资源临时 Steve 包

```powershell
# 只写新的 ignored build 输出，原木临时包须已恢复
py -3.12 -B tools/prepare_steve_probe_overlay.py
py -3.12 -B tools/check_steve_probe.py --rebuild
```

默认输出 `build/steve-probe-overlay`。它只接受上节固定十资源 assembly 和一份
两属性替换，实际包必须恰好十一项：十个 crimsonmc 新 basename 加上述唯一旧路径。
`prepare_asset_overlay.py` 的普通 CLI 和 `load_resources` 继续拒绝旧 basename；
新增的 `replacement_report` 仅为程序内部限定入口，由 appearance 的纯固定 loader
验证。旧路径通过新 overlay 首位挂载覆盖，不改写原版 0009 PAZ/PAMT。

专用安装器重新验证两个候选报告、十一项解包字节及真实存储 flags、六份包／metadata
文件、原索引和纹理注册，复用已有备份、锁、关闭游戏检查和恢复事务。独立种类为
`steve-mesh-parameters`，owner 为 `CrimsonMC temporary Steve mesh-parameter probe v1`。
原 `install_asset_probe.py` CLI 保持默认 `oak-log`。两者共用一份 active receipt，
禁止并存；kind/owner 不符在恢复写入前拒绝，Steve 包必须用 Steve 入口恢复。

完成隔离故障检查并安排实机验证后，关闭游戏时的专用操作入口是：

```powershell
py -3.12 -B tools/install_steve_probe.py --install --plan build/steve-probe-overlay
# 验证后正常退出红沙，再恢复同种类包
py -3.12 -B tools/install_steve_probe.py --restore
```

安装前备份 metadata 和存档，恢复只解除临时挂载、恢复原 metadata、删除确属收据的
包文件，**不覆盖后来存档**；外部修改或游戏运行时停止并保留恢复证据。独立 Steve
故障／真实重建检查 **21/21** 通过，包括不同 kind 拒绝交叉恢复。Windows 本地路径
先规范分隔符再检查 build 边界，游戏虚拟路径仍严格要求 POSIX；目录越界反例通过。
实机结果另记 [progress.md](progress.md)，隔离故障检查不代替原生显示／恢复验收。
该十一资源首测没有通过 Steve 游戏内显示、装备覆盖或实际外观恢复；临时共享资源包也
不满足启用 mod 后跨重载自动持续 Steve 的完整目标。一次真实安装／启动后，受控
选项表已读到两私有 basename，但接管再次被物理 Escape 停止。用户随后明确反馈
仍是原角色，因此外观切换未通过。退出后已恢复原始文件，最新存档和 MC 状态保持，
无待恢复项；详情见进度记录。

## 私有头描述文件的单变量对照

首测用户实际仍看到原角色。原版头 prefab 有同 basename 的 `.prefabdata_xml`，
此前十资源 assembly 只有身体描述文件；固定 CDMW 的 Name 关系解析也会枚举这类
配套文件。这支持补齐依赖的对照，但尚不能证明缺失文件导致首测失败。

```powershell
py -3.12 -B tools/prepare_steve_head_descriptor.py
py -3.12 -B tools/check_steve_head_descriptor.py --rebuild
py -3.12 -B tools/prepare_steve_probe_overlay.py --head-descriptor-report build/steve-head-descriptor/steve-head-descriptor-report.json
py -3.12 -B tools/check_steve_probe.py --head-descriptor --rebuild
```

描述文件输出为 `build/steve-head-descriptor`，对照包为独立的
`build/steve-head-descriptor-probe-overlay`。两个生成器均拒绝覆盖已有输出。
默认十一资源包保留；新包恰好增加一项：
`character/prefab/1_pc/01_phm/head/head/crimsonmc_steve_head_1_21_1.prefabdata_xml`。
内容逐字复制固定原头 Head0001 的 466 字节，SHA256 为
`d69be68d7e5592b40c601f98899465a69694eeff7213809b0063217a9faee56b`，flags 为 48。
原七个字段、BOM／换行和六个文件引用保持，EmotionAnimationSet 保持原命名集；
外部依赖未重复打包。原十一项 payload 和纹理注册表逐字不变，不同时修改 app、
PAC、材质、prefab、骨架、缩放或 meshparam。

本对照仅允许原两个报告加上这一个固定报告；缺报告、多资源、错标志或字节变化
均拒绝。对照收据的 `probeVariant=steve-kliff-head-descriptor-v1`，沿用
`kind=steve-mesh-parameters`、原 Steve owner 和恢复事务，绑定完整包报告及安装哈希。
独立头描述文件的 8 项检查通过；对照包的完整事务结果见进度。
实际试验时使用 `install_steve_probe.py --install --plan build/steve-head-descriptor-probe-overlay`；
退出后仍用 `install_steve_probe.py --restore`，不覆盖后来存档。
后续手动实测仍显示原角色，单独补齐头描述文件没有使外观切换通过；下一项为下述目录登记对照。

## 私有部件目录登记与单 app 对照

后续手动实测确认：十二资源包仍显示原角色，schema 7 双采样读到当前初始 app 为
`character/appearance/1_pc/1_phm/cd_phm_macduff/cd_phm_macduff_00000.app_xml`。
固定 EXE 的 Name 解析还依赖 `character/bin__/partprefabtable.pappt`；原表两段均没有
私有 Steve stem。仅加入 prefab、descriptor 和 meshparam 没有补齐此目录依赖。

```powershell
py -3.12 -B tools/prepare_steve_part_table.py
py -3.12 -B tools/check_steve_part_table.py --rebuild
# 两份 app 候选分别生成，每份只修改自身两个 Name，不同时替换两个 app
py -3.12 -B tools/prepare_steve_app.py --variant macduff-00000
py -3.12 -B tools/prepare_steve_app.py --variant macduff-00002
py -3.12 -B tools/check_steve_app.py --rebuild
```

PAPPT 固定源为 2130295 字节，SHA256
`d6947dcb57d32e0503704da28edf4645baaa8faad8fbd47d09a8a8832686abed`，flags 50。
独立有界解析限定原始 tag=01 格式，原部件数 15566、描述文件目录数 2630。克隆当前
Body 01_0002 与 Head0001 的记录，换 stem 后让新 part 行仅保留私有 prefab 实际拥有
的 CD_Nude／CD_Head；原目录、socket、额外字段、flags 保持，原始 donor 行仍保留
自己的全部部件。两段各追加两行，计数变为 15568／2632，全部旧行字节／顺序保持。
v2 文件 2130527 字节，增加 232 字节；逆移除逐字恢复。旧 v1 沿用原版 2／7 个槽
与私有 prefab 不符，已失败撤回；新候选为这处具体差异的对照，尚待实机验证。
同名私有 prefab 和描述文件必须同时存在，目录登记本身不包含模型载荷。

PAPPT v2 默认输出 `build/steve-part-table-v2/steve-part-table-report.json`，kind 为
`partPrefabTable`；app 默认输出分别为 `build/steve-app-macduff-00000` 和 `...00002`，
报告名 `steve-app-report.json`，kind 为 `appearanceDefinition`，flags 48。
三份报告均只有一项 `targetReplacements`、空 `candidateResources`；纯 loader 从固定
源重新构造精确报告与 payload，不使用报告中的成功标记准入。PAPPT v2 **10/10**、
既有 app 候选 **8/8** 检查通过；实际注册加载、显示、动画和装备仍未验证。

资源包入口将登记和初始选择分开：十三资源先在十二资源包上只加 PAPPT；十四资源
再加一份显式 app。app 缺注册表或头描述文件时拒绝。需先恢复当前临时包，再生成：

```powershell
py -3.12 -B tools/prepare_steve_probe_overlay.py --head-descriptor-report build/steve-head-descriptor/steve-head-descriptor-report.json --part-table-report build/steve-part-table-v2/steve-part-table-report.json
py -3.12 -B tools/check_steve_probe.py --part-table --rebuild
py -3.12 -B tools/prepare_steve_probe_overlay.py --head-descriptor-report build/steve-head-descriptor/steve-head-descriptor-report.json --part-table-report build/steve-part-table-v2/steve-part-table-report.json --app-report build/steve-app-macduff-00000/steve-app-report.json
py -3.12 -B tools/check_steve_probe.py --app-variant macduff-00000 --rebuild
```

默认输出依次为 `build/steve-part-table-v2-probe-overlay` 和
`build/steve-app-macduff-00000-part-table-v2-probe-overlay`；原十一／十二资源包保留。安装仍通过
Steve 专用入口，并以完整 plan SHA／文件哈希绑定收据。十三／十四资源包当前完整
重建与事务检查状态见进度；未通过检查前不安装。初始 app 控制只用于当前已观察的
00000，不从静态存在推断 00002 已被当前身体使用。所有资源仅存本机 ignored build。

2026-10-08 已完成十三资源 **23/23**、十四资源 00000 **24/24** 的真实重建与隔离
安装／恢复检查；默认十一、十二分别 21/21、23/23 回归通过。随后十三包 v1 实测进入
闪退，已恢复且用户确认同一存档正常；旧十四包未安装，不能继续使用该失败注册表。
v2 只修新 part 行的组件列表，并在封装／安装入口与实际 prefab 交叉检查；原始行、
描述目录、其余资源和旧失败产物保持。新版完整检查及实机结果以进度记录为准，
静态修正不是闪退根因或显示成功的证明。当前实际收据及待恢复状态以
[current-state.md](current-state.md) 为准；不要同时安装两个包。

## 原生头网格单引用定位对照

十三资源 v2 的用户画面已出现 MC 块体，但位置错开，且仍有原版独立 Armor／Hair。
仅改初始 app 的十四资源包不会移除这些装备和发型，也不能直接验证模型定位。
当前先使用独立原生头对照：保留 v2 的私有 CD_Head prefab，只把 `_skinnedMeshFile`
从私有 Steve PAC 改回原生 `cd_phm_00_head_00_0001_macduff.pac`，实际完整路径见报告。

```powershell
py -3.12 -B tools/prepare_steve_head_mesh_control.py
py -3.12 -B tools/check_steve_head_mesh_control.py --rebuild
py -3.12 -B tools/prepare_steve_probe_overlay.py --head-descriptor-report build/steve-head-descriptor/steve-head-descriptor-report.json --part-table-report build/steve-part-table-v2/steve-part-table-report.json --head-mesh-control-report build/steve-head-mesh-control/steve-head-mesh-control-report.json
py -3.12 -B tools/check_steve_probe.py --native-head --rebuild
```

候选为 `build/steve-head-mesh-control/steve-head-mesh-control-report.json`，同一私有
prefab 路径、单 CD_Head、flags 0；1918→1921 字节，只改一条资源引用及其必需的
六个尺寸／指针字段。固定字节变换与 CDMW 独立正逆往返一致，结果还与原生 donor
首组件逐字相同。其余 shrink、owner、空骨架字段及 breath 脚本保持。

封装输出 `build/steve-native-head-probe-overlay`，仍是 13 项，只有一个 payload
改变；其余 12 项与 metadata-before 保持。入口必须同时有 v2 注册表及头描述文件，
与 app 对照互斥；通用资源入口仍拒绝重复路径。专用五报告集合同时绑定原 assembly
和覆盖候选，安装 variant 为 `steve-kliff-native-head-part-table-v2`，沿用原恢复事务。
当前完整检查、实际安装／恢复状态以进度和 current-state 为准。

预期只判断原生头的位置：若正确，优先查私有 PAC 及其资源链；若仍错位，优先查
共同的组件／descriptor 装配。该对照连带使用原生 PAC 自己的材质依赖，因此不能
仅凭结果把根因限定为骨权重。它不修身体、不隐藏装备，也不应作为 Steve 成品使用。

## 原生头模板与共同父骨的 Steve 候选

原生头引用实测已正常连接，测试后恢复完成。旧自建头使用身体模板的四 LOD、
palette slot8→Head93；原生头实际是三 LOD／节2、3、4，192项均为 B_face_com122
子骨，Head93 不在其中。独立候选保留原生结构，只把固定 slot0 的一个 hash 改为
共同父骨122，其余191项保持；替换全部脸几何，eyecover置空，MC头48点／24面
刚性绑定slot0。按真实 Head PABC 对该骨逆补偿并量化回放，保留 UV、表面和材质纹理。
这是一项明示的新绑定策略，不声称原 palette 完全不变或实际动画已验证。

```powershell
py -3.12 -B tools/prepare_steve_native_head_root.py
py -3.12 -B tools/check_steve_native_head_root.py --rebuild
py -3.12 -B tools/prepare_steve_probe_overlay.py --head-descriptor-report build/steve-head-descriptor/steve-head-descriptor-report.json --part-table-report build/steve-part-table-v2/steve-part-table-report.json --head-root-report build/steve-native-head-root/steve-native-head-root-report.json
py -3.12 -B tools/check_steve_probe.py --native-head-root --rebuild
```

前置为已核对的 assembly、头描述文件与PAPPTv2。生成入口从 `--game-root` 或
本机 installation.json 读取固定0009原生头，核对EXE、索引、精确路径、flags及哈希；
不依赖研究目录。原版资产及五份来源复制在 ignored `build/steve-native-head-root`，
其 `load_candidate` 无 CDMW 或游戏读取，并从这些固定来源重构 PAC／材质逐字准入。
输出目录存在时拒绝覆盖；需要另一份输出时使用新的 `--output`。

封装输出 `build/steve-native-head-root-probe-overlay`，variant为
`steve-kliff-native-head-root-part-table-v2`；仍13资源，仅覆盖私有头 PAC和对应PAMI，
其他11项保持。独立五报告集合同时保留旧assembly与新候选来源；与app及原生头引用
对照互斥，通用重复路径保护保持。只有游戏关闭后才能安装／恢复：

```powershell
py -3.12 -B tools/install_steve_probe.py --install --plan build/steve-native-head-root-probe-overlay
py -3.12 -B tools/install_steve_probe.py --restore
```

检查结果和实际收据以 [current-state.md](current-state.md) 为准。候选只验证头部路径，
仍须验收引擎蒙皮、表情、scale与实际位置；身体错位、装备、发型和持续外观未完成。

## 保留 MC 头几何的原生头 PAMI 单变量对照

此对照以固定 head-root 十三资源包为基线，只替换私有头 PAMI；三 LOD PAC 仍保留
真实 MC 头／帽的 48 点、24 面、公共父骨绑定及 UV。它暂用原生头材质和原生纹理
检查位置，最终 MC 皮肤、头身位置、动画、身体装配、原装备禁用及持续完整 Steve
仍未完成。本对照已实际安装并收到用户方块头位置正常的反馈，随后实际退出恢复；
位置结果来自人工观察，原服装仍与MC重叠，不等于完整Steve或某个shader字段已验收。

```powershell
py -3.12 -B tools/prepare_steve_head_native_material.py
py -3.12 -B tools/check_steve_head_native_material.py --rebuild
py -3.12 -B tools/prepare_steve_probe_overlay.py --head-descriptor-report build/steve-head-descriptor/steve-head-descriptor-report.json --part-table-report build/steve-part-table-v2/steve-part-table-report.json --head-root-report build/steve-native-head-root/steve-native-head-root-report.json --head-native-material-report build/steve-head-native-material/steve-head-native-material-report.json
py -3.12 -B tools/check_steve_probe.py --head-native-material --rebuild
```

生成器默认输出 `build/steve-head-native-material/steve-head-native-material-report.json`，
候选 variant 为 `steve-head-native-material-only-v1`。新输出目录必须不存在；已有产物
需要保留，另选新的 `--output`。原生来源为固定 0009 中
`character/modelproperty/1_pc/1_phm/head/head/cd_phm_00_head_00_0001_macduff.pac_xml`，
读取前后核对 EXE／索引 SHA、精确路径、flags 50 与原件 SHA。基线也必须通过固定
head-root 的纯 loader，并核对以下三项字节身份：

| 资源 | SHA256 |
| --- | --- |
| 保留的 head-root PAC | `182fc7385116a74536adf3f6603c057d4103f885bf1c6519d62d6689ea877660` |
| 被替换的 head-root PAMI | `442b56d40caf42e31f082123577483d195e107504a6cb85bcba556a3638c8ff9` |
| 新原生头 PAMI，16149 字节 | `440a9e68a2e1ef425d9eef90cb0c50895f6888cb01c301eb7f04efa8197ba9a5` |

原生 PAMI 保留 3 变体×2 draw 的完整原字节合同，每个变体都有 EyeCover 和主 draw：

| 变体 | EyeCover shader／参数数 | 主 draw shader／参数数 |
| --- | --- | --- |
| 0 | `SkinnedMeshEyeCover`／1 | `SkinnedMeshSkinWrinkle`／14 |
| 1 | `SkinnedMeshEyeCover`／1 | `SkinnedMeshSkinWrinkle`／14 |
| 2 | `SkinnedMeshEyeCover`／1 | `SkinnedMeshSkinWrinkleAging`／16 |

draw 名称、wrapper 元数据、全部参数及顺序、原生纹理和 wrinkle 引用逐字保持，
不序列化 XML，也不扩成上一份 Steve PAMI 的 6 变体。报告只有一项
`candidateResources`：虚拟路径为
`character/modelproperty/1_pc/1_phm/head/head/crimsonmc_steve_head_1_21_1.pac_xml`，
kind 为 `skinnedMaterial`，`payloadSize=16149`，两个 archive flags 均为 50；
`sourceVirtualPath`／`templatePath` 和 `templateSha256` 指向上述固定原生头 PAMI。

包内保存原生 PAMI、旧 PAMI、保留 PAC、固定 head-root 报告四份来源。
`load_candidate(report_path)` 返回 `(report, {virtualPath: bytes}, snapshot)`，
snapshot 使用绝对 `Path` key，直接兼容 `orientation.verify_snapshot`。纯 loader
只读这些包内来源和候选，从固定来源重构整个 manifest 并逐字比对，不加载 CDMW
或读取游戏，也不使用报告中的成功标记准入。2026-10-08 独立检查器含真实固定重建
**10/10**、完整封装及隔离安装／恢复／故障／重建检查 **28/28** 通过；这些检查未安装
实际游戏。PAZ 为 768912 字节，计划报告 SHA256 为
`991fa0fcf756bfec6138a3be13f651658721fb2a0a2b9f9e7dbe724871d39048`。

新封装默认输出 `build/steve-head-native-material-probe-overlay`，安装 variant 为
`steve-kliff-native-head-root-original-material-part-table-v2`。报告集合必须恰好包含
`steve-assembly-report.json`、`steve-appearance-report.json`、
`steve-head-descriptor-report.json`、`steve-part-table-report.json`、
`steve-native-head-root-report.json` 和 `steve-head-native-material-report.json`。
先应用 head-root 的两项覆盖，再只替换固定旧 SHA 的 PAMI；仍为 13 个资源，PAC 及
其余 11 项与 head-root 包逐字保持，原有 meshparam／PAPPT 两个旧路径覆盖范围保持。
缺头描述文件／注册表／head-root 或混入 app／head-mesh 时拒绝；通用重复路径保护保持。

完整事务通过并核实游戏关闭后，安装入口为
`install_steve_probe.py --install --plan build/steve-head-native-material-probe-overlay`；
测试后正常退出，仍用 `install_steve_probe.py --restore`。它沿用
`kind=steve-mesh-parameters` 的所有权／备份／收据和共享锁，恢复不覆盖安装后的最新
存档。2026-10-08 已实际安装，收据为 `5249d2f2339844f3a5b27b77d1353a66`；
before-install／installed 两阶段均 exit 0，41 项文件匹配，36 个最新存档、完整 schema3
MC 状态、原点和 ASI 保持。随后用户确认方块头正常连接在肩膀上方；实际退出后已恢复，
38项原文件、退出时36个最新存档、完整MC、原点及ASI保持，无active receipt／0041。
完整人物／动画／最终皮肤仍未完成；实际检查及恢复状态见
[progress.md](progress.md) 与 [current-state.md](current-state.md)。

## 默认服装空 Armor 的单变量对照

原字节头 PAMI 实测后，用户确认方块头正常连接在肩膀上方，同时反馈原服装与 MC
建模持续重叠。用户要求先去除原服装模块，再处理 MC 头皮肤。新对照以该已通过头
位置的十三资源为基线，只新增一份固定 00000 app 的默认 Armor 清空替换；不同时
修改皮肤、PAC／palette、骨架、身体、发须或 customization。

```powershell
py -3.12 -B tools/prepare_steve_clothing_control.py
py -3.12 -B tools/check_steve_clothing_control.py --rebuild
py -3.12 -B tools/prepare_steve_probe_overlay.py --head-descriptor-report build/steve-head-descriptor/steve-head-descriptor-report.json --part-table-report build/steve-part-table-v2/steve-part-table-report.json --head-root-report build/steve-native-head-root/steve-native-head-root-report.json --head-native-material-report build/steve-head-native-material/steve-head-native-material-report.json --clothing-report build/steve-clothing-control/steve-clothing-control-report.json
py -3.12 -B tools/check_steve_probe.py --clothing --rebuild
```

独立候选默认输出 `build/steve-clothing-control/steve-clothing-control-report.json`，variant
为 `steve-clothing-empty-default-armor-only-v1`；已有输出拒绝覆盖，另选新 `--output`。
来源固定为 0009 中
`character/appearance/1_pc/1_phm/cd_phm_macduff/cd_phm_macduff_00000.app_xml`，
原件 1117 字节、flags 48、SHA256
`945e25586db2d50a83b4dd5227ab89a8e5db8c7937abd404470e52ae5b9edffe`。
生成入口在读取前后核对固定 EXE／索引 SHA、精确路径、真实 flags 与原件身份，
不读取进程，不安装或改变游戏文件／存档／MC 状态。

唯一变换是删除原始字节区间 `[499,1093)` 的 594 字节：Armor 内 12 行 Prefab，
其中 8 行普通、4 行 `Preview=true`。`<Armor>`／`</Armor>` 保留为空；候选 523 字节、
SHA256 `2b172fc5e2287b9cb7afde9c1e03a0842f99d1ed15cd3518ee269f9a42cb17d2`，
flags 48。Nude／Head 的原名称、CharacterScale `1.02571`、HeadScale `0.92`、
Hair／Beard、Customization、BOM 与外部 XML／剩余 CRLF 全部逐字保持。候选不改
Nude／Head Name 为私有 basename；既有 meshparam 选择继续由十三资源基线提供。
插回固定 12 行即恢复完整原件，不通过 XML 重新序列化生成。

报告空 `candidateResources`、单项 `targetReplacements`，kind 为
`appearanceDefinition`、`templateArchiveFlags=archiveFlags=48`。包内只有原 app 模板、
候选及固定报告；纯 `load_candidate` 返回 `(report, {fixedAppPath: bytes}, snapshot)`，
snapshot 使用绝对 `Path` key。准入重构整份报告及精确删除结果，不加载 CDMW 或
读取游戏，不信报告中的成功标记；未知字段、路径越界、输出覆盖、模板或候选篡改
（包括同时重写内外哈希）、过大报告和失效快照均拒绝。

封装接口为 `clothing_path`／overlay 的 `clothing_report`，CLI 为 `--clothing-report`；
必须具备 head-native-material、head-root、head descriptor、PAPPT v2 全部控制来源。
十四资源的候选报告集合必须恰好是以下七项：

- `steve-assembly-report.json`
- `steve-appearance-report.json`
- `steve-head-descriptor-report.json`
- `steve-part-table-report.json`
- `steve-native-head-root-report.json`
- `steve-head-native-material-report.json`
- `steve-clothing-control-report.json`

原十三项的 payload／资源行逐字保持，包括已通过位置反馈的头 PAC 和原生 PAMI；
只增加这份固定 app 旧路径。纹理注册与原十三资源基线保持，不增加新的 DDS。
缺报告、未知／重复报告、混入此前两 Name 的 app 对照或原生 head-mesh 对照拒绝；
00002 不在此次候选内，通用新资产入口仍拒绝原 basename。默认封装输出为
`build/steve-clothing-control-probe-overlay`，安装 variant 为
`steve-kliff-original-material-empty-armor-part-table-v2`，沿用
`kind=steve-mesh-parameters` 的所有权／备份／共享锁／收据，不能与其他临时包并存。

2026-10-08 独立生成器检查（含真实固定重建）**10/10** 通过，报告 SHA256 为
`cca720b41ed2bdb8722e12d363e3e35e0788c57dc8b0ca9c8e1678456a86ac72`。
十四资源封装已构建，PAZ 769440 字节，计划报告 SHA256 为
`6703890ac16748566f54b5dfd81ff95ca68ead3d2ba41e2b59602704cc0dc319`；
完整隔离事务／重建检查 **28/28** 通过。专用安装／恢复入口为：

```powershell
py -3.12 -B tools/install_steve_probe.py --install --plan build/steve-clothing-control-probe-overlay
# 测试后正常退出游戏，再恢复；保留安装后的最新存档
py -3.12 -B tools/install_steve_probe.py --restore
```

随后主控重新核实上轮游戏已退出、无 active receipt、38 项原文件保持，完成
before-install 基线记录后实际安装。用户实测原话为“原服装消失，左手没有了。后背
背着的装备依旧存在并和身体重叠。头部过大”。默认服装抑制人工通过，完整人物
未通过。用户退出后核实会话结束并恢复；收据 `2feb0ddf41b3488fba9eb226cf8fb672`
为 restored，该服装会话恢复时无 active receipt／0041；随后进入下方身体材质对照。
五阶段均 exit 0，41 项安装文件／38 项
恢复原文件匹配，退出时 36 个最新存档、完整 MC schema3/revision25、原点及 ASI
保持；只读 appearance 双采样仍因原 PAC 声明空为稳定 notReady，不能当作完整模型
或遮罩解码成功。头部过大仍缺实际比例证据，本轮没有猜测缩头。

该 app 是共享初始外观资源，其全部消费者可能受影响。默认服装消失的人工反馈
不证明全部装备选择链已被抑制；动态穿戴部件可能由其他选择层再次应用，静态删除 12 行
不等于禁止全部红沙装备，也不删除装备库存／存档。发须、完整身体去重、动画和
跨重载持续 Steve 均未验收。MC 头贴图后续只计划替换三个主 draw 的 baseColor
路径，候选已在后文独立生成／封装；不与本轮服装变换混合。实际测试／收据及恢复
状态以 [current-state.md](current-state.md) 与 [progress.md](progress.md) 为准。

## 保留身体补偿 PAC 的原生身体 PAMI 单变量对照

服装实测留下左手缺失、背部装备重叠和头部比例问题。已有身体材质从原生
`SkinnedMeshSkin` 改成 `SkinnedMeshStandard`，这是一个已改变而未证明运行时语义
一致的变量。下一对照只把私有身体 PAMI 换成固定原件；保留其余 13 项资源，包括
空 Armor 和身体 PAC，暂用原生身体纹理诊断左手／身体，不混入头缩放或 MC 皮肤变换。
头材质的历史人工位置结果不能直接证明身体 shader 是唯一根因。

```powershell
py -3.12 -B tools/prepare_steve_body_native_material.py
py -3.12 -B tools/check_steve_body_native_material.py --rebuild
py -3.12 -B tools/prepare_steve_probe_overlay.py --head-descriptor-report build/steve-head-descriptor/steve-head-descriptor-report.json --part-table-report build/steve-part-table-v2/steve-part-table-report.json --head-root-report build/steve-native-head-root/steve-native-head-root-report.json --head-native-material-report build/steve-head-native-material/steve-head-native-material-report.json --clothing-report build/steve-clothing-control/steve-clothing-control-report.json --body-native-material-report build/steve-body-native-material/steve-body-native-material-report.json
py -3.12 -B tools/check_steve_probe.py --body-native-material --rebuild
```

候选默认输出 `build/steve-body-native-material/steve-body-native-material-report.json`，
variant 为 `steve-body-native-material-only-v1`；已有输出拒绝覆盖，另选新 `--output`。
只替换私有路径
`character/modelproperty/1_pc/1_phm/nude/crimsonmc_steve_body_1_21_1.pac_xml`，原件来自
固定 0009 中 `character/modelproperty/1_pc/1_phm/nude/cd_phm_00_nude_00_0001.pac_xml`。

| 固定身份 | SHA256 |
| --- | --- |
| 覆盖前身体 PAMI | `01f17ad65bf24e4d8ce59bec0de2c9d3cf570992101a67ac2e0ac94ce52d0538` |
| 原生身体 PAMI，50017 字节／flags 50 | `65b217b938346cc47c1207263507eaef38a24ad605f2890a4b0845c9005fc7a4` |
| 保留的补偿身体 PAC | `8f26d6ceb38768be8b933067a53cb3a5cb1170a13b8f287cc4159f865b1e4537` |

原 PAMI 为 6 变体×3 draw，三个名称为 `cd_phm_00_head_0001_01`、
`cd_phm_00_nude_0001_hand`、`cd_phm_00_nude_0001`，各 wrapper 均使用
`SkinnedMeshSkin`。候选逐字复制完整原件；保留所有参数及其顺序、wrapper、纹理、
damage／wrinkle 引用、BOM 与换行，不重序列化或删去没有几何的 wrapper。
实际 PAC 的 draw／蒙皮语义不能由原件复制证明；本次左手和观测姿势身体显示的人工
结果见下方记录，完整MC动作仍须另验。

生成入口读取前后固定 EXE／0009 索引，提取并核验精确 PAMI 的 SHA／长度／flags。
同一原索引内有界确认 22 个真实纹理条目（flags 1）和 1 个 wrinkle 条目（flags 50），
连同 PAMI 共 24 个唯一条目；只核对依赖路径、真实 flags、PAZ 存在和原归档边界，
不提取／解码依赖载荷、不导出它们，也不声称引擎已经解析。原
`texture/nonetexture0xffffffff.dds` sentinel 保留，不要求归档条目，运行时回退未知。
报告没有动态 PAZ／offset，不重复打包原生纹理。

报告仅一项 `candidateResources`，kind 为 `skinnedMaterial`、`payloadSize=50017`，
`templateArchiveFlags=archiveFlags=50`；`sourceVirtualPath`／`templatePath` 和模板 SHA
均指向原生 PAMI。包内四份固定来源是原 PAMI、覆盖前 PAMI、保留 PAC 与 assembly
报告。纯 `load_candidate` 只用这些字节重构整份报告及原件载荷，返回报告、单私有
PAMI 字典与绝对 `Path` key 的六项快照；不读取游戏／进程／CDMW，不信成功标记。
路径越界、未知字段、覆盖已有输出、报告／来源／载荷篡改和失效快照均拒绝。

封装接口为 `body_native_material_path`／overlay 的 `body_native_material_report`，CLI 为
`--body-native-material-report`。必须具备前节完整空 Armor 七份报告，再增加唯一
`steve-body-native-material-report.json`；严格八报告、仍十四资源，与此前 app／
head-mesh 对照互斥，缺依赖或混入未知报告拒绝。覆盖顺序是 head-root、原生头 PAMI、
空 Armor，最后仅身体 PAMI；其余 13 项 payload／资源行保持，包括当前身体 PAC、
空 Armor 和头 PAC／材质；纹理注册不变。新增材质双 flags 为 50，封装核对真实模板 flags，
安装独立核对精确载荷及 PAMT 实际 flags，不放开通用重复路径规则。

默认封装输出 `build/steve-body-native-material-probe-overlay`，安装 variant 为
`steve-kliff-original-head-body-material-empty-armor-part-table-v2`，沿用 Steve kind 的
所有权／备份／共享锁／收据；恢复不覆盖后来存档，不能与其他临时包并存。
2026-10-08 独立检查含真实固定重建 **10/10** 通过，候选报告 SHA256 为
`485e0b529cf096b3c2568bdbfdf8a66aedeffae626f2fe031d65aff1741ce55c`。
完整封装／隔离事务／真实重建 **28/28** 通过；仍 14 项，PAZ 770800 字节，计划
报告 SHA256 为 `fa1f38ec686644fdebeddd53ad09429aab87083495da12155b5b6f3248b8e341`。
专用安装／恢复入口为：

```powershell
py -3.12 -B tools/install_steve_probe.py --install --plan build/steve-body-native-material-probe-overlay
# 实测后正常退出，再恢复；保留退出时最新存档
py -3.12 -B tools/install_steve_probe.py --restore
```

主控核实游戏实际关闭、无 active receipt、38 项原件保持后，已实际安装此身体材质包。
收据 `069425c3a6a0430fa9c576e3afe8f20b` 现为 restored，variant 为上述身体原件对照；
before-install／installed 两阶段均 exit 0，41 项安装文件、36 个存档、完整 MC
schema3/revision25、原点及 ASI 保持。用户已手动进入并反馈“左手出现、身体和四肢
没有错位，没有无关，同时身上还背着装备”；随后确认“是，头部没有五官”。本次人工
通过仅限左手可见和观测姿势下身体／四肢对齐，头部没有脸部图案，背部原装备仍可见。
头比例、最终MC皮肤、MC动作、背部装备移除与全部原装备禁止未验收。

主控in-world记录41项安装文件匹配、完整MC／原点／ASI保持；视觉结果报告绑定本次
收据、计划SHA和同一会话，并保存原话及澄清。只读owner目录完整20项、primary RTTI
仅6项观测、14项未解析，双采样稳定；同会话render-input-paths双采样稳定但notReady。
这些读取不识别背部资源或证明逐成员owner回链，不构成删除装备或写存档的依据。
原始证据为ignored `runtime/steve-body-native-material-20261008-visual-result.json`、
`...-owner-components.json`、`...-render-input-paths.json`，公开交接保存摘要而不上传原始进程数据。
整体PAMI合同变化不能进一步归因于单个shader字段。用户正常退出后主控核实进程结束，
before-restore／restored均exit0，38项原文件、退出时最新36个存档、完整MC／原点／ASI
保持，恢复时无active／0041。随后安装下一头贴图包，最新终态以
[current-state.md](current-state.md) 与 [progress.md](progress.md) 为准，不复用旧会话地址。

当前状态以 [current-state.md](current-state.md) 与 [progress.md](progress.md) 为准；
生成器成功与历史头位置反馈不能替代这次身体材质的实机验收。


## 保留原生头材质合同的MC主颜色贴图候选

身体材质对照等待人工反馈期间，离线完成下一项独立候选；没有覆盖当时安装包。

```powershell
py -3.12 -B tools/prepare_steve_head_basecolor.py
py -3.12 -B tools/check_steve_head_basecolor.py --rebuild
```

默认输出 `build/steve-head-basecolor/steve-head-basecolor-report.json`，variant
`steve-head-basecolor-only-v1`。已有输出拒绝覆盖，另选新 `--output`；来源可用
`--head-material-report`及`--assembly-report`显式选择，仍须固定完整纯准入。
原件SHA `440a9e68a2e1ef425d9eef90cb0c50895f6888cb01c301eb7f04efa8197ba9a5`、16149字节。
只改三个主draw的 `_baseColorTexture` 路径byte spans [1406,1455)、[6516,6565)、
[11631,11680)，改为 `character/texture/crimsonmc_steve_1_21_1.dds`。新件16134字节SHA
`cc86b387583430d7e2d8ef136db965dd39d3e5754501626b7c82fa606b2abf3f`；候选spans
[1406,1450)、[6511,6555)、[11621,11665)逆替换逐字恢复原件。其余全部字节及3变体×2draw、
EyeCover、Wrinkle／Aging shader、参数／ItemID／flags、其他纹理、BOM／CRLF保持。

四份包内固定来源为原PAMI、当前头PAC、已有DDS和原生头材质报告；完整canonical报告
由这些字节重构，pureloader返回单头PAMI资源与6项绝对Path快照。来源DDS SHA
`653aa5d14644e515da6284fecd65711fae65a187323697a1b571dbbab74a6b1a`、87536字节，保留
256×256 DXT5九mip，全部载荷字节范围核对。它是已有固定MC皮肤编码依赖，不新增
candidate resource，也不将BC3说成无损；此工具不重编码PNG或读取游戏／CDMW／网络。
保护原输入及已有头／衣服／身体对照包，未知字段、路径／flags／type／duplicate、
来源／候选／报告改hash篡改、source race、输出覆盖／交叠均拒绝。

2026-10-08独立检查含真实纯重建10/10通过；报告36429字节SHA
`56d0ee077c290395c6efcc013c1c48524fe0db1af5c3bea6137d01a944c9f466`，37项原输入快照保持。
独立只读QA核对当前身体14资源包中同DDS唯一flags0、decoded字节一致和PATHC直接注册。
这些归档事实不证明新头PAMI已被引擎读取或最终MC皮肤正确。新候选接入独立九报告
本地封装；身体单变量对照现已完成人工反馈／只读采样与正常退出恢复，头包随后才
实际安装，没有在待反馈期间撤换或重新安装。

### 固定身体计划的本地九报告封装

独立 `prepare_steve_head_basecolor_overlay.py` 与 `check_steve_head_basecolor_overlay.py`
负责本地组合及隔离事务；默认输出 `build/steve-head-basecolor-probe-overlay`。
默认正式包已构建，完整隔离检查31/31通过；独立构建与检查入口为：

```powershell
py -3.12 -B tools/prepare_steve_head_basecolor_overlay.py
py -3.12 -X utf8 -B tools/check_steve_head_basecolor_overlay.py --rebuild
```

封装可用 `--baseline`、`--head-basecolor-report`、`--output`、`--cdmw-source`、`--deps`
显式指定，已有输出必须拒绝覆盖；没有 `--game-root`。它只读取ignored中的固定
身体计划、全部6份包／元数据文件、canonical八报告和头baseColor候选，不读取实际
游戏metadata，也不调用通用game-based prepare；`prepare_steve_probe_overlay.py`
的构建CLI保持旧接口。完整封装仍使用固定CDMW源门禁及离线打包函数；单PAMI生成器
不读CDMW，不能据此声称整个归档封装无CDMW。

身体基线 overlay-report SHA256必须是
`fa1f38ec686644fdebeddd53ad09429aab87083495da12155b5b6f3248b8e341`，恰8报告／14资源，
各实际文件哈希和来源快照一致。原34项 `sourceIndexes`、5个未安装可选目录
0036～0040和3项 `replacementPaths`逐项保持。原8项控制全集加
`steve-head-basecolor-report.json`构成唯一允许的9报告模式，不接受部分控制或与app／
head-mesh混用；缺依赖、错误名称和未知／歧义报告组合必须在来源读取前拒绝。

在完整身体基线上最后调用 `apply_head_basecolor`：旧头PAMI `440a…`／16149／flags50、
头PAC `182fc7…`／flags1及DDS `653aa5…`／87536实际载荷固定，只有新头PAMI
`cc86b3…`／16134字节／flags50进入精确10字段行，并可逐字逆恢复。
既有assembly DDS行不含 `archiveFlags`；完整baseline row和真实PAMT entry必须验证
DDS恰一次、flags0、载荷不变及既有PATHC直接注册，不能重复加DDS或继承模板flags1。
其他13项编码载荷、flags、orig_size和完整资源行全部保持。

原metadata-before两文件及PATHC-after保持原字节。只有头PAMI重新压缩／加密产生
新PAZ／PAMT后，PAPGT-after从原before和实际新PAMTCRC重算；不能复制旧PAPGT-after，
也不能把当前已安装身体包的metadata-after用作新安装before。完整新包重新解包、
审挂载和注册并重构manifest，不只沿用旧审计bool。发布前后复验所有来源与6文件
快照；独立build输出拒绝覆盖、交叠、链接和路径逃逸，不写当前实际0041或收据。
默认正式输出的子目录或祖先也拒绝，不能在既有计划目录内嵌套生成或用祖先覆盖它。

`install_steve_probe.py` 已接严格9报告入口，正常资源／flags／挂载／注册审计后再
执行 `validate_composition`，冻结固定身体基线和整包变化范围并合并快照。variant为
`steve-kliff-original-head-body-material-empty-armor-head-basecolor-part-table-v2`。
既有active拒绝、关闭游戏、原始vanilla元数据精确匹配、真实原索引全集／hash检查、
共享锁、所有权、存档备份和可逆恢复全部保留；不会为当前active状态放宽安装门禁。

独立checker仅其新类对当前production metadata／active receipt／installed文件作
前后不变核对，从原34份PAMT实际只读复制fake fixture并执行产品 `audit_sources`，
不mock真实来源门禁；test21走本地compose，原默认全套不变。
主控实际构建exit0：默认包14资源／9报告、PAZ770800字节，计划SHA256
`29b813224b362f8d2e751a8ae31968846a55d96410f290ffd10deb00322078e5`；
包／挂载／注册三项审计通过，新9报告标准loader与旧8报告模式准入均通过。
主控按上述完整checker命令重跑exit0，31/31通过，219.466秒，production快照和
cleanup均无异常。
身体材质对照已正常退出恢复后，主控实际安装该九报告头贴图包，收据
`bbdda1c5304f4cfe884a1e8ca1fdeed6` 现为restored，variant为上述head-basecolor模式。
before-install／installed均exit0，41项安装文件、36个存档、完整MC schema3/revision25、
原点／ASI保持。用户手动进入反馈“头部没出现正确的史蒂夫五官、
头的位置仍正常”：本次位置人工通过，正确MC头皮肤未通过，头比例、alpha及光照仍未验收。
in-world recorder exit0，41项安装文件、完整MC／原点／ASI保持，本次原生身份与会话
记录一致；render-input双采样稳定但notReady，PAC/PAB声明不完整，不能证明新PAMI／
DDS实际读取或渲染采样。独立视觉记录绑定本次收据、计划和会话，保存于ignored
`runtime/steve-head-basecolor-20261008-visual-result.json`；不能从这次失败推定某个shader
或贴图为唯一根因。用户正常退出后主控核实进程结束，before-restore／restored均exit0，
38项原文件、退出时最新36个存档、完整MC／原点／ASI保持，当前无active receipt／0041。
该会话已结束，不能复用PID／地址。最新终态见 [current-state.md](current-state.md) 与
[progress.md](progress.md)。

## 固定MC算法的离线姿态基准（2026-10-08）

`tools/StevePoseDump.java` 实际调用固定MC 1.21.1 PlayerEntityModel 的animateModel／setAngles，
不是仿写三角公式。正常构造ArmorStandEntity为显式离线输入夹具，非Player、World=null、
不tick，不使用Unsafe或覆盖getter；逐帧前后核对8个真实状态字段。仅支持未骑乘、
未蹲伏、未攻击、空手、未游泳／飞行的standing／look／walk三种有界输入。

```powershell
py -3.12 -B tools/build_steve_pose.py
py -3.12 -B tools/check_steve_pose.py --rebuild
```

默认 `build/steve-pose-1.21.1` 已构建，拒绝覆写；重建检查使用独立build目录。固定官方client
及21显式算法类、46外部JAR、Java工具；复制已校验依赖到独占stage后编译／运行。各41帧，
六个root子部件的原始9字段／FloatBits及TRS完整输出，注明度／弧度、像素／米、坐标基、
ZYX旋转与独立rendererRootScale。步态覆盖40tick＋endpoint，age同时驱动手臂idle bob，
不声称全身所有部件在endpoint闭环。9/9真实重建通过，两独立JVM逐字一致。
poses SHA为 `0302fd9021bc0bd31eb5b51478cb6512f8fcb7b053ed32458ed0fe6c6d8b0855`。
来源报告与产物保持ignored，仓库只发布自己的调用／检查工具。此三组基准不覆盖挥击、
蹲伏、跳落或持物；新增部分前置见下节，nativeApplied／animationSystemComplete=false。

## 蹲伏／挥击模型样本与真实玩家状态前置（2026-10-08）

新增工具保持上述六项旧来源／产物原字节。固定29个MC类、46个外部依赖、Java工具及
官方mapping；所有依赖SHA256与旧基准对应记录一致，不以当前读取摘要替代固定来源。

```powershell
py -3.12 -B tools/build_steve_action_pose.py
py -3.12 -B tools/check_steve_action_pose.py --rebuild
py -3.12 -B tools/check_steve_player_context.py
py -3.12 -B tools/check_steve_player_context.py --run
```

动作输出默认`build/steve-action-pose-1.21.1`，已生成，构建拒绝覆写；`--output`可指定
新ignored目录。真实官方模型求值43次：model_crouch一帧，固定右主手MAIN／OFF各21个
指定progress点。9/9独立JVM重建通过；六部件原始字段／FloatBits及TRS保留，OFF是左副手，
不是左主手实体；左右结果不强制镜像。model.sneaking只是模型输入，实际ArmorStand仍
为STANDING／isInSneakingPose=false，null-World不支持本次真实CROUCHING切换，失败夹具
不复用。progress为float32(index/20)，不宣称时长、完整tick或真实玩家时间序列。

玩家上下文默认命令只preflight；`--run`在独立8768/25580世界编译并正常构造ServerPlayer，
与inventory／equipment／block-state检查串行。固定本地named MC jar须已存在；工具不下载。
`tools/player_context_fixture/`仅注入owned runtime/build，不更改生产Authority或build.gradle。
实际25项通过：左右主手、sneaking／CROUCHING、状态恢复、八次官方protected tickHandSwing
进度推进回零，class codeSource为固定named jar。没有注册PlayerManager、生成实体或连接
客户端，没有完整tick／20Hz生命周期／前帧复制；不能据此宣称客户端动画或攻击已实现。
报告写入完成marker后runner才读取，finally通过自有进程stdin正常stop，前后核对生产
minecraft/src与build。初始实验及tracked路径验证分别保留独立runtime目录，均正常退出。

后续完整入口采集使用`py -3.12 -B tools/check_steve_player_tick.py --run`；默认不带`--run`
仍只preflight。独立world九块stone地板上自然落稳，按每server tick顺序调用完整
world.tickEntity／player.playerTick；前者复制位置并推进age，后者推进实际人物物理、
Pose和挥击。11次暖机后四组32帧（站／蹲×MAIN／OFF），年龄12..43，包含每帧真实
delta0/.5/1插值。精确ServerPlayer与正常handler／connection不接传输、不注册／生成实体，
网络包只进入自身队列，实测4项；不手写age／velocity／onGround。两入口各43次均完成，
首次及tracked路径验证均正常console stop，源码／build保持。完整连接生命周期仍未覆盖。
采集证据分别为`runtime/mc-player-tick-4tm1bcz6`与`runtime/mc-player-tick-uxn5vmag`。
真实玩家状态→模型回放已在下列固定输入范围接通；持物、跳落、红沙姿态控制及伤害／
击退继续单独验收。
实际工具源码可上传，MC二进制、世界和输出保持ignored。

```powershell
py -3.12 -B tools/build_steve_player_pose.py --source runtime/mc-player-tick-4tm1bcz6
py -3.12 -B tools/check_steve_player_pose.py --source runtime/mc-player-tick-4tm1bcz6 --rebuild
```

此回放是本机固定capture基准，`--source`只接受上列成功目录及固定两JSON／ticket／六份
producer源码摘要，不能替换为任意fresh run。默认`build/steve-player-pose-1.21.1`已生成，
不覆写；需新输出时使用`--output`。32个after帧×delta0/.5/1共96次官方模型求值，真实
progress／isInSneakingPose／age及MathHelper角度映射保持。限定空手RIGHT、静止站／蹲、
MAIN／OFF；模型夹具仍为null-World ArmorStand，不能声称执行Player renderer或披风。
8/8检查通过（16.853秒），一次独立JVM的pose／class／完整report逐字一致；79项快照和
旧12工具／产物保持。poses SHA `9bf389fdb3eb34dfcee9b558df55138fbcf7d037b4d5287b8ae819c718d8a3a0`，
report SHA `77dc04a8dd90b23765485298e4430ec2513d6c94c1212fb252314e555ffdb9c7`。
结果证明真实状态到官方六关节的离线转换；实时帧服务、原生重定向、装备和攻击仍未实现。

## 头主UV方向单变量候选（2026-10-08）

`prepare_steve_head_uv_control.py` 只从已准入head-baseColor候选读当前PAC／PAMI／DDS／报告，
无游戏／CDMW读写。PAR有界解析固定三LOD各48条40字节记录，主UV为+8／+10；cloth-guide
sentinel等字段保持。唯一变更是LOD起点90529／92593／94657下各48个half V→1−V，共144
个两字节span、实际144字节改变；逐字逆恢复源PAC182fc…，全部其他字节／材质／纹理保持。

```powershell
py -3.12 -B tools/prepare_steve_head_uv_control.py
py -3.12 -B tools/check_steve_head_uv_control.py --rebuild
```

默认ignored目录 `build/steve-head-uv-control` 已生成，pureloader四来源／6包内文件摘要固定。
PAC96721字节、flags1、新SHA `c0df7b6e6fbe90038b8e277839ef59b26aa4cbba560f30770d82eec9acf50b55`。
独立重建11/11通过；独立MC accessor／PAR／half映射、BC3脸部特征区域、逆恢复、非V／
改hash篡改和输出保护覆盖。直接DDS行序采样旧脸区域全透明，翻V后的区域有眼鼻嘴；
CDMW本身也翻V，该约定不能排除shader内部再反V。integration全false，主UV选择、
shader／alpha／normalframe、最终MC五官未验。孤立PAC不可单独安装；其14资源／严格10报告
封装见下节，实际五官仍需人工验证。

## 头UV十报告可逆封装（2026-10-08）

`prepare_steve_head_uv_overlay.py` 从固定九报告本地计划29b813…组合，不读取游戏元数据。
只有头PAC从182fc…替换为c0df7…；另外13项完整资源行、编码payload、flags、orig_size保持。
metadata-before与已注册纹理PATHC逐字保持，PAMT与PAPGT按实际CRC重建；全归档逐字重建
排除额外条目及尾部数据。候选固定56790…，新`headUvComposition`保存基线及当前变更范围。

```powershell
py -3.12 -X utf8 -B tools/prepare_steve_head_uv_overlay.py
py -3.12 -X utf8 -B tools/check_steve_head_uv_overlay.py --rebuild
# 仅主控完成检查、核实游戏退出及原资源基线后安装
py -3.12 -X utf8 -B tools/install_steve_probe.py --install --plan build/steve-head-uv-probe-overlay
```

默认输出拒绝覆写，为`build/steve-head-uv-probe-overlay`，14资源／严格10报告，PAZ770800字节。
计划SHA为`b27484b952059015920635a23cf489a2881d23ba86e554b0b80f7157a03e7c10`；variant为
`steve-kliff-original-head-body-material-empty-armor-head-basecolor-head-uv-part-table-v2`。
安装器对10报告启用独立完整重建校验，原九报告及其他历史模式保留。源34索引、关闭游戏、
active收据互斥、所有权、存档备份及恢复门禁不变。实际检查与安装终态见
[current-state.md](current-state.md)；封装成功不证明MC五官、shader采样或头比例。

## 固定头PAMI文件读取诊断（2026-10-08）

新增 `tools/probe_steve_head_material.py` 与独立checker；在已准入九报告或十报告包实际安装、游戏
运行且固定EXE／实例成立时，读取唯一别名steve_head_pami，物理路径含两层head/head。
完整固定plan／14资源/PAMI及active收据／marker／41实际安装与原索引文件必须匹配。
两计划分别固定完整SHA、variant和报告集合，不允许串用收据；十报告通过完整新封装校验。
保留16KiB双native尺寸、flags50、队列／TTL／handler释放，POST持久化且不重发，完整MC
状态前后核对；不提供任意路径、DDS／PAC读取或外观刷新。

```powershell
py -3.12 -B tools/check_steve_head_material_probe.py
# 仅主控在新的真实安装／运行会话中执行，证据必须用新路径
py -3.12 -B tools/probe_steve_head_material.py --output runtime/steve-head-material-read-new-session.json
# 十报告UV对照必须显式指定其计划
py -3.12 -B tools/probe_steve_head_material.py --plan build/steve-head-uv-probe-overlay --output runtime/steve-head-uv-material-read-new-session.json
```

最初九报告隔离客户端21/21、原生23/23、旧客户端27/27通过，ASI已构建并更新实际安装及发布artifact。
本次扩展九／十报告客户端后46/46通过，82.870秒，覆盖跨计划／variant／收据拒绝及未提交保证；
两计划PAMI相同，原生别名与已安装ASI未变。
此诊断已在十报告UV对照中首次实采成功：16134字节、flags50、stored1694、head16及
FNV `3a4d0e960a22bdf3`匹配，ticket1一次提交／读取，handler释放，前后同实例和完整MC保持。
用户仍反馈五官不正确、头位置正常；之后正常退出并恢复，五阶段exit0，无active／0041。
fileResolvableReadMatched只能证明引擎文件解析读取字节匹配，不能证明renderer实际选择
该PAMI或采样DDS，MC皮肤和原生shader语义仍须实测。

## 固定透明帽层的单变量几何候选（2026-10-08）

当前头main draw每LOD同时包含base24顶点与hat24顶点，各36索引；EyeCover没有几何。
独立BC3核对得到六个hat区域共6144texel全RGBA0，六个base区域各1024texel全alpha255，
原生SkinWrinkle的alpha／混合规则没有实机证据。因此下一控制只移除固定Steve透明帽面，
不把遮挡假设记录为根因，也不改变材质参数。

```powershell
py -3.12 -X utf8 -B tools/prepare_steve_head_visible_layer.py
py -3.12 -X utf8 -B tools/check_steve_head_visible_layer.py --rebuild
```

候选基于固定UV头PAC c0df…、PAMI cc86…、DDS653…及56790…报告。每LOD删除末36个
hat索引（72字节），main计数72→36、PAR section2064→1992，同步三LOD的绝对位置镜像；
全部48×40字节顶点记录、前36个base索引、palette、UV、皮肤权重、法线、切线、边界及材质
保持。总长度96721→96505，恢复时插回固定216字节索引尾并逆转字段，逐字回到c0df…。
保留原边界为保守包围盒；没有通过退化三角形模拟删除，也没有留下未说明的section间隙。

默认输出`build/steve-head-visible-layer`，报告`steve-head-visible-layer-report.json`；
variant为`steve-head-fixed-transparent-hat-triangles-removed-v1`，单一PAC／flags1，新SHA为
`7c222d1cb2d475d7e487c8cad87967afc63d27a1fa14b99d35c62a24f762d9ca`。
生成时核对固定官方glTF的head／hat UV及各自canonical quad索引，并用固定CDMW读回三LOD；
不声称PAC索引直接等于glTF顶点重排后的三角映射。pureloader从四份固定复制来源完整重建
报告／候选，返回绝对Path快照，不读游戏或调用CDMW。实测、材质采样与安装字段全false。
尚需接入严格11报告／14资源封装，证明其他13资源保持并检查安装／恢复后才能安装。
canonical报告34472字节，SHA `6d68aa3eff9428fe9f7c63838fdbed10097a4c17ef0da940648b24ea972e6501`。
独立重建12/12通过（10.781秒），覆盖全部12元数据字段（其中2项位置未变）、三LOD原始
记录及索引边界、独立BC3／MC accessor、真实CDMW及保守bbox、完整逆恢复、来源／manifest
篡改、输出保护和源变化拒绝；纯准入返回六个绝对Path快照。

## 透明帽层十一报告整包（2026-10-08）

`prepare_steve_head_visible_layer_overlay.py`从固定十报告b27484…本地包组合，仅把头PAC从
c0df…替换为7c222d…；其他13项完整资源行、编码payload、flags和orig_size保持。
metadata-before和PATHC保持，PAMT与PAPGT按新归档实际CRC重建。顶层使用独立
`headVisibleLayerComposition`，旧UV变换通过固定基线来源保留，不沿用为当前变更断言。

```powershell
py -3.12 -X utf8 -B tools/prepare_steve_head_visible_layer_overlay.py
py -3.12 -X utf8 -B tools/check_steve_head_visible_layer_overlay.py --rebuild
# 主控完成全套检查并重新核对进程／原文件基线后才能安装
py -3.12 -X utf8 -B tools/install_steve_probe.py --install --plan build/steve-head-visible-layer-probe-overlay
```

默认输出`build/steve-head-visible-layer-probe-overlay`，14资源／严格11报告，PAZ770576字节。
计划17784字节，SHA `e86048837217e7cd85ac957d12db2b05b3315449234e8639668ebf627665add1`；variant为
`steve-kliff-original-head-body-material-empty-armor-head-basecolor-head-uv-visible-layer-part-table-v2`。
生成器无game-root参数，不读取实际游戏元数据；旧模式准入、安装时源34索引／原metadata／
进程关闭／active互斥、备份与恢复门禁保持。完整检查及实机状态见[current-state.md](current-state.md)。

安装器每次准入现在返回独立`readSnapshot`，包括本次manifest／六文件及全部候选和基线来源。
同一路径不同字节立即拒绝，metadata二读须一致，返回前完整回读；不跨调用缓存，也不把
Path→bytes快照序列化到报告或收据。新11层复用一次完整10层准入的快照，避免为了收集来源
再重复全部解析；旧9／10封装算法和固定报告没有改变。

头PAMI读取客户端分别固定9／10／11计划SHA和variant，69/69隔离检查通过（134.101秒）；
每一对计划／variant／收据串用都拒绝，依然仅steve_head_pami／16KiB／flags50，ASI不变。
新包实采必须显式指定：

```powershell
py -3.12 -X utf8 -B tools/probe_steve_head_material.py --plan build/steve-head-visible-layer-probe-overlay --output runtime/steve-head-visible-layer-material-read-new-session.json
```
