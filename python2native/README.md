# Python 调用与导出本地接口（Cython 示例）

本示例展示如何用 Cython 将 Python 代码编译为原生扩展，同时导出 Python 可直接 `import` 的模块，以及可供 C/C++ 动态链接的 C 接口。

## 目录结构
- `requirement.txt`：编译依赖（Cython、setuptools）。
- `python/`：面向 Python 调用的示例，含 `mymath.pyx`、`setup.py`、`call_mymath.py`。
- `C/`：在 `python/` 示例基础上，额外通过 `cdef public` 导出 C API，提供 `mymath_c_api.h`、`call_mymath_linux.cpp`。
- `.so` 与 `.pyi`：已编译的 Linux x86_64 示例，仅供参考，跨平台请重新编译生成。

## 先决条件
- Python 3.10+，已安装编译工具链（Linux/WSL: `build-essential`；Windows: MSVC 或对应的 C 编译环境）。
- 安装依赖：
  ```bash
  python -m pip install -r requirement.txt
  ```

## Python 侧使用（目录：`python/`）
1. 进入目录：`cd python2native/python`。
2. 编译生成本地扩展（推荐重新编译以匹配当前平台）：
   ```bash
   python setup.py build_ext --inplace
   # 或直接安装为可编辑模式
   python -m pip install -e .
   ```
3. 运行示例：
   ```bash
   python call_mymath.py
   # 预期输出：10 + 20 = 30
   ```
4. 可用函数（Python 层）：`add_int(a, b)`、`add_double(a, b)`、`dot(x, y)`。

## C/C++ 调用 C 接口（目录：`C/`）
1. 进入目录：`cd python2native/C`。
2. 重新编译 Cython 扩展，生成符合当前平台的 `.so/.pyd`（示例为 Linux）：
   ```bash
   python setup.py build_ext --inplace
   ```
3. 头文件：`mymath_c_api.h` 声明了导出的 C 函数：
   - `int C_add_int(int a, int b);`
   - `double C_add_double(double a, double b);`
   - `double C_dot(double *x, double *y, int length);`（在 C 侧传入同长度数组）
4. Linux 下编译演示程序（`call_mymath_linux.cpp` 通过 `dlopen`/`dlsym` 调用 `.so`）：
   ```bash
   g++ call_mymath_linux.cpp -o call_mymath -ldl
   LD_LIBRARY_PATH=. ./call_mymath
   ```
   如未找到 `libpython3.12.so`，需按实际 Python 版本调整 `dlopen` 名称或链接路径。

## 关键点与提示
- `.so/.pyd` 与 Python 版本、平台、架构强相关，必须在目标环境重新编译。
- `mymath.pyx` 中使用 `cdef public` 导出 C 接口，便于在 Python 编译出的模块上直接获取原生函数符号。
- 若需要改用 C++，可将 `setup.py` 的 `language` 改为 `"c++"`，并调整编译指令。
- Windows 调用 C 接口时，请使用对应的编译器和 `.pyd` 名称，按需修改 `dlopen` 逻辑或直接链接导出符号。
