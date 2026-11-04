# Android GNSS 观测生成修复移植至 NTRIP（2026-10-30）

已完成目标工程源码移植、四 ABI APK 构建、目标工程测试和一次既有真实 WHU SSR+Raw 的 701 历元回放。没有安装 APK、连接手机、录制新数据、提交或推送。没有修改 PPP 模型及 R/Q/P0/GIM/抗差/Joseph 参数或实现。本次修复不是约 9 m 高差的完整解决方案。

## 1. 基线保护和修改范围

两个活动目录均返回 `fatal: not a git repository`，因此无法给出 Git 未提交文件列表，不能将其解释为“工作区干净”。修改前保存了 342 项源码/工具指纹，备份拟修改文件、旧 PC EXE、旧 APK 和原清单；后续增加的 PC ledger 文件也在修改前备份。未整目录复制参考工程，未替换整套 RTKLIB。

备份及证据主目录：`E:/android/test/PPP_NTRIP/tools/observation_generation_ntrip_20261030/`。

- `before.json`、`before/`：修改前原件、SHA256、大小和路径；包含原 APK/EXE。
- `source_inventory_before.json`：旧源文件审计范围；最终只读核验见 `verification.json`。
- `android_port_final.patch`、`pc_port_final.patch`：被修改旧文件的差异。
- 原 `pc_profile.sha256` / `pc_snapshot.json` 为历史父工程快照，原样保留；不得再将它们误认成现行 NTRIP 源码清单。
- 现行构建校验使用 `ntrip_profile.sha256`（32→33 项）；新增 `ntrip_observation_snapshot_20261030.json` 同时记录当前真实原始字节 SHA 和归一化 SHA。另外 29 项原生内核 pin 保持不变。关闭校验或跳过不匹配的做法没有采用。

### Android 实际源码

|文件（均位于目标工程）|函数/作用|
|---|---|
|`app/src/main/cpp/gnss_jni.cpp`|`ClockHistory`、`normalize_clock()`（162）、`read_clock()`（174）、`read_measurements()` 的 Tx presence（254）、`nativeProfile()` 的版本标记（515）；保留所有 SSR 专用函数|
|`app/src/main/cpp/ppp_live/rtklib/gnss_raw.h`|闰秒、归一化钟段标记、Tx presence；原 API 时间字段仍保留|
|同目录 `gnss_clock_reference.h`（新增）|溢出检查、整数/分数纳秒运算、`gnss_clock_reference_apply()`|
|同目录 `gnss_adapter.h/.c`|时钟上下文、`gnss_adapter_clock_time()`（113）、`gnss_adapter_convert()`（128）；信号/波长、ADR 弧段、异步限制|
|`app/src/main/java/com/example/ftpget/ObservationClock.kt`（新增）|Kotlin 同约定钟段、GPST/BDT/GLO、日期闰秒和 Raw 辅助 UTC|
|同目录 `RinexConverter.kt`|`convert()`（184）、`processEpochs()`（238）、`parseLine()`（601）及动态 RINEX 头/正文/审计；该模块差异全部属于观测转换，核对后移植完整模块|
|同目录 `GnssDataLogger.kt`|只替换 `formatMeasurementToCsv()` 的辅助 UTC 算术及列1说明；采集/停止排空/回调观察者不变|
|`app/src/main/cpp/tests/verified_device_replay.cpp`|测试辅助 Raw 解析器同步 presence/严格数值与 HCDC 分组，Android 使用 `strtoll`；不是 App 生产入口|
|`verify_ppp_profile.cmake`、`ntrip_profile.sha256`、新增快照 JSON|校验真实 33 项源码|
|`app/src/test/.../ObservationGenerationTest.kt`、`FullBiasConversionAuditTest.kt`（新增）|确定性用例，五份真实 Raw 转换及源行审计|

另新增只读验收工具 `tools/verify_observation_generation_ntrip.py`，保存目标测试探针、目标编译日志及结果。参考 `FTPGet`、`PPP_only` 本轮均只读。

### PC 必要同步

`E:/GNSS/PPP_NTRIP_PC`：

