# 手机实时 PPP 的广播星历备用源

建议在原服务器反复返回 404 或等待首包超时时，选用匿名广播流 `ntrip.use-snip.com:2101/RTCM3EPH`。2026-11-19 北京时间 21:35:42 起，vivo 蜂窝网约 118 秒的三路并发测试收到 3,856 帧广播、93 帧 WHU 轨钟和 97 帧 WHU 偏差，三路 CRC24Q 错误均为零。分开连接使广播摆脱原 caster 的单点故障。WHU 轨钟或偏差本身中断时，PPP 仍可能等待产品。

## 怎样切换

- 新版 Android 打开「NTRIP 设置」，开启「使用 SNIP 独立广播星历」，点保存，在下一次采集生效。只将广播连接指向上述公开服务，不向它发送 Authorization。轨钟 `SSRC00WHU0` 和偏差 `OSBC00WHU1` 使用现有服务器及账号。关闭开关后恢复原来填写的广播挂载点。本次已构建个人 Debug APK，手机实测使用独立网络探针，应用内开关尚未在真机运行。
- 使用原版 App 时，在「广播星历挂载点」填 `BCEP00CAS0` 可以用原账号试同服备用。原版的「服务器」字段供三路共用，直接改为 SNIP 会同时改变两条 WHU 请求的目的地。CAS 在 PC 上与两条 WHU 同时出流，在本轮手机短测中三路都遇到超时。经过对比，优先推荐独立广播入口。
- PC 在工程根目录运行 `python tools/ntrip_capture.py --config config/caster_whu_snip.json --seconds 125`。同服 CAS 方案使用 `config/caster_whu_cas.json`。单独核查匿名广播可运行 `python tools/probe_ntrip_mounts.py --config config/caster_whu_snip.json --mount RTCM3EPH --seconds 15 --header-timeout 60`。默认配置继续使用历史 BKG 广播基线。
- 另一个可申请的分发入口是 BKG 官方产品 caster。其完整源表列有 `BCEP00CAS0` 和 `BCEP00CHC0`，443/TLS 两路匿名请求实测均返回 401，需要该服务自己的账号。[BKG 官方注册](https://register.rtcm-ntrip.org/cgi-bin/registration.cgi?mod=register) · [IGS 广播产品目录](https://igs.org/rts/products/)

## 相同接收判据的实测

表中是成功通过 CRC24Q 的帧数。各行按实际时段分别建立连接。GNSSLAB 在不同分钟的响应差异很大，帧数也受各源轮播频率影响，不能直接换算为长期可用率或定位精度。

|网络和时段（北京时间）|广播源|广播|WHU 轨钟|WHU 偏差|
|---|---|---:|---:|---:|
|PC 21:24，同服三路，最长等响应 60 秒|CAS|226|43|78|
|PC 21:27，相同策略|BKG|0|0|0|
|vivo 21:28，约 48 秒|CAS|0|0|0|
|vivo 21:29，约 48 秒|BKG|90|1|2|
|vivo 21:30，约 48 秒|SNIP|1,698|0|6|
|PC 21:33，正式录流入口，125.5 秒|SNIP|4,080|61|109|
|vivo 21:35，约 118 秒|SNIP|3,856|93|97|

PC 分服录流的广播、轨钟、偏差依次在 1.75、42.03、47.41 秒完成响应头。三路无重连、CRC 错误均为零。客户端现对响应头阶段每次读取允许等待 60 秒，进入数据流后仍以 15 秒无数据触发重连。当晚旧包的真实 HTTP 404 与本轮未收到响应头的超时分别记录。手机的有效对照在 ADB 两端以 Base64 传送请求和回包，已用已知字节校验 CRLF。早期 ADB 直接传输会改变请求字节，相关结果已从表中剔除。[各窗口和消息类型](results.json)

## 星历内容与可用性

手机收到 GPS 1019、GLONASS 1020、北斗 1042、Galileo 1045/1046。SNIP 手机长测覆盖 32 颗 GPS、36 颗北斗、30 颗 Galileo；这些星的广播轨道参考时刻与采集时刻之差均在两小时内。PC 依次处理已保存的三路到达记录，只用 WHU 轨钟帧到达之前收到的星历核对其引用的星号和期号。匹配 GPS 29/32、Galileo 29/29、北斗 35/35，GPS 有 3 个星号／期号组合未匹配。北斗沿用工程的时钟参考时刻和 WHU 八位期号约定。[逐系统汇总](iod_pairs.json)

本次 PC 录流通过四项文件大小及 SHA-256 复核。历史 PC V1 连续性检查在 125 秒内最高同时记录 88 颗三项改正齐全的卫星，仍处于独立偏差启动等待，最高可用数为零。该检查使用 PC V1 策略；本轮无同步手机观测用于评估 Android V2 首解或定位精度。长期断线率也需要更长时间的实录。[V1 检查](native_result.txt)

Android 完成 `:app:testDebugUnitTest` 和 `:app:assembleDebug`。JUnit 报告列出 172 项，166 项执行通过、6 项跳过。PC 录流 16 项和探针 19 项回归通过，包括用两个独立监听端口检查账号只出现在主服务器请求中。正式 PPP 内核及历史采集数据沿用原版本。
