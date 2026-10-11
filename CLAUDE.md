# hasn-qwentts 开发约定

这是平台本机语音引擎的独立 infra fork，主分支为 `main`。真实上游是
`https://github.com/ServeurpersoCom/qwentts.cpp`，起点
`51512f129a7419567f4b8abfb06801451789b8f1`；`upstream` 不指向本机目录。
父仓开发约定同时生效。任务分支必须在 worktree，模型与构建产物必须在源码树外。

- GGML 源来自上游 gitlink 指定的真实独立 checkout，通过 `GGML_SOURCE_DIR` 传入；不 vendor，不更新或下载子模块。
- 新增注释、文档、TODO、配置说明用中文；上游英文保持原样。
- 内循环只跑 `tests/` 的有界专项；默认 CTest 不加载模型，不运行 E2E。
- 构建入口见 `docs/引擎接入与验证.md`。完成即精确提交，合入主 clone 由任务收口者协调；不自行 push。