- `core/gnss_raw.h`、`gnss_adapter.h/.c` 和新增 `gnss_clock_reference.h`：与目标 Android 逐项核验一致。
- `src/gnss_replay.c`：只适配严格 Raw 解析、固定钟段归一化、HCDC 分组和缺基准等待；保留原 SSR CLI、流准备、到达顺序和全 WAIT 失败保护。
- `tools/android_ledger.py`、`tests/test_android_ledger.py`：按录制 `profile.txt` 的显式 `OBSGEN_POLICY=FIXED_CLOCK_2023` 校验新包。无标记的历史包继续原历史规则；未知版本拒绝。原 10 μs 关联容差、到达 seq/elapsed 因果限制均不变。旧 50 μs 函数仅用于认证旧包，不再参与新观测生成，也不叠加到新时标。
- `bin/ppp_ssr_replay.exe` 及依赖全部重新构建；修改前 EXE 已备份。PC 自己的 AGENTS 已先读取。

## 2. 钟段、符号和时间约定

```
tRx_ns = (TimeNanos - FullBias_ref) - Bias_ref + TimeOffsetNanos
P_m = c * wrap(tRx_in_constellation - ReceivedSvTimeNanos)
L_cycle = ADR_m / lambda_actual_signal
D_Hz = -PRR_mps / lambda_actual_signal
```

连续硬件钟段固定首个有效 FullBias/Bias，不随新的 API bias 估计改变。新会话、HCDC 改变、硬件 TimeNanos 回退或显式确认事件重建；新参考未到时保持 pending，不借用旧段。单星 ADR RESET/SLIP 只切分相应信号弧段。`reference_segment` 防止 JNI/回放 provider 与 adapter 重复应用。

64位整数先相减，再处理 Bias/TimeOffset 的小数纳秒；不先转为大 double。GPS/GAL/QZSS 使用 GPST 周边界；BDT=GPST−14 s；GLO 使用实际 FDMA 频道及 UTC+3 h 日边界。优先有效 API 闰秒，否则按日期表；不对历史日期一律套18 s。没有给 SSR 加8小时，没有重写改正时间或新鲜度。

VALID+RESET/SLIP 当期不再输出连续 L；pending reset 等有效新相位/所需码恢复后传递。半周未解为 LLI bit1，重启/状态转换为 bit0，可同时存在。负相位保留，Doppler 不取绝对值。PRR/ADR及不确定度缺失或坏格式不会填0冒充有效数据。真实零值与缺失在 Kotlin/RINEX 中有 presence；Native 旧结构的零值限制见第6节。

RINEX 按实际 TimeOffset 时刻输出，只进行其格式的100 ns舍入，不整秒对齐、不100 ms合并、不用 Doppler传播。动态信号数、固定宽度字段、LLI、重复记录整行选择及源行映射均已测试。默认 `applyLegacyQc=false`，旧经验预处理不暗中进入默认转换。

Raw 仍为54列，原 API 字段2–53保留原映射；未来记录辅助 `utcTimeMillis` 补上 GPS→Unix 起点差，并保留分数纳秒计算，使用当期 API 估计而非固定参考。该辅助列不参与 P/L/D/RINEX 时标生成；历史 Raw 未改写。

目标工程保留了 `outputDirectory`、`RawEventDrain`、`clockObserver`、`eventObserver`、IO错误与停止排空逻辑，没有覆盖成参考工程的文件采集器。目标中未发现“采集码相预处理（实验）”生产分支，本轮也未移入参考工程的 `CaptureCodePhaseRepair`/`CodePhaseCandidate`。参考旧实验不因此自动获得固定钟段同步，不能作为 PPP 候选改正使用。

## 3. NTRIP/SSR 保持情况

对342项旧源码/工具的差异白名单核验通过。以下源码未改：NTRIP连接/鉴权/挂载点/重连，`ntrip_ssr.cpp/.h`，`pc_ssr_replay.cpp/.h`，RTCM解码，IOD/缓存/有效期，GIM/CODE约定，PPP状态生命周期、模型、抗差、Joseph与参数配置。原生观测入口三份旧文件是明确授权的改动，不能要求整个解算轨迹逐位不变。

新增 profile 标记只用于解释新观测生成版本及录制包时间校验；不改变产品来源，不用 SP3/CLK/BIA 替代实际 WHU SSR。

## 4. 目标工程测试及同输入观测验证

这些是本轮在目标源码上新执行的结果，不是引用参考工程测试通过记录：

