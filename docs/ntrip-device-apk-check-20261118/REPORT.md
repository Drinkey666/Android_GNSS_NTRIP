# 手机安装包核验

2026-11-18 实查 vivo V2507A，com.example.pppntrip 最后更新 2026-11-18 15:09:06。手机 arm64 版与本地最新多 ABI APK 的全部 DEX、资源、资产和 arm64 原生库逐项一致。整体 APK SHA 不同。手机 Manifest 额外设置 testOnly=true，本地额外包含其他三种 ABI 共九个库；Manifest 逐属性解析的唯一语义差异为该测试标志。安装内容与当前最新本地程序内容一致，实时 PPP 采集验收待执行。

- 已安装 APK SHA-256 `cf0eedfd15b96d950d279d3e6d7549509fe2967cdd83a486138cf708cf1df91d`。
- 本地多 ABI APK SHA-256 `6a280c7b4e03b76ca49bd587556e0ed7a2bcb05b6962c7518121cd3c0ace038b`。
- 实时解算库 SHA-256 `bcff767e8cab4727cd83ab4a9a0000bccbf37f9ef7ae776515b1bfd7c32669d2`。
- 两端 33 项共享核心清单核对通过。本轮读取设备安装包并在内存中比较，未安装或采集。

[逐项核验摘要](verification.json)
