# Steve 动画 A/B 离线检查的手动启动

## 当前只需执行这一条新复核命令

保持红沙关闭，在**普通PowerShell**粘贴下面一条命令，不需要管理员权限：

```powershell
& 'C:\Users\ASUS\AppData\Local\Programs\Python\Python312\python.exe' -I -S -X utf8 -B 'C:\Users\ASUS\Desktop\CrimsonMC\build\steve-paa-motion-pack-20261013\run_next_review.py'
```

这一步只读取实际安装／当前存档／MC／备份，运行独立13项包测试并再次核对保护快照。
只在工程build内写日志和测试夹具，不安装、不恢复存档、不启动游戏，不重跑44项、不执行PAAcodec。
等出现`PASS: independent 13/13`或报错后，把最后几行告诉主任务；不要同时开游戏或再开一份测试。
日志自动保留在`build/steve-paa-motion-pack-20261013/next-review-attempts/<UTC>/`。
若解释器启动前就报错，该目录可能没有新记录；保留PowerShell错误原文，不更改ACL或安全设置。

工具环境已经读回实际41文件并与f616收据逐项匹配；随后current save目录读取被WinError5拒绝，
所以完整保护快照仍未通过。这是需要手动普通PowerShell接续的具体原因，不要求重复点击批准弹窗。
首次restore前还需另做最新存档／生产MC世界的新备份；此只读步骤不会替代该备份。

2026-10-13终态：用户已执行成功，A/B实际生成，44/44隔离事务通过，05:26:51Z exit0；不要重复运行已完成批次。
batch-result.json passed=true，源码／五固定输入保持，completion-readback.json七项通过。下方启动命令保留作执行记录。
启动前诊断：
当前 Codex 执行上下文读取固定 Python EXE/DLL 和 LZ4 缓存时返回 WinError 5；
普通工程源码、固定69a计划及PAA原件可读取。升级工具只返回 aborted，没有审批／会话 ID。
这不足以区分宿主 Windows ACL 与执行环境隔离，不修改任何权限或安全设置来尝试修复。

## 已修复的代码问题

批处理先构建A/B，随后测试又调用只允许干净进程的 `native.load_cdmw`，必然触发
`CDMW was already imported`。现改用 `bootstrap_backend`，仍核已载模块来源、固定源码摘要及依赖版本。
另增加最外层启动日志，捕获原来位于main内部try之前的解释器校验、源码和依赖导入错误。
八项纯标准库诊断通过，含控制台断管时保留日志及SystemExit(None)正常退出；未加载归档backend或执行完整批处理。

固定Python3.12依据是原有执行来源合同和保存记录中的 `_block.cp312-win_amd64.pyd`。
当前PATH中的MinGW Python3.14不是可直接替代的运行时。本轮没有重新核验被拒绝读取的DLL／WHEEL。

## 在普通 PowerShell 中执行一次

无需管理员模式。下面两行仅记录输出并启动同一已审阅脚本；若仍拒绝访问，保留错误后停止，
不改ACL、不换解释器、不关闭安全设置。此操作由用户自行执行，不代表Codex已获得或绕过审批。

```powershell
$motionLaunchLog = 'C:\Users\ASUS\Desktop\CrimsonMC\build\steve-paa-motion-pack-20261013\manual-launch-' + (Get-Date -Format 'yyyyMMdd-HHmmss') + '.log'
& 'C:\Users\ASUS\AppData\Local\Programs\Python\Python312\python.exe' -I -S -X utf8 -B 'C:\Users\ASUS\Desktop\CrimsonMC\build\steve-paa-motion-pack-20261013\run_offline.py' 2>&1 | Tee-Object -FilePath $motionLaunchLog
```

脚本读取已固定的本地资源及归档库，只在 `CrimsonMC/build` 创建A/B包、日志和临时fake-game／save副本。
测试包含副本写入、故障注入、文件锁、build内部链接拒绝及临时目录清理；不读写正式安装或用户存档，
不启动游戏／MC、不访问网络、不下载软件、不重跑PAA codec，也不上传工程。
耗时取决于归档校验和磁盘速度，不要因短时间没有测试汇总就重复启动。

## 如何判断执行到了哪里

- PowerShell立即报拒绝访问且没有新 `attempts/<UTC>/run-state.json`：未得到解释器进入脚本的证据。
- 出现新 `attempts/<UTC>/console.log` 和 `run-state.json`：解释器已进入；失败异常和exitCode在其中。
- 出现 `resource-work/plan-a`、`plan-b`：只能说明已有包产物，还须看验证结果。
- `batch-result.json` 中A/B各22项、failures/errors为0且 `passed=true`，才算该批隔离检查通过。
  `checks-a.log`／`checks-b.log`保存逐项结果。既有结果和部分包不自动覆盖；失败后由主控检查并使用新证据目录修复。

完整批处理已通过；独立13项包复核另有已准备脚本，仍未执行。
离线通过也不代表游戏接受动画、已选中当前walk clip或MC走路已应用；实际A–B–A观察另行协调。

## 安全进入实机前的下一步

先对已生成A/B执行 `independent-review/review_packages.py` 的13项包复核，包含A/B混report／encoded载荷、
metadata重算自报SHA以及旧14项同decoded但换encoded的拒绝测试；使用独立新输出目录，不重建A/B，不重跑codec。
随后由主控重新核游戏已关闭、EXE版本、实际source indexes／metadata、原0041归属、active f616收据、最新存档／MC及备份。
本批对这些真实保护对象没有fresh hash，只有runtime收据只读仍登记installed，不能跳过现场核对。

实际序列为标准恢复旧f616→新收据安装A1→正常退出恢复→新收据B→正常退出恢复→新收据A2；
每段相同Steve／装备／镜头／起点，站2秒、W10秒、松开2秒，保留录制；最终按需要恢复原14项Steve包为新有效收据。
不叠0042，不手改收据，不恢复旧saveBackups；崩溃／严重变形停止B，进程结束后标准恢复，不强杀或自动重试。
B独有变化且A2返回只证明资源视觉影响；无变化或条件不一致记不确定，不能扩大角度、扫描范围或声称MC动作完成。