|检查|结果|
|---|---|
|观测生成 Native 确定性测试|51通过，0失败；使用目标 adapter 和从目标 `gnss_replay.c` 原样提取的解析器|
|PC既有原生回归|579 SSR + 40因果时序 + 15滤波安全 + 121 GIM几何 + 13偏差参考 = 768通过|
|Android实际原生源码的MSVC SSR测试|579通过；独立输出目录，不覆盖历史测试证据|
|PC Python|42通过（原35 + 新增7个版本化ledger用例）|
|目标 Android JVM|162报告，158通过，4跳过，0失败/错误|
|Android|arm64-v8a、armeabi-v7a、x86、x86_64的 CMake/Native 构建及 Debug APK 打包成功；受头文件结构变化影响的 live/postprocessing 调用方重编译|
|可选设备回放测试源码|四ABI语法编译通过；未在手机执行。首次适配编译发现测试解析器的Windows函数名/缺少split函数，已修正并保留首次失败日志|

51项涵盖连续bias变化固定参考、HCDC/会话/pending、单星reset不影响其他卫星、分数纳秒/周日/BDT/GLO/闰秒、负L/D符号/零值/缺失、半周/切换/重复、异步拒绝和数值解析。JVM还覆盖动态7信号/28观测类型及实际接收时刻。4项跳过为3个可选网络 smoke 和另一个未设置环境变量的旧单文件 RINEX 测试；本轮五Raw专项和FullBias专项均实际执行。

五份原始文件共4971个回调、351032行，338516条受支持原字段/时间/符号核验，278486条 Native/Kotlin共同身份行、850604项RINEX数值检查全部通过：

|数据|回调|Native共同身份行|RINEX数值检查|LLI差异|
|---|---:|---:|---:|---:|
|K70 early|709|38447|125314|142|
|K70 late|660|36244|112405|68|
|K70 10/21|1341|86346|255536|358|
|K70 10/25 文件产品采集|1560|83009|254616|76|
|10/25 实际 NTRIP 采集|701|34440|102733|82|

共同P精确一致，L最大差9.1e−13 cycle，D按Native float量化后差≤5.1e−10 Hz。726处LLI差异均限于BDS 1P/2I竞争同一Native槽：Native按最终选槽维护弧段，RINEX独立保存各实际信号。没有声称两者全信号行集合和LLI序列完全相同。

修改前对照使用备份的真实旧 adapter、解析器及50 μs归一化器重新生成；没有用新实现模拟旧算法。共同保留L数值和D不变，L数值变化只来自RESET/SLIP当期移除；通用观测生成增加GLO行单列统计，不代表正式PPP已启用GLO。

256 ns事件共同连续P/L样本的 `ΔP−λΔL` 中位数：early（23对）−76.867887→−0.121018 m，10/21（35对）−76.797280→−0.050410 m。真实NTRIP Raw的29086条共同P行变化约−76.746869 m，来自固定参考不再采用更新256 ns的FullBias；1915条旧RESET/SLIP相位不再输出。此公共码变化大多可进入接收机钟差，不能直接解释为同量坐标改善。

## 5. 真实WHU录流回放

输出：`E:/GNSS/PPP_NTRIP_PC/validation/observation_generation_ntrip_20261030/`，包括命令、solution/observations/stat/trace、corrections和 `replay_comparison.json`。

输入仍为 `RawData_20261025_140605.txt` + 原已接收WHU轨钟/OSB/广播三路及原到达/处理ledger。Raw SHA仍为 `f92b7bbb9d5c7a4defacd5b717af3c46f18ef318040c75230ee0722e9ffec0c7`。大气预报、官方ATX、B_VERIFIED配置与既有 `code_ionex_geometry_fix_20261027/auto_official` 控制相同；复用该保存控制，不重新跑历史精度排查。

