# DeepSeek Harness (dsh) 安装记录 2026-08-16

- 位置: C:\Users\WH\Desktop\deepseek-harness（源码克隆，v0.1.0-rc.5，MIT）
- 依赖: Node 24.14.1，pnpm 11.7.0（全局安装于 AppData\Roaming\npm，corepack 的 pnpm 不在 PATH 不能用）
- 构建: pnpm install + pnpm run build 均成功
- 运行: 在项目目录执行 pnpm dsh web，Web UI 监听 http://127.0.0.1:3080
- 重要坑: 本机 C:\Users\WH\.dsh 目录创建被系统拒绝（EPERM），必须设置 DSH_HOME=C:\Users\WH\Desktop\deepseek-harness\.dsh 才能启动
- CLI: pnpm dsh --help 正常；profile 机制可配置插件组合