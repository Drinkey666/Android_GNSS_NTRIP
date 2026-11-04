# WHU 北斗 SSR 修复、生命周期修复与完整回放（2026-10-25）

## 当前结论

已实施并验证三项确定的程序修复：现代北斗 SSR 解码及严格广播匹配、不可建模信号的模糊度播种保护、已工作 NTRIP 流短暂 404 的有界恢复及失败通道记录。

**定位精度问题没有解决，不能将本轮结果验收为精度提升。** 旧版该包仅使用 GPS/Galileo，末点水平 2.693 m、Up +4.659 m。修复后真实恢复北斗，末点水平 2.120 m、Up +9.067 m；最后 60 个 PPP 历元的高程 RMS 从 4.651 m 增至 9.172 m。因此不能继续把原有高程偏差归结为“北斗解码一处错误”，也不能隐藏恢复北斗后的恶化结果。

新 APK 已构建，**没有覆盖手机现有 APK**。用户已授权修复，但精度回归未通过，故保留现有已采集版本，避免把新包当成精度已解决的版本。原始观测、改正、参考坐标及 R/Q/P0/GIM/Joseph/抗差参数均未更改；无提交、无推送。

## 保护及可复现输入

PC 项目 E:/GNSS/PPP_NTRIP_PC、安卓 E:/android/test/PPP_NTRIP 均不是独立 Git 仓库。修改前源文件、配置指纹和原始 PC 可执行程序已备份到 validation/bds_ssr_fix_20261025/before/ 及 before.json。没有覆盖旧回放结果，也没有修改原 PPP_only 或 FTPGet 源码。

复用 validation/android_long_20261025/imported/ 的单份实际采集数据，不重复复制产品树；原 ZIP SHA256 仍为 2014e459041de79261c738401ccffafbb94af39104fb5a3ca5a9edd52b5f02c0。参考仅用于解后计算：WGS84 纬度 30.69820588888889°、经度 104.05203827777777°、椭球高 459.813 m。

## 修复 1：现代北斗 SSR 格式与星历匹配

修改仅在 PPP_NTRIP_SSR 编译路径生效；PC 和 Android 的对应四个核心文件逐字节一致。

- core/rtcm3.c：decode_ssr1()/decode_ssr4() 对标准 BDS 使用 DF470=10 位、DF471=8 位。固定长度消息必须完整容纳声明的 nsat，且剩余仅允许 0～7 个填充位；否则在写入任何卫星之前拒绝。不会尝试猜测、混读 24 位草案。
- 标准 BDS 各 SSR 家族使用实际 PRN，不再加一；IGS 4076 原有布局和 GPST 处理不变。新增测试覆盖 C01、C63、无效零编号。
- core/rtklib.h：SSR 中新增 bds_iod_mode 和 bds_toe_mod，把原始 toe-modulo 与 IOD 分开存储，不改广播 AODE/IODE，也不伪造 provider、solution 或 epoch。
- core/ephemeris.c：现代 BDS SSR 独立按 (GPST TOC / 720) % 240 匹配 DF471，仍检查原有 TOE 年龄及健康状态；对选定的同一条广播星历计算位置、速度、钟差和相对论。没有用 iode=-1 退化为随意选择最近星历，广播解及其他星座原路径不变。

