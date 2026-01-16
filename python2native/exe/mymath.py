# mymath.pyx
# 简单示例：提供几个函数，演示 Cython 编译

# cpdef: 既能被 Python 调用，也能在 C层被调用（后面扩展 DLL 用得上）
def add_int( a,  b):
    """
    整数加法：a + b
    """
    return a + b

def  add_double( a,  b):
    """
    浮点加法：a + b
    """
    return a + b


