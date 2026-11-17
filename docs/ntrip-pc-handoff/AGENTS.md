# PPP NTRIP PC 项目规则

## 接手入口
- 实际根目录是 E:/GNSS/PPP_NTRIP_PC，对应 Android 是 E:/android/test/PPP_NTRIP。
- 新会话先读本文件和 `docs/CURRENT_STATE.md`。核对实际根目录、分支/HEAD、已暂存和未暂存变更；PC 无 Git 时，核对与当前任务相关的源码、二进制和证据 SHA。
- 以源码、Git、测试和日志为当前事实。遇到交接冲突，按对应输入和版本核实；无法取得的证据明确标记。接手审阅结束后按本轮用户授权决定是否继续开发。
- 只读当前任务涉及的源码、报告和日志；新增实验前先查索引，已有证据可解释当下问题时直接复用。
- `docs/PPP_INVESTIGATION_INDEX.md` 提供实验索引，`docs/PPP_INVESTIGATION_LEDGER.json` 是历史证据台账，其顶层日期和“当前”字段可能过时。
- README.md 中早期 BKG 默认、仅采集、尚无 PPP 输出等叙述已被现行源码与 CURRENT_STATE 取代。
- 聊天默认的 E:/GNSS/rtklib_only/rtklib_only/rtklib_Project2 是旧工程，不在此修改或接续 NTRIP。
- 原 PPP_only、FTPGet 仅为参考源，本范围限 NTRIP 分支后的工作。

## 定位与模块
- 本工程为 Windows 手机 Raw/TXT + 同期 NTRIP 三流的严格因果 PPP 回放和验证工具。
- core/ 为共享 C 解算内核、观测生成、RTCM、产品检查及诊断。
- src/ntrip_ssr.cpp/.h 管理解码、缓存、WHU 来源/参考、IOD、时标及有效性。
- src/pc_ssr_replay.cpp 管理到达前缀、应用顺序与回放保护，src/gnss_replay.c 为观测和解算入口。
- tools/ 管理录流、导入、构建和分析，tests/ 为定向回归，validation/ 保存可复核证据。
- config/caster_whu.json 为现行 WHU 配置，旧 caster.json/BKG 示例不代表当前默认。

