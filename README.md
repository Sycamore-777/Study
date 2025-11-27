# Study

一个收集练习项目的仓库，用来快速尝试后端服务、监控、日志等主题。仓库按照场景分目录，当前主要包含 FastAPI 驱动的“服务编排/监控”示例：

- `serving-and-monitoring/study_without_log`：最小可用的算法服务 + 模拟数据源 + 轮询示例，便于先跑通整体流程。
- `serving-and-monitoring/study_with_log`：在基础流程上增加全局请求日志与 X-Token 鉴权中间件，演示如何在生产化时补充观测能力。

> 环境建议：Python 3.10+，安装依赖请参考各子目录 README。

快速查看：
- 若想了解无日志的基础版，进入 `serving-and-monitoring/study_without_log`。
- 若想了解带日志与鉴权的版本，进入 `serving-and-monitoring/study_with_log`。

后续会将更多学习实验按主题新增到本仓库，保持单目录自包含、README 可直接上手。

