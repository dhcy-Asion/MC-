# MC 与红沙原生资产：可复建的离线管线

2026-10-07。离线准备工具已生成并检查真实资产，输出留在忽略上传的 `build/`。
后面的临时探针另有可恢复安装与实机步骤，当前验证结果见进度文件。正式桥接仍使用
蓝色方块代理，受控角色仍是原角色；候选资产不等于全部 MC 内容或 Steve 模式已接通。

## Steve 的原版几何

```powershell
python tools/build_steve_asset.py
python tools/check_steve_asset.py
```

复用哈希固定的官方 MC Java 1.21.1 客户端，调用真实模型构造。输出
`build/steve-1.21.1/steve.gltf`、顶点二进制、64×64 皮肤及来源清单。
六个刚性关节、外层、UV、绕序、逆绑定矩阵和原版渲染比例经过 13 项检查。
官方资源缺失时可使用 `--download` 获取固定依赖，不能随意更换客户端版本。

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
当前没有已验收的 Steve 游戏内显示、装备覆盖或实际外观恢复；临时共享资源包也
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

安装器仅允许原两个报告或加上这一个固定报告；缺报告、多资源、错标志或字节变化
均拒绝。对照收据的 `probeVariant=steve-kliff-head-descriptor-v1`，沿用
`kind=steve-mesh-parameters`、原 Steve owner 和恢复事务，绑定完整包报告及安装哈希。
独立头描述文件的 8 项检查通过；对照包的完整事务结果见进度。
实际试验时使用 `install_steve_probe.py --install --plan build/steve-head-descriptor-probe-overlay`；
退出后仍用 `install_steve_probe.py --restore`，不覆盖后来存档。
该包尚待游戏内显示验证，不代表已实现 Steve 或已确认故障原因。
