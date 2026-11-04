# 真机长时 WHU SSR PPP 核查（2026-10-25）

## 结论与范围

本轮不是此前 39/47 历元的短测。手机为 Xiaomi 2407FRK8EC（ADB CE7X4DL7FUFIMJJ7），已安装 APK SHA256 为 61eec3ffd213c7a718b6613367f35eb3d6e4f3044f75c6177ffaf8aa7fa4012c。原包 Capture_20261025_140604_09be8fea，持续 701.328676888 秒，已实际进入 B_VERIFIED 的 PPP 更新。

发现三个不同层次的问题：

1. **确定的解码实现错误：标准北斗 SSR 1261 沿用旧 24 位字段布局，与真实 WHU 流的 8 位 IOD 不符。** 当前北斗轨钟不能被可靠解释，实际最终观测仅有 GPS/Galileo。已保存真实报文的逐位及原始 native 解码复现，未修改正式解码器。
2. **确定的工具错误，已修复：PC ledger 校验未复现已存在的 native 公共钟跳归一化。** 这造成长包不能导入，不能解释手机坐标误差。修复仅涉及 Python 校验，不改数据、不拟合或平移 UTC、不放宽 10 μs 比较容限。
3. **确定的运行中断：HTTP 404 导致全会话停止。** 唯一中断通道为广播星历，符合其约 1 秒后重连返回 404 的调用时序；最终 HTTP 错误缺少显式 channel 字段，仍需补日志以直接标明来源。

另外，当前实际使用的 ANTEX 缺少部分 GPS L5 项，程序因此不接受这些相应观测；这是文件内容/参考约定限制，不能靠补零或经验复制其他频段处理。尚未证明任何单项问题可以解释全部米级精度偏差。

## 原始包与实际出解

原 ZIP SHA256：2014e459041de79261c738401ccffafbb94af39104fb5a3ca5a9edd52b5f02c0。PC 保存于 validation/android_long_20261025/，手机原目录及 ZIP 未改、未删。本轮没有启动新的采集、重装 App 或调整手机解算配置。

| 项目 | 结果 |
|---|---:|
| 采集时长 | 701.329 s |
| Raw 观测行 | 42,708，全部 54 列 |
| Raw 时钟锚 / ledger 历元 | 701 / 701 |
| Raw 掉行 / 写盘错误 | 0 / 无 |
| 文件哈希核验 | 21 项全部通过 |
| 轨钟 / 广播 / 偏差有效帧 | 559 / 23,098 / 979 |
| 三流 CRC 错误 | 全部 0 |
| 产品等待历元 | 223 |
| 首次 Q6 | 距首个 GNSS 原始历元 222.999 s |
| 实际调用 rtkpos 的历元 | 478 |
| Q6 / Q5 | 477 / 1 |
| 手机处理耗时中位数 / P95 / 最大 | 118.483 / 144.518 / 173.444 ms |

最初约 223 秒是 WHU 偏差连续估计预热，期间不输出 PPP。不能把有流字节当作此时已有坐标，也不能把这段时间从端到端启动体验中删除。首次出解约 3 分 43 秒不等于达到某个精度阈值。

包内实际冻结：COD0OPSP1D_20262980000_01D_01H_GIM.INX、VMF3_20261025.H06/H12、orography、igs20.atx。产品时间保护通过，未见超覆盖或混用文件 SP3/CLK/BIA。冻结快照和下载回执只能证明会话采用哪些文件，不能独立证明产品的历史发布时间。

## 手机—PC 因果回放

复用原包的 Raw、三流字节、到达顺序、实际 applied_seq、冻结产品和同一 profile。回放结果位于 replay/。

- PC 701 历元，Q0=223、Q5=1、Q6=477；与手机 ledger 一致。
- 已输出历元 ECEF 各分量最大差 X=3.290e-7、Y=4.778e-7、Z=4.522e-7 m，均小于 0.5 μm。
- 两端传入 RTKLIB 的观测行标识、P/L/D、CN0、LLI、code 完全一致。
- Raw、产品、流文件及正式回放可执行程序指纹保持不变。

因此，当前这份数据的米级误差可以在 PC 复现，证据不支持归因于 Android JNI 数值差异或观测序列移植错误。

### 第 410 历元的时钟与 Q5

TimeNanos/FullBiasNanos 表明一次 HCDC 不变的静默公共跳变，step=999,936 ns。Android 与 PC 的 normalize_clock() 本来就会累积此修正：间隔 (0,5 s]、阈值 50,000 ns。原 Python 校验器却直接比较 Raw GPST 与已经归一化的 native GPST，导致第 410～701 历元共 292 个锚差约 1 ms。