## 运行约束
- 正式产品链为 SSRC00WHU0(CoM) + OSBC00WHU1，广播 BCEP00BKG0。
- 电离层/对流层使用匹配的预报 IONEX/VMF3，流中有轨钟不等于含完整大气改正。
- 正式基线沿用 B_VERIFIED、非组合、Joseph 及现有 R/Q/P0/GIM/抗差。
- 禁止提出、实现或运行双频无电离层组合（IF/IFLC），包括旁路诊断和对照。坚持非组合模型、显式电离层和浮点模糊度，禁止推进模糊度固定（AR）。旧结果按历史范围保留。
- 参考坐标只用于解后评估，按采集包绑定椭球高/正常高和参考位置；禁止参与在线估计、权重和参数反馈。
- 所有变更先区分正式路径与独立实验，研究候选通过 PC 验证后才考虑移植 Android。
- 不把私有 B1C 联合、零状态修复或无 300s 等待候选描述成已部署正式版本。
- 不预加载未来 SSR，不给 GPST 加 8 小时，不静默平移时刻、重打时间或放宽过期/IOD/来源保护。
- WHU 独立 OSB 有专门来源和连续性规则，不恢复错误的统一同 IOD/90s 假设。
- 零码偏差与缺失码偏差必须区分，不补零、混中心或自动外推过期 OSB。
- 已确认的旧 ANTEX 身份、CODE IONEX 几何/约定、BDS 时标/布局修复应保留。
- 坐标接近真值、Q6 多或 PSD 通过均不足以证明物理模型正确。
- 只统计最终成功提交，区分试更新、编辑重试、Q0/Q5/Q6 与真实/虚拟观测。
- 原始 Raw、SSR、产品及失败证据保留，旧结果不覆盖，回放使用独立输出目录。
- 不重做已经有保存结果的 P0/R、DOP、删星、平滑或启动试验，除非输入/代码改变或有明确新问题。
- 本机仅写 E 盘，避免复制大产品/捕获目录及无限录流。只清理本轮可恢复副本，压缩须核对解压哈希。
- 凭据仅本地忽略文件/会话使用，不打印、写入交接或提交，不公开个人 Debug APK。
- 用户已授权每次本项目对话交付时，将该轮新增或改动的项目源码、测试、文档和可分享验证产物提交并推送至 [Android_GNSS_NTRIP](https://github.com/Drinkey666/Android_GNSS_NTRIP) 的 main。核对远端提交后，用 GitHub 提交级文件链接交付。有只读结论时可归档报告；无新增或修改文件的对话沿用相关文件链接。
- Android 源码进正常目录；无 Git 的 PC 工程通过 Android 仓库的 docs 发布可分享文件。阶段证据按日期归档，PC 交接入口镜像在 `docs/ntrip-pc-handoff/`。只暂存本轮指定文件，遵守当次发布范围。连接凭据、原始采集包、个人 APK 和精确参考坐标留在本地。
- 安装 APK、清手机数据、回滚他人改动仍按各任务的授权范围执行。
- 不 reset/clean/整树覆盖，不绕过来源清单。旧清单按其历史快照解释。
- 共享头/结构变更须完整重编译调用方，先读 Android 的 AGENTS.md，再同步真实源码哈希。
- Native 零值哨兵/异步观测限制、100ms 发送时标冲突、GAL7Q ADR/PRR 不一致仍需明确保留。
- 缺少同期测量型接收机数据已有用户确认，不反复索取或假造独立真值。
- 用户倾向程序/估计问题，本轮以放置和参考条件固定为前提，不自行转回摆放试验。
- 无子代理，除非用户或适用项目规则明确要求。

## 构建和检查
- 本机 VS2022 Professional + MSVC x64，tools/build.py 记录开发环境路径。
- NFREQ=4、ENAGLO、PPP_NTRIP_SSR、TRACE，禁用 ENAQZS；C/C++ 状态布局必须一致。
- 正式构建及原生回归运行 .\build_pc.cmd --test，会重建 build/、bin/ 并更新 validation/build.json。
- Python 回归运行 .\tools\plot_venv\Scripts\python.exe -X utf8 tools/run_ntrip_python_regressions.py；按用户约束排除历史 test_ntrip_continuous_code.py 的消电离层诊断，未执行项不计为通过。
- CMakeLists.txt 为另一构建入口，是否验证须按真实日志说明。
- 回放使用 replay_txt.cmd，导入使用 import_android_capture.cmd，输出目录须尚不存在。
- 修改前读相关测试和验证器。verify_isolation.py 比较分叉前快照，可能因已知后续修复报错，不盲跑或改 pin 放行。
- 只读分析优先复用已有 summary/矩阵，历史通过数不冒充本轮重新执行。
- 工作区无 Git 时用源码/输入/产物 SHA 与独立输出保护，不能声称工作区干净。

## 维护交接
- 重要阶段结束或任务转向后维护 `docs/CURRENT_STATE.md`。更新核验时点、两端版本与改动、最后完成节点、剩余问题、下一步及验收条件。
- 替换过时状态，已解决事项移入已验证工作，已失败方案留简短排除索引。
- 明确区分正式源码、构建、真机部署、隔离实验及推测。验证记录写清回放口径、测试是否本轮执行及未验证项，并链接底层证据。
- 变更共享文件时同时检查 Android 当前状态，避免两端交接与实际源码漂移。
- `AGENTS.md` 仅维护长期规则，`CURRENT_STATE.md` 就地更新当前事实。详细历史留在原报告，状态文件按任务提供最小阅读索引。
- 2026-11-07 合并前原 AGENTS 全文和 SHA 保存在 docs/handoff_archive/20261107/。
