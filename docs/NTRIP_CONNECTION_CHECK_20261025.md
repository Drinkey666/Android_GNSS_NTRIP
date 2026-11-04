# 手机安装版本与 NTRIP 连接核查（2026-10-25）

## 已安装版本

手机 V2507A，包名 com.example.pppntrip，手机显示最后更新时间 2026-10-25 12:21:14，versionCode=1 / versionName=1.0。versionName 尚不能区分这些调试构建，因此直接比较 APK 内容。

- 已安装 APK SHA256：`61eec3ffd213c7a718b6613367f35eb3d6e4f3044f75c6177ffaf8aa7fa4012c`。
- 当前本地 app/build/outputs/apk/debug/app-debug.apk：`9138598a998fedde7cfec9ceaec479b6d65647761639564bd0b68fd581d0b42d`，文件时间 2026-10-25 12:19:56。
- 比较全部 880 个非 META-INF 条目：业务 DEX、资源、assets 和 arm64 的全部 native 库相同。差异为 AndroidManifest.xml 和手机包未包含的另外三种 ABI 库。不能拿整包 SHA 不同断言手机代码过旧；就实际运行的业务代码和 arm64 解算库而言，与当前构建一致。
- 原 FTPGet 包也存在，但本次失败与短测证据都来自 com.example.pppntrip。本轮未覆盖安装、卸载或清数据。

## 失败证据及可确定范围

读取手机保存的三个会话：Capture_20261025_122200_a8aab1c5、Capture_20261025_122227_c1464cfb、Capture_20261025_122235_7da93c0c，stop_reason 均为 NTRIP_HTTP_404。并非根据 UI 泛化提示猜测。

现有 NtripCaptureService 在任一路返回 HTTP 4xx 时停止整个会话；保存的 stop_reason 没有通道标识，失败分支也未在 arrivals.csv 留下对应 CLOSED 事件。因此，不能从这些历史文件确定最终 404 属于哪一路，更不能证明服务器内部为何返回 404。已有成功 200 只说明该次流此前连接成功；中断后重连仍可能失败。

本轮使用授权本地默认凭据，对相同 caster ntrip.gnsslab.cn:2101 及三个挂载点做有界功能请求。三路均 HTTP 200，正确解除 HTTP chunked 后均有 CRC 正确的 RTCM。源列表也列有 SSRC00WHU0、BCEP00BKG0、OSBC00WHU1。这证明当前挂载点及默认账户可用，不能将先前 404 说成挂载点永久不存在或当前账户无权限。

probes.json 只用于响应头和源列表；其初次原始 HTTP 探测未解除 chunked，故不保留其错误 CRC 统计。RTCM 结论以 decoded_probes.json 和实际手机采集为准。

## 配置修正与真机短测

发现最后一次手机配置 com_whu=false，即 SSRC00WHU0 被选为 APC。通过现有设置界面将其改回 CoM，保存后读取偏好确认 com_whu=true。该项是与产品声明不符的配置问题，独立于 HTTP 404，不声称它导致网络错误。

随后启动一次有界短测并正常停止：Capture_20261025_123257_fb6f9f5f。

| 流 | HTTP | CRC 有效帧 | CRC 错误 |
|---|---:|---:|---:|
| SSRC00WHU0 轨钟 | 200 | 7 | 0 |
| BCEP00BKG0 广播 | 200 | 211 | 0 |
| OSBC00WHU1 偏差 | 200 | 13 | 0 |

complete=true，USER_STOP，Raw 掉行 0、写盘无错，software.json 的 APK 指纹与手机一致。记录了 10 个处理历元；仍在 WHU_OSB_WAIT_NEXT_ESTIMATE 预热阶段，没有验证 PPP 更新或精度。采集服务已停止，原始 ZIP 留在手机，未将整套产品再次复制到 PC。

## 当前结论与边界

当前手机版本的运行代码是最新，三路连接在手机已恢复。此前失败可确定是 caster HTTP 404，确切历史通道和服务器端触发原因证据不足。不通过换产品中心、伪造时间或放松产品有效性保护绕过问题。

本轮未改任何源码、默认 R/Q/P0、Joseph 或抗差参数。只将手机错误的 APC 选择恢复为该 WHU 挂载点的 CoM，并保存小型诊断证据。没有开始长时间出解验证。

证据目录：E:/GNSS/PPP_NTRIP_PC/validation/ntrip_connection_20261025/，约 29 KB，含三个失败会话及本次成功会话的清单副本、decoded_probes.json 和 verification.json；无密码或认证头。

若再次失败，最小后续改进是为安全状态记录补充失败 channel/mount/status，使下一次能直接定位通道；这不是目前连接恢复的必要条件。本轮未修改此逻辑。
