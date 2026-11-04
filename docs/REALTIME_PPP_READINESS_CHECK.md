# 实时 PPP 离线核验与待验收边界（2026-10-24）

## 结论

实时解算代码已经接入，不只是录流：Android Raw 回调 → LiveSsrSession 单线程队列 → JNI → gnss_adapter → NtripSsr::prepare → rtkpos → pppos → B_VERIFIED 的 Joseph 更新和提交检查 → 界面及留档。WHU 轨钟、独立码偏差、广播星历和预报 IONEX/VMF3 按实际到达顺序使用。

**离线检查通过不等于真机 PPP 更新或精度已验收。** 原真机 39 历元和历史 47 历元均为 Q0、rtkpos 调用 0，处于产品保护等待；它们只能验证记录、解码、产品加载和因果回放。用户本轮明确选择“暂不方便，先完成离线核验”，因此没有再启动采集、覆盖安装或声称 Q6 成功。

## 本轮确定问题与修复

PC 原有 `pc_ssr_preserve_rejected_arcs()` 会在 SSR 筛选后保留未转交 PPP 的 LLI_SLIP。Android `process_raw_epoch()` 原来直接原地 prepare，并在少于四颗星时返回，缺少此步骤。若已有模糊度且确认周跳恰在被挡历元发生，下一次 Raw 回调可能不再带同一 LLI，旧弧段存在错误延续风险。此前短测未进入 PPP，不能声称这一风险已经造成了该短测的坐标误差。

最小修复：将 PC 既有实现移至两端完全一致的 `NtripSsr::preserveRejectedArcs()`，PC 包装器委托它，Android 在 prepare 前保存观测副本、prepare 后调用它，最后才判断少于四颗星并返回。该函数只向现有 `ppp_input_failure_arcs()` 转交没有真正被送入 PPP 的周跳证据；已转交的有效信号不重复重置。使用现有 corrected_lifecycle 策略，不引入新的周跳检测器。

- Android：`app/src/main/cpp/gnss_jni.cpp:419`，`app/src/main/cpp/ntrip_ssr.cpp:296`，`app/src/main/cpp/ntrip_ssr.h:30`。
- PC：`src/ntrip_ssr.cpp:296`，`src/ntrip_ssr.h:30`，`src/pc_ssr_replay.cpp:248`。
- 现有核心：两端 ppp.c 的 `ppp_input_failure_arcs()` / `invalidate_arc_ppp()` 将旧模糊度及交叉协方差清除，标记 pending；本轮未修改这些核心函数。
- 回归：两端 `tests/ntrip_ssr_test.cpp` 新增 8 项断言，覆盖正常转交、少于四星、单信号被挡、实际信号切换、全部被挡、没有周跳及输入只读。

Android 独立 native 测试文件原先仍按旧的 10 秒规则断言失效，首次运行暴露测试与已冻结实现不同步。已与 PC 现有 WHU/BDT 全套测试对齐，仅调整头文件和配置函数名，没有为通过测试修改任何产品策略。

## 结果

| 检查 | 结果 |
|---|---|
| Android 四 ABI Debug APK | 构建成功 |
| Android JVM（强制重新运行） | 131 项，127 通过、4 跳过、0 失败/错误 |
| Android native SSR | 167 断言通过 |
| PC native SSR / 因果回放 / 滤波安全 | 167 / 40 / 15，通过，共 222 |
| PC Python | 28 测试通过 |
| 原 39 期 WHU 回放 | solution.csv、solution.stat、observations.csv、corrections.csv 逐字节一致 |
| 原 47 期 GENERIC_STRICT 回放 | 上述四文件逐字节一致 |
| 两端 SSR .cpp | 逐字节一致；.h 除核心 include 路径外一致 |
| 两端 RTKLIB 核心 | 与已有来源快照一致，零修改 |
| APK 中 native 库 | 仅四 ABI 的 libgnss_ppp_live.so 改变，另外八个库不变 |

回放两组都没有 PPP 更新，不能用它们证明已有非空 PPP 解逐位不变。原 R/Q/P0、Joseph、GIM 和抗差机制没有修改；未对原 PPP_only/FTPGet 项目写入，不提交、不推送。

## 版本与证据

本轮 APK：`E:/android/test/PPP_NTRIP/app/build/outputs/apk/debug/app-debug.apk`，SHA-256：

`a0333e0c9939fa1deec7be662485e1bb8ba12e218619c7c21221ed73cb2c893b`

**此 APK 尚未安装。** 手机最后核实安装的仍为 `8761a149...`，见 ANDROID_VERIFIED_DEVICE_TEST.md；不能将本轮源码修复描述成已在手机运行。

证据目录：`E:/GNSS/PPP_NTRIP_PC/validation/android_ssr_readiness_20261024/`。

- `before/`、`before.json`：8 个修改前源文件及指纹。
- `verification.json`：结构化结果；Android 副本为 tools/ssr_readiness_verification.json。
- `replay_short/`、`replay_generic/`：复用原始 ZIP 导入数据的回放，没有复制大型产品集。
- 本轮证据目录约 0.34 MB，未删除原始采集包、未无限录流。

复测命令：PC `python tools/build.py --test`、`python -m unittest discover -s tests -p "test_*.py"`；Android `gradlew.bat :app:assembleDebug :app:testDebugUnitTest --offline --console=plain`，独立 native `python tools/run_ntrip_native_tests.py`。本机使用项目既有 Python/JDK/Gradle 位置。

## 唯一下一项必要验收

用户方便后安装本轮 APK，进行同期、开阔天空、稳定网络的有界采集，至少跨过 WHU 连续两个偏差估计所需预热时间，检查实际 rtkpos/PPP 更新、Q6、持续运行、停止完整打包及 PC 同期回放。需要独立 WGS84 经纬度和椭球高才能评价精度。当前不承诺等待固定分钟数就必然出解，也不将 Q6 当作精度通过。

WHU 的 300+5 秒为已经记录的连续推进工程看门狗，不是已证实的官方绝对 OSB 有效期。本轮不改变此策略，不新增相位 OSB/模糊度固定或大气流；仍使用 WHU 精密改正＋预报大气。