tools/android_ledger.py 现在复现相同的确定性历史规则；只由实际 native ledger 行推进历史，不用初始化前原始回调播种。701 个锚全部通过，未改原始时间、未移动流到达顺序。原失败 import.log 保留；因临时目录清理被自动审批拦截，直接对已解压文件重新执行全部哈希/Raw/ledger 校验，再由正式 replay_session.py 生成回放，没有重复解压产品或绕过 ledger。

这一历元距首个 GNSS 历元 408.999 s，模糊度进入 pending，最终 phase_sat=0、code_sat=10，日志正确标记 Q5。下一历元恢复 Q6；没有 filter error、NAN_*、NON_PSD 或 ASYM 失败日志，没有整机重启或全滤波器重新冷启动。Q5 是码更新降级，不是一个应当伪装成 Q6 的历元。

## 参考坐标与完整曲线

使用用户本轮明确给出的参考：纬度 30.69820588888889°、经度 104.05203827777777°、**椭球高 459.813 m**。采用 WGS84 椭球和此点作为 ENU 原点。没有沿用前次正常高或 Pt30 旧坐标，未参与滤波初始化。参考测量的不确定度及天线点偏移未提供，因此以下是对该给定参考的实测差，不额外宣称参考点的认证精度。

| 指标 | 首次 Q6 | 最后 Q6 | 最后 60 个 Q6 历元 RMS |
|---|---:|---:|---:|
| E | +2.360 m | +2.396 m | 2.540 m |
| N | +1.056 m | +1.230 m | 1.097 m |
| U | +10.078 m | +4.659 m | 4.651 m |
| 水平 | 2.586 m | 2.693 m | 2.766 m |
| 三维 | 10.404 m | 5.382 m | 5.411 m |

首次 Q6 约在 223 s；高程偏差随后从约 10 m 降到约 3.5～4 m，末段又回到约 +4.66 m。水平偏差全段为 2.586～3.675 m，没有小于 1 m 的有效 PPP 历元。因此不能声称已收敛到 1 m，也不能只截取较低的中段高程来报告精度。

总 ZTD 范围 2.2142～2.5081 m，本次未出现以前 vivo 数据的负总 ZTD。初值约 2.3556 m，末期 2.5081 m；ZTD 与坐标共同变化本身不能证明大气模型或 GIM 错误。本轮未重复 P0/R 消融或改变任何参数。

图：validation/android_long_20261025/convergence.png / convergence.svg。逐历元误差：position_errors_verified.csv；完整数值：analysis.json。灰区保留没有 PPP 的启动时间，黑叉单独标记 Q5，所有 PPP 统计均排除该降级历元。

## 确定错误：北斗标准 SSR 1261 字段错位

### 实际源码

- PC core/rtcm3.c:1566，decode_ssr1()；1750，decode_ssr4()：SYS_CMP 仍设 ni=10、nj=24。
- 同函数把前一个 10 位字段写入 ssr.iode，后一个字段写入 iodcrc；core/ephemeris.c:485 又将 ssr.iode 与广播 eph.iode 直接比较。
- Android app/src/main/cpp/ppp_live/rtklib/rtcm3.c / ephemeris.c 包含相同实现。

这不仅是一个数值参数差异。当前消息中的相应结构是 toe-modulo 10 位＋IOD 8 位，旧代码多消耗 16 位/卫星，后续轨道、钟差及下一颗卫星编号都会错位。还必须同时核实 PRN 起算和广播 IOD 的物理语义，不能只把 24 改成 8 就宣称完成。

### 本包的确定证据

1. 全部 140 帧有效 CRC 的 1261 消息，均为 35 星、payload 950 字节。
2. 采用 10+8 位布局，每帧仅剩 7 个填充位，全部精确闭合；采用当前 10+24 布局，每帧缺少 553 位，不可能容纳声明的 35 星。
3. 用**原版、未修改的 native decoder** 单独处理首帧，实际仅写入 11 个独立北斗卫星槽，而头部声明 35 星。存在串位与槽覆盖；这不是只看文档作出的推测。复现读取 decoder 的当前消息缓冲，不把尚未结束的多消息事务当作已提交 SSR。
4. 原格式读出 toe-modulo 而非现代 IOD；实际首颗字段 IOD=30。它不能与旧程序的 ssr.iode=toe-modulo 混用。实时回放中出现 426 条 no broadcast ephemeris，部分已通过产品连续性检查的北斗也未通过 satpos/广播匹配。
5. 真实最终观测只有 GPS/Galileo，虽然 Raw 中包含北斗 2I/1P/5P 等观测。这个结论来自 actual observations.csv，不使用“产品库存 89 星”冒充实际定位卫星数。

