import ExamplePkg  # 导入打包后的 Python 包
import matlab  # 导入 MATLAB 引擎


# ==================================
# ★ 初始化 MATLAB Runtime 客户端
# ==================================
def _init_matlab_client():
    """
    启动 MATLAB Runtime，并加载导入的包。
    这一步会比较慢（几百 ms ~ 几秒），但只在进程启动时做一次。
    """
    print("[MATLAB] Initializing ExamplePkg client...")
    client = ExamplePkg.initialize()
    print("[MATLAB] ExamplePkg client initialized.")
    return client


MATLAB_CLIENT = _init_matlab_client()  # 进程启动时初始化

# 当然，初始化 MATLAB Runtime 客户端的代码可以用下面这种更加简洁的方式：
# MATLAB_CLIENT = ExamplePkg.initialize()

# ==================================
# ★ 调用 MATLAB 函数
# ==================================
a = 3.5
b = 2.7
add_status, add_result = MATLAB_CLIENT.add_func(
    float(a), float(b), nargout=2
)  # 注意输入参数的类型转换，以及 nargout 的使用，nargout 表示输出参数的个数
sub_status, sub_result = MATLAB_CLIENT.sub_func(
    float(a), float(b), nargout=2
)  # 注意输入参数的类型转换，以及 nargout 的使用，nargout 表示输出参数的个数

print(f"add_func({a}, {b}) = {add_result} (status: {add_status})")
print(f"sub_func({a}, {b}) = {sub_result} (status: {sub_status})")


# # ==================================
# # ★ 调用 MATLAB 类 TODO: matlab2024b 似乎依然不支持类的调用
# # ==================================
# # 创建类的实例
# class_instance = MATLAB_CLIENT.Class_example()
# # 调用类的方法
# class_instance = class_instance.add(float(a), float(b))  # 调用 add 方法
# print(f"Class_example.add({a}, {b}) = {class_instance.result}")
# class_instance = class_instance.subtract(float(a), float(b))  # 调用 subtract 方法
# print(f"Class_example.subtract({a}, {b}) = {class_instance.result}")

# ==================================
# ★ 关闭 MATLAB Runtime 客户端
# ==================================
MATLAB_CLIENT.terminate()
