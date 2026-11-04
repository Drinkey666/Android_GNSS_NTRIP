# 新版安装与留档真机验证（2026-10-24）

## 当前状态

用户确认手机可以调试后，ADB 授权正常。检查无活动采集，覆盖安装 `com.example.pppntrip` 成功，未卸载或清除数据。Vivo 安装确认完成后，读取已安装 base.apk 的 SHA-256，与本地构建一致：

`8761a1492c4e15132da9c642819b323cf81d7569e020b24469eebdd1f8863e47`

该版本同时包含 WHU_OSB_CONTINUITY_V1、标准 RTCM 北斗时标修复、Raw 回调排空保护和 software.json 留档。此前“未授权/拒绝安装/仍为 d0407f82 旧版”记录现已成为历史，不再是当前状态。

## 实际执行

- 设备 vivo V2507A / Android API36，序列号 `10AFCP26FR007MJ`。
- App 显示 SSRC00WHU0(CoM)、OSBC00WHU1 和 BCEP00BKG0。
- 启动配套采集后按 HOME，在后台继续采集；返回 App，点击停止并等待完整打包。
- 点击 App 的“导出最近录制包”，通过既有 SAF 授权导出到公共目录。
- 验证前台服务已停止，启动按钮恢复；未在手机留下正在运行的采集。
- 复制 ZIP 到 PC，校验导入，再按包内产品、profile 和 applied_seq 因果顺序回放。未改原始数据、时间戳或滤波参数。

## 结果

| 项目 | 结果 |
|---|---|
| 会话 | `Capture_20261024_214556_e76a0cd0` |
| 实际时长 | 39.417056617 s |
| 原始观测 | 299 行，全部 54 列，39 个原始时钟历元 |
| 时钟锚 / native ledger / PC 历元 | 39 / 39 / 39 |
| 掉行 / 写盘错误 | 0 / 无 |
| 轨钟 / 广播 / 偏差有效 RTCM 帧 | 31 / 1733 / 55 |
| 三路 CRC 错误 | 全部 0 |
| 清单列明文件哈希检查 | 21 项全部通过 |
| software.json 的 APK 指纹 | 与手机、本地构建一致 |
| 手机/PC GPST 一致 | 39/39 |
| 已应用 arrival seq 一致 | 39/39 |
| 改正状态一致 | 39/39 |
| 停止原因 / complete | USER_STOP / true |
| 本次 Q6 / 滤波调用 | 0 / 0，处于 `WHU_OSB_WAIT_NEXT_ESTIMATE` |

本次是短时安装、后台、停止排空和回放完整性检查，**不是定位精度、长时间稳定性或锁屏测试**。不足一个偏差估计周期，仍等待下一次估计符合当前保护策略；没有冒充已得到 PPP 坐标。不能把三路有帧或本次核验通过当作 Q6/精度验收。

## 文件位置

手机公共目录：

`/sdcard/2026106/Capture_20261024_214556_e76a0cd0.zip`

PC 原始包、导入目录、回放和证据：

`E:/GNSS/PPP_NTRIP_PC/validation/android_verified_device_20261024/`

- `Capture_20261024_214556_e76a0cd0.zip`
- `imported/`（包括原始 TXT/三路流、产品快照、时钟锚、ledger、software.json、trace）
- `replay/`、`import.log`、`replay.log`
- `verification.json`

公共导出 ZIP 与 PC 包 SHA-256 均为：

`ebe2324ebacbd5562c8af4e13b9f88a65958ef7658ce729743837dc7d7b47b0e`

Android 结构化证据：`E:/android/test/PPP_NTRIP/tools/verified_device_test.json`。两份此前真实包与手机其他原始记录均保留。本轮未改安卓或解算源码、未重跑历史精度消融、未提交推送。

## 户外下一步

手机已安装新版，可以开始户外出解验证。采集前先准备当天预报产品；选择天空开阔、位置固定、网络稳定的环境。首次可能等待约一个 300 秒偏差估计周期，断流后可能重新核验；看到 Q6 才说明产生浮点 PPP 解。完成后正常停止并导出整包，使用独立 WGS84 经纬度及椭球高评价完整收敛曲线。当前没有新的定位精度结论。
