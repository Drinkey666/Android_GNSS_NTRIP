# Gradle testClasses兼容修复（2026-10-30）

错误发生在Gradle任务选择阶段。Android app没有Java插件的testClasses任务；实际任务列表确认存在compileDebugUnitTestSources及testDebugUnitTest。工程.idea中未发现持久的错误taskNames配置，无法据此确认具体哪个外部启动器产生调用。

只修改app/build.gradle.kts：注册testClasses兼容别名，依赖真正的compileDebugUnitTestSources。不是空任务或跳过编译，也不宣称它会执行测试；运行单元测试用testDebugUnitTest。未修改PPP/观测/SSR源码。

验证命令：gradlew.bat :app:testClasses :app:testDebugUnitTest :app:assembleDebug --offline --console=plain。
结果：BUILD SUCCESSFUL in 20s；testClasses、测试编译和testDebugUnitTest命中已有最新输出（UP-TO-DATE），APK打包成功。没有冒称此次重新执行158项测试体。没有安装或推送。

原build.gradle.kts及SHA、完整验证日志见tools/gradle_testclasses_fix_20261030。之前观测移植delivery_manifest是当时产物指纹，不改写；本次重新打包的现行APK SHA为ecbf5abf6e557ec7eee6eb21de2dcefdeee5ba2828cd06fb4115b017b44d7e7f，并不表示Native算法改变。上次报告874f9500...为上次构建快照，不再是当前APK文件SHA。

Android Studio先Sync Project with Gradle Files，然后重新运行原配置；如希望执行测试，使用:app:testDebugUnitTest；希望生成APK用:app:assembleDebug。