primary 对照来源：BNC [r8970 的字段定义](https://software.rtcm-ntrip.org/changeset/8970/ntrip/) 明确为 DF470=10 位、DF471=8 位；[r8996 的解码修改](https://software.rtcm-ntrip.org/changeset/8996/ntrip/) 为 GETBITS(a,8)；[BNC ephemeris.cpp r10630](https://software.rtcm-ntrip.org/browser/ntrip/trunk/BNC/src/ephemeris.cpp?rev=10630) 的 t_ephBDS::IOD() 按 (TOC.gpssec()/720)%240 生成匹配键。旧版 BNC 曾使用 24 位草案格式，不能拿旧草案或本项目旧合成帧验证当前 WHU 流。

复现：tools/audit_bds_ssr_layout.py；bds1261_bit_layout.json；first_phase_detail/bds_frame_reproduce.cpp、bds_frame_build.cmd、bds_frame_reproduce.json。此独立检查不改变正式 decoder 或消息时间。

既有合成北斗测试采用旧布局，故 167 项断言通过也未覆盖该真实协议问题。下一轮应先将这份真实帧固化为现代格式回归，再修复两端相同的 SSR 解码和严格 IOD 匹配。**不能使用 iode=-1 绕过匹配、补零改正或直接套其他中心产品。**

## 天线缺项及弧段日志的含义

独立 trace-level=3，仅重放到首次 PPP 更新：G03 和 G26 的 L5 出现 PPP_SAT_ANTEX_MISSING，slot=2、code=25、pcv_valid=0。检查包内实际 ATX：当前 G03/G069、G26/G071、G27/G066 条目仅含 G01/G02，没有 G05；G04/G074 则有 G05。

由 solution.stat 核实，G03/G26/G27 的 F3 从未成为最终 accepted phase。大量 OUTAGE 重置中 G03/F3、G26/F3 各 447 条，G27/F3 为 403 条。这些是“初始化但未进入更新”的状态反复触发 outc，不能说发生了 1,297 次独立硬件失锁。

这暴露了 udbias_ppp() 初始化与 ppp_res() 产品可用性筛选不一致的生命周期问题/无效状态周转。由于这些行未被最终接受，尚未证明它直接导致米级位置误差。需要依据正式天线改正约定处理缺频项，并使不可建模信号不反复播种模糊度；不通过关闭有效性保护、复制 L2 为 L5 或降低 R 来让其强行参加。

## 网络停止与下一步最小顺序

arrivals.csv 中 seq=25500 事件：channel=1（BCEP00BKG0）在 699.728304273 s CLOSED / NETWORK_DISCONNECTED；其他两路没有 CLOSED，轨钟还在 701.095759350 s 接收 DATA。全会话在 701.328676888 s 以 NTRIP_HTTP_404 结束。结合 NtripClient 断流后最短 1 s 重连和 NtripCaptureService.kt:100 任一路 4xx 立即 finish(status) 的实现，广播重连是唯一得到时序支持的 404 来源。服务器内部为何暂时返回 404 无法从客户端证明。

优先顺序：

1. 修复已证实的现代北斗 SSR 字段、PRN 与 IOD 匹配兼容，保留严格卫星/产品有效性与时标检查；对同一原包做独立回放，不能预期必然改善精度。
2. 为网络失败明确记录 channel/mount/status；设计“已连接流的短暂重连失败继续保留 Raw/其他流”的有界恢复。产品不满足时仍暂停 PPP，绝不延长陈旧轨钟有效期。当前“404 结束全包”是可复现行为，不等于服务器错误由 App 算法造成。
3. 解决有明确参考依据的 ANTEX 缺频处理及无效模糊度重复初始化，然后才重新评价完整曲线。没有依据时保持缺项显式，不制造默认改正。

本轮只修了 PC ledger 工具；以上正式 App/RTCM/PPP 模型修复均未实施。未改 R、Q、P0、Joseph、GIM、抗差阈值，未提交、推送。

## 回归与空间

- Python 工具回归 35 项通过（新增 7 项：静默钟跳、拒绝未归一化时间、HCDC 变化、长间断、小跳变、分数 Bias、初始化前锚）。旧 39/47 历元包仍通过校验。
- 现有 native SSR 167＋因果回放 40＋滤波安全 15，共 222 断言重新运行通过；其真实北斗格式覆盖缺口已明确记录，不能据此否认新缺陷。
- 新增 tools/analyze_android_live_capture.py、tools/audit_bds_ssr_layout.py；修改 tools/android_ledger.py、tests/test_android_ledger.py。修改前工具保存在 tool_before/。
- 原包、必要单次解压、完整回放、最小定点诊断总计约 86 MB；隔离的绘图环境 tools/plot_venv 约 79 MB，供后续复用，没有全局安装绘图包，没有 F 盘写入，没有重复拷贝原始产品树。原始 ZIP 末次 SHA 与首次一致。

结构化证据：validation/android_long_20261025/analysis.json、archive_audit.json、validated_existing_extraction.json、python_tests.log、replay/replay.json。后续从这些证据继续，不重新做历史大范围 P0/R/CN0 审计。