依据：[BNC r8970 字段定义](https://software.rtcm-ntrip.org/changeset/8970/ntrip/)、[r8996 解码定义](https://software.rtcm-ntrip.org/changeset/8996/ntrip/)、[BNC ephemeris.cpp r10630 的 t_ephBDS::IOD()](https://software.rtcm-ntrip.org/browser/ntrip/trunk/BNC/src/ephemeris.cpp?rev=10630)。实际流的全部 140 帧 1261 已在上一轮完成逐位闭合，本轮不重复大范围静态审计。

真实报文回归不再沿用错误的旧合成布局：tests/fixtures/whu1261_reference.h 保存 956 字节原帧及 35 颗卫星的独立逐位期望值。两端测试核对全部轨道、轨道变化率、钟差、IOD、编号及时标。旧解码器同帧只写入 11 个独立槽，修复后 35/35 正确。另覆盖独立轨道 1258、截短但 CRC 正确的消息、IOD 不匹配、星历过期、IGS 布局、周界和重复报文。

现有 BDT→GPST 边界修正保留：标准 BDS 转换一次；IGS BDS 不重复转换。没有移动改正到达时间，仍按捕获的 applied_seq 释放。

## 修复 2：ANTEX 缺项不再反复播种模糊度

core/ppp.c 的 udbias_ppp() 新增 ssr_ambiguity_model_available()。在 corrected_lifecycle 的 SSR 路径，先核对与 ppp_res 一致的静态 PCO/PCV 完整性，再决定是否播种模糊度。confirmed slip 的旧弧段失效仍在前面执行，不能因为本历元产品缺项跳过 reset。

这没有补零天线改正、复制 L2 到 L5、放开缺项行，也没有新增残差拒绝规则。G03/G26/G27 L5 的真实改正仍然缺失；只是这些不可进入观测方程的信号不再创建一个下一历元又被 OUTAGE 清除的状态。

单因素验证：仅解码修复 replay_bds/ 的 OUTAGE 重置日志为 1307 条，再加播种保护的 replay_seed_guard/ 为 31 条；**两次回放全部已输出 XYZ 完全相同**。因此该修复解决无效状态生命周期，不冒充精度改善。其余 CONFIRMED_SLIP 日志数量的变化包括空状态的诊断变化，不能把日志总数当作独立硬件周跳数。

## 修复 3：短暂 404 与可追踪性

Android NtripClient.kt 新增 NtripReconnectPolicy：

- 首次请求即 404，仍按未知/错误挂载点停止。
- 一条流已经收到数据后，重连遇到 404 可按既有指数退避再试，最多 3 次；收到新数据才恢复重试预算。
- 401/403 不重试；超过预算仍明确停止。没有修改轨钟 90 秒有效性、偏差连续性或其他产品保护，重连不代表旧改正重新有效。
- NtripCaptureService.kt 先写 CLOSED(channel,reason)，再执行终止，capture.json.failures 也保留通道。旧版 fatal 4xx 分支漏掉此记录的问题已修复。
- UI 将 RETRY_HTTP_404_n 显示为重连，不当作永久挂载错误。

本地实际 socket 测试完成“200＋数据 → 断开 → 404 → 200＋数据”恢复；同时测试初次 404、预算耗尽、收到数据后预算恢复、401/403 始终终止。此为传输行为修复，不能声称它修正离线坐标误差。真实 caster 何时返回 404 不由 App 控制，本轮没有重复录流来替代已保存证据。

## 701 历元受控回放

| 指标 | 冻结旧版 | 修复北斗 | 再加模糊度播种保护 |
|---|---:|---:|---:|
| 总历元 | 701 | 701 | 701 |
| Q0 / Q5 / Q6 | 223 / 1 / 477 | 223 / 1 / 477 | 223 / 1 / 477 |
| 首次 PPP 距首 Raw | 222.999 s | 222.999 s | 222.999 s |
| 末点 E / N | 2.396 / 1.230 m | 1.547 / 1.449 m | 相同 |
| 末点 Up | +4.659 m | +9.067 m | 相同 |
| 末点水平 | 2.693 m | 2.120 m | 相同 |
| 末 60 历元水平 RMS | 2.766 m | 2.146 m | 相同 |
| 末 60 历元 Up RMS | 4.651 m | 9.172 m | 相同 |
| 全 PPP 历元水平 RMS | 2.998 m | 2.362 m | 相同 |
| 全 PPP 历元 Up RMS | 4.628 m | 8.996 m | 相同 |
| OUTAGE 重置日志 | 1306 | 1307 | 31 |

修复后输入中真实恢复北斗：G=6687、E=3766、C=5918 个卫星/信号观测行；这些是观测行数量，不是独立历元或定位卫星数。接收机钟差、ISB、逐星电离层、模糊度及观测集合因此发生变化，不能要求全部后验与旧版相同。

所有主回放没有数值失败日志，未出现 NaN/Inf、NON_PSD 或 ASYM 失败。第 410 历元的约 1 ms 公共钟跳仍按原逻辑处理、短暂 Q5 后恢复 Q6；本轮没更改该时钟规则。

完整曲线 before_after.png / before_after.svg，逐历元 CSV、分段 RMS、偏差及全部状态统计见 comparison.json。未删除启动、未用平滑掩盖恶化、未按末点挑选参数。

## 对“为什么误差大”的证据边界

能够排除：不是这次 Android/PC 算术移植分叉；旧版手机与 PC 的坐标差小于 0.5 μm。不是 NaN/Inf 或已知协方差数值缺陷在该段重新发生。北斗解码错误修复是必要的正确性修复，但旧版的米级偏差发生在仅有 GPS/Galileo 的实际解中，不能把全部误差归给未参与的北斗。

能够确认：实际缺少多颗 GPS IIF 的 L5 天线改正，限制了可用双频组合；只有约 478 秒已进入 PPP 的数据。恢复北斗后垂直变化很大，说明新增观测与现有电离层/码偏差/大气联合状态之间还有待解释的偏差。**这不是已经证明某个 R/Q/P0 参数错了，更不是已证明北斗数据本身质量差。**

本轮额外核对实际码偏差：多数 GPS/Galileo/BDS 参考频对的 IF 组合接近量化零，但部分北斗条目（例如本段 C12 的 B1I/B3I IF 偏差约 +26.27 m）不同。C12 没有同时使用 B3I 观测，且尚无逐星产品基准的独立证明，不能据此认定 B1I 偏差错误；因此没有擅自归一化 OSB、改卫星钟差或屏蔽该星。继续修精度应集中验证新增北斗及原 GPS/Galileo 的逐星码相—钟差基准与联合状态可辨识性，不再做盲目参数搜索或重复泛化 CN0/P0/R 审计。

GPS IIF L5 校准不足也不能以“照抄 L2”静默修补；[原始研究指出此类替代存在风险](https://www.ion.org/publications/abstract.cfm?articleID=18016)。在取得有依据的改正约定前保持缺项显式。

## 构建、测试及影响范围

- PC native：579 条 SSR/真实报文断言＋40 因果回放＋15 滤波安全，共 634，通过。
- Android 相同源码的 MSVC native：579，通过。
- **真实 Xiaomi arm64 设备：579 个 native 断言全部通过，退出码 0**。使用本次 NDK 编译对象链接独立测试程序运行于 /data/local/tmp/ppp_ntrip_protocol_test，没有替换 APK，也不是另一份手机实时采集或精度验证。
- Android 四 ABI APK 构建成功；JVM 总 136 项，132 通过、4 跳过，0 失败/错误，包括真实 socket 断流—404—恢复测试。
- Python 工具回归 35 项通过。
- PPP_NTRIP_SSR 关闭后，ppp.c、ephemeris.c、rtcm3.c 对本轮冻结源码的预处理 token 与机器码 text 均相同。原文件产品 A/B 路径不受本轮新增分支影响。
- Android 的 32 文件 fork manifest 已在逐文件核对 PC 完全一致后刷新，未关闭 CMake 校验。最初构建因旧 pin 拦截，更新对应修复指纹后成功。
- 历史 39 期 WHU 包 solution/stat/observations/corrections 全部逐字节相同。47 期 GENERIC_STRICT 包 solution/stat/observations 相同；43 期诊断 reason 从 MISSING_ORBIT_CLOCK_CODE_BIAS 变为 SSR_IOD_MISMATCH，因为现可正确解出北斗但通用模式仍拒绝独立 WHU 的配置编号不一致。没有改变它的严格策略，也没有伪造 Q6。
- 旧 check_ntrip_isolation.py 依赖早期 FTPGet 全目录快照，本轮运行未通过：AGENTS.md、FtpDownloader.kt、LivePppProducts.kt、MainActivity.kt 已与该历史快照不同。本轮未写 FTPGet、未还原其他工作的修改，也未改快照让其假通过；替代的本轮源码前后宏关闭核验已通过，不能声称该旧检查通过。

主要修改文件：PC/Android 两端 rtcm3.c、rtklib.h、ephemeris.c、ppp.c；两端 ntrip_ssr_test.cpp 和真实 fixture；Android ntrip_profile.sha256、NtripClient.kt、NtripCaptureService.kt、MainActivity.kt、NtripProtocolTest.kt。新增 tools/compare_ssr_fix.py 仅用于离线图表。

新 APK：E:/android/test/PPP_NTRIP/app/build/outputs/apk/debug/app-debug.apk，SHA256 `476d5b4b15526feb299297a031bfcf743fa8dbf9f02fef43634ebe1f231663aa`。手机仍是 `61eec3ff...`。**不得把“构建成功/协议测试通过”描述为手机已安装或精度已修复。**

证据入口：validation/bds_ssr_fix_20261025/verification.json、comparison.json、before/、macro_off/、各 replay 目录和构建日志。真实设备测试命令与结果位于 Android tools/android_bds_protocol_test/commands.json、device_result.log。全部原始输入保持不变，没有 F 盘写入、无限录流或未经确认的参数提交。
