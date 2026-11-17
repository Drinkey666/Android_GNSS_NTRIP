# PPP NTRIP Android 项目规则

## 接手入口
- 实际根目录是 E:/android/test/PPP_NTRIP，对应 PC 工程 E:/GNSS/PPP_NTRIP_PC。
- 新任务先读本文件和 docs/CURRENT_STATE.md，再核对当前 Git 和所改模块。
- 精度/PC 候选任务再读 E:/GNSS/PPP_NTRIP_PC/docs/CURRENT_STATE.md 及所指的单项报告。
- 详细历史按需查 docs/PPP_INVESTIGATION_INDEX.md。旧台账、README_NTRIP 和 CODEX_HANDOFF_20261018 的阶段状态可能过时。
- 本范围只接续 NTRIP 分支之后，不自动回到 PPP_only、FTPGet 或旧 rtklib_Project2 开发。
- 旧 AGENTS 原文归档于 E:/GNSS/PPP_NTRIP_PC/docs/handoff_archive/20261107/android_AGENTS.original.md。

## 定位与模块
- App 同时进行 WHU SSR PPP、原始 GNSS/三流留档与 PC 因果复核。
- applicationId 为 com.example.pppntrip，Kotlin namespace 仍为 com.example.ftpget。
- app/src/main/java/com/example/ftpget/ 中 LiveSsrSession.kt 串行调用 JNI。
- NtripClient/NtripCaptureService/NtripCaptureStore 管理三流、服务、到达/应用顺序和 ZIP。
- GnssDataLogger.kt、RinexConverter.kt 管理 Raw 与 RINEX，参考坐标用于误差显示。
- app/src/main/cpp/gnss_jni.cpp 为在线桥，ntrip_ssr.cpp 为 SSR 缓存和保护。
- 现行共享核心只在 app/src/main/cpp/ppp_live/rtklib/，勿与旧 cpp/rtklib 混用。
- CMake 目标 gnss_ppp_live 启用 PPP_NTRIP_SSR，rtklib_engine 事后入口不启用。
- LivePppProducts、BundledProducts、AntennaProductVersion 管理产品准备和版本检查。
- UI 遵守本项目 .agents/skills/material-ui，使用 Compose Material3 和资源字符串。

## 开发约束
- 正式链为 SSRC00WHU0(CoM) + OSBC00WHU1，广播 BCEP00BKG0，预报 IONEX/VMF3。
- 广播转发源不等同精密改正中心。正常在线入口保持 NTRIP，不改成文件精密产品模式。
- 保留 B_VERIFIED、非组合、Joseph 及现有 R/Q/P0/GIM/抗差，模型研究先在 PC 独立配置验证。
- 用户明确禁止后续考虑双频无电离层组合（IF/IFLC），包括定位、研究候选及以旁路诊断/对照名义使用双频消电离层组合。后续坚持非组合模型、显式处理电离层；已有结果只保留为历史。
- PC 的 B1C/零状态/无两次300s等待候选尚未自动部署到本 App。
- 不用未来改正，不给 GPST 加8小时，不重打 SSR 时标、放宽过期/IOD/来源或补零缺失偏差。
- 保留 WHU 独立 OSB 的专门来源/连续性检查，精度好不等于绝对有效期已认证。
- FIXED_CLOCK_2023 固定每个真实钟段首个有效 FullBias/Bias，单星 ADR reset 不重置公共钟。
- 不恢复旧50μs重复修正，不隐式整秒对齐、100ms合并或重写历史 Raw。
- Native 零值哨兵/异步观测限制、100ms发送时标冲突和GAL7Q ADR/PRR问题须明确记录。
- 原 API 字段、ADR/PRR符号、真实零值/缺失、LLI及信号身份需要逐行可追溯。
- Raw实验预处理默认关闭，候选不能未经验证送入正式PPP。
- 完整保留 Raw、三流、到达/应用 ledger、clock anchors、实际产品快照、软件指纹和停止排空流程。
- 旧V1严格UTC校验与V2处理序列分别维护，不静默修正旧包时间。
- 原始数据、失败反例、旧哈希清单与报告保留。新回放目录不覆盖旧证据。
- 不 reset/clean/整树覆盖他人修改。安装 APK 和清手机数据仍按各任务的授权范围执行。
- 用户已授权每次本项目对话交付时，将该轮新增或改动的项目源码、测试、文档和可分享验证产物提交并推送至 [Android_GNSS_NTRIP](https://github.com/Drinkey666/Android_GNSS_NTRIP) 的 main。核对远端提交后，用 GitHub 提交级文件链接交付。有只读结论时可归档报告；无新增或修改文件的对话沿用相关文件链接。
- Android 源码进正常目录；无 Git 的 PC 工程通过 Android 仓库中对应日期的 docs 归档发布代码快照和可分享证据。只暂存本轮指定文件。连接凭据、原始采集包、个人 APK 和精确参考坐标留在本地。
- 凭据仅忽略的 local properties 注入个人Debug，release默认空，不打印/入包/提交/公开个人APK。
- 既有授权在任务范围内沿用，具体真机操作须区分构建、已安装和已验证采集。
- 对设备当前版本做结论时须重新读实际APK指纹，不能沿用旧“已安装/未授权”条目。
- 同期测量型接收机数据已确认没有，不重复等待或用手机状态冒充独立真值。
- 精度按具体采集的WGS84参考和高程基准统计，保留启动段、无解与Q5。
- 仅用E盘并控制产物体积，不重复复制Raw/产品，不无限录流。
- 无子代理，除非用户或适用项目规则明确要求。

## 构建与验证
- 使用工程 Gradle Wrapper 8.11.1 和 Android Studio/SDK 支持的 JDK。
- .\gradlew.bat :app:testDebugUnitTest --console=plain 执行 JVM 测试。
- .\gradlew.bat :app:assembleDebug --console=plain 构建APK，构建不等于安装或精度验收。
- :app:testClasses 只是到 compileDebugUnitTestSources 的兼容别名，不执行测试。
- Maven Central 当前配置 Google 镜像，既有403修复保留原依赖坐标和版本。
- 共享C/C++采用 NFREQ=4、ENAGLO、无ENAQZS，保持相同状态布局和 signed-char。
- verify_ppp_profile.cmake 校验33项 ntrip_profile.sha256，保留旧父工程清单的历史含义。
- 核心改动先验证PC/Android内容和历史基线，再更新真实pin，不关闭校验或批量盲同步。
- 共享结构修改后完整重建所有受影响的ABI/调用方。
- 历史 verify_observation_generation_ntrip.py 可能绑定旧APK/文档SHA，先检查适用快照。
- 新改动运行相关测试，保存本轮结果。历史通过数和UP-TO-DATE不得冒充新执行。

## 持续维护
- 重要阶段结束后更新 docs/CURRENT_STATE.md，覆盖过时事实并给出精确证据路径。
- 已完成/已排除/候选未部署/尚未解决分别写清，不逐轮追加聊天摘要。
- 共享核心或部署状态变化时，同时检查PC交接文件是否需要更新。
- 本轮上下文整理完成后停止，业务开发由用户后续任务恢复。
