# Study

一个收集练习项目的仓库，用来快速尝试后端服务、监控、日志以及工具链整合等主题。各实验按场景拆分子目录，互不干扰，每个子目录都附带独立的 README 便于直接上手。

## 目录速览
- `matlab2python/`：示例演示如何把 MATLAB 代码打包成可通过 `pip install` 安装的 Python 包，并提供 Python 侧调用示例。
- `serving-and-monitoring/study_without_log`：最小可用的算法服务 + 模拟数据源 + 轮询示例，方便先跑通整体流程。
- `serving-and-monitoring/study_with_log`：在基础流程上增加全局请求日志和 X-Token 鉴权中间件，演示生产化时的观测能力补充。
- `python2native/`：预留的 Python -> 原生扩展相关实验（待补充说明）。

> 环境建议：Python 3.10+。具体依赖与运行方法请查阅各子目录的 README。

后续会按照主题持续补充新的学习实验，保持每个子目录自包含，README 可直接照着操作。
