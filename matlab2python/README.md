# MATLAB 打包为可 pip 安装的 Python 包

本示例演示如何把 MATLAB 代码封装成 Python 包，通过 `pip install` 安装后即可在 Python 中调用 MATLAB 函数。已包含最小加减法例子和 Python 侧调用脚本，可在此基础上按需扩展。

## 目录结构
- `add_func.m`、`sub_func.m`：示例入口函数。
- `Class_example.m`：类示例（当前 MATLAB 2024b 打包类仍有兼容性问题，暂未启用）。
- `build.m`：核心打包脚本，配置入口函数、输出目录、包名等。
- `call_example.py`：Python 侧调用示例，展示初始化 MATLAB Runtime 并调用函数。
- `example_python312_matlab2024b/`：已生成的示例包输出，包含 `setup.py`、`ExamplePkg/` 等，可直接安装验证。

## 先决条件
- MATLAB R2024b + Compiler SDK（打包时需要完整 MATLAB 环境）。
- 目标 Python 版本：示例使用 3.12，官方支持 3.9/3.10/3.11/3.12。
- 运行时要求：在部署机器上需安装对应版本的 MATLAB Runtime（MCR）。可在 MATLAB 中执行 `mcrinstaller` 获取安装包，或从 MathWorks 官网下载 Windows 版 R2024b MCR。

## 打包流程
1. **选择入口函数**：在 `build.m` 的 `entryPoints` 列表中加入需要暴露给 Python 的 `.m` 文件路径。每个函数都会被映射为 Python 方法。
2. **设置输出路径与包名**：修改 `outputDir` 与 `PackageName`，建议在包名或输出目录中标注 Python/Matlab 版本，便于区分。
3. **可选资源**：如需打包 `.mat` 等数据文件，将路径加入 `AdditionalFiles`，或保持 `AutoDetectDataFiles="on"` 让 MATLAB 自动扫描。
4. **执行打包**：在 MATLAB 命令行运行：
   ```matlab
   build % 或在脚本内 F5 运行
   ```
   完成后，在 `outputDir` 下会生成可直接安装的 Python 包结构（含 `setup.py`、`pyproject.toml`、`ExamplePkg/` 等）。
5. **安装验证**：切换到生成目录后执行：
   ```bash
   python -m pip install .  # 无管理员权限可加 --user
   ```
   安装完成后，任意位置可 `import <PackageName>` 并通过 `import matlab` 调用 MATLAB Runtime。

## Python 调用示例
`call_example.py` 演示了完整调用流程，关键步骤如下：
- 初始化 MATLAB Runtime 客户端仅需一次，耗时相对较长，示例通过 `_init_matlab_client()` 在进程启动时完成。
- 调用函数时显式转换数值类型（如 `float(a)`），并使用 `nargout` 声明期望的输出个数，例如：
  ```python
  import ExamplePkg

  client = ExamplePkg.initialize()
  status, result = client.add_func(float(a), float(b), nargout=2)
  ```
- 结束时若需释放资源，可调用 `client.terminate()`（示例未显式调用，依赖进程结束回收）。
- 类的打包在 MATLAB 2024b 仍存在限制，示例中的 `Class_example` 相关代码保持注释。

## 常见问题与提示
- **找不到 MATLAB Runtime**：确保目标机器已安装与打包版本一致的 MCR，并已正确配置 PATH（安装器默认会添加）。
- **入口函数输出个数不匹配**：Python 侧 `nargout` 必须与 MATLAB 函数实际输出一致，否则会报错。
- **新增函数**：在 `entryPoints` 中追加 `.m`，根据需要调整 `AdditionalFiles` 后重新运行 `build.m`。
- **升级 Python / MATLAB 版本**：重新设置 `outputDir`，保证输出目录与版本号匹配，避免不同版本文件混用。