- 701输入、478有效解；223 Q0 / 1 Q5 / 477 Q6，与保存控制逐历元Q相同。
- 701期实际释放记录数和改正就绪原因一致，最大GPST变化256 ns；旧录制包本身的原ledger校验仍通过，未改写任何原包字段。
- 新的观测时间能与旧ledger的既有10 μs关联规则匹配；未扩大容差。未来新包由明确profile标记采用固定参考校验。
- 有效输出状态/坐标有限；trace未出现NAN_INPUT/NAN_STATE/NAN_COV/NON_PSD/FILTER_ERROR或OBS_TIME_CONFLICT。不是另外导出每期完整P矩阵再独立特征分解；协方差保护由原正式安全路径及回归核验。
- ARC_RESET日志行1386→2249，这是ADR事件正确转发后的预期行为变化；日志行可含重试，不能等同独立周跳次数。
- 末点坐标变化ENU约[−0.020447,+0.002395,−0.020389]m；整段最大绝对变化[0.048078,0.046527,0.216791]m。
- 末点椭球高468.855635→468.835246m；与原确认参考459.813m仍约+9.022m。不能声称本次已解决主高差，也不以末点改善决定是否采用正确观测定义。

## 6. 已知限制与尚未完成

1. **固定参考没有解决100 ms发送时标冲突。** K70 late仍有11条 `CODE_TIME_OUT_OF_RANGE`；保留Raw、明确原因及可用L/D，不通过重锚公共钟或强行对齐掩盖。
2. **GAL7Q部分原始ADR/PRR仍不一致。** 四个既有文件中百米量级差异在本轮目标转换核验中保持，没有改频率、拟合趋势或强迫L/D闭合。该限制不等于所有信号都异常；NTRIP这段没有对应的GAL7Q统计组。
3. `obsd_t`同星只有一个时间；选中同星多信号接收时刻不同则明确 `OBS_TIME_CONFLICT`，不做异步伪对齐。不同卫星的原TimeOffset保留。此次实际SSR Raw TimeOffset为0；不将该回放冒充非零异步全系统PPP验证。
4. RTKLIB以L=0/D=0为缺失哨兵。Kotlin/RINEX可表达合法零相位/零D，Native明确记录零L表示限制；没有扩展整个PPP观测结构解决零值presence。
5. 钟参考以各入口**实际会话起点**为准。全文件RINEX与较晚才初始化的live会话不能默认拥有相同首锚点；本次真实回放同会话数据已实际匹配。未来记录需核对profile、`OBS_CLOCK_REFERENCE`和clock_anchors，不能静默移动时标。
6. 没有安装新APK，没有修改后室外采集、JNI真实Android对象/设备回调验收；四ABI构建、主机测试与旧Raw回放不替代这一项。

参考工程旧实验、旧文件产品模式及原调查结论均保留；本轮完成观测移植后停止，不开展新的抗差或PPP参数实验。

## 7. 构建、复核和接续

现行APK：`E:/android/test/PPP_NTRIP/app/build/outputs/apk/debug/app-debug.apk`，SHA256 `874f9500a9835e86ba4f1de0478f974f7fdbb243ef5f9a2e5d10a5b17ee5e31d`，**未安装**。

PC EXE SHA256：`9e47e0019a89cc8ac86f77de2447db9312646f94193ceb08d71c55b7f0fded6c`。

在目标Android目录用 `E:/GNSS/PPP_NTRIP_PC/tools/plot_venv/Scripts/python.exe tools/verify_observation_generation_ntrip.py` 可只读复核当前源码/清单/结果。源行证据位于主目录 `raw_validation/`，保留原始行号、原/参考F/B、纳秒及分数、钟段、信号、P/L/D/LLI和无效原因；`delivery_manifest.json`登记交付文件SHA。

需重建时：PC目录运行 `tools/plot_venv/Scripts/python.exe tools/build.py --test`；Android设置JAVA_HOME到Android Studio jbr后运行 `gradlew.bat :app:testDebugUnitTest :app:assembleDebug --offline --console=plain`。完整五Raw测试需同时设置 `OBSERVATION_GENERATION_OUTPUT` 为本轮 `raw_validation`、`FULLBIAS_AUDIT_DIR=E:/GNSS/PPP_only/validation/fullbias_reference_v1`；这些命令会生成测试输出，先选新的独立证据目录，避免覆盖当前交付。Native51探针构建脚本保存为 `raw_validation/build_probes.cmd`，源解析片段须随生产解析器变更刷新，不能拿旧探针冒充当前结果。

旧数值调查索引/台账已追加本次正式观测修复记录，旧轨迹标为旧观测生成管线下的历史证据，未删除其有效结论或重新执行精度消融。
