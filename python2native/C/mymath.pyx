# mymath.pyx
# 简单示例：提供几个函数，演示 Cython 编译

# ==========================
# 👇导出给 python 调用的函数
# ==========================

cpdef int add_int(int a, int b):
    """
    整数加法：a + b
    """
    return a + b

cpdef double add_double(double a, double b):
    """
    浮点加法：a + b
    """
    return a + b

cpdef double dot(double[:] x, double[:] y):
    """
    计算两个等长向量的点积
    参数使用 Cython 的 memoryview，性能更好
    """
    cdef Py_ssize_t n = x.shape[0]
    cdef Py_ssize_t i
    cdef double s = 0.0
    for i in range(n):
        s += x[i] * y[i]
    return s

# ==========================
# 👇导出给 C/C++ 调用的 C 函数
# ==========================

cdef public int C_add_int(int a, int b):
    """
    C 接口：调用内部的 add_int
    """
    return add_int(a, b)

cdef public double C_add_double(double a, double b):
    """
    C 接口：调用内部的 add_double
    """
    return add_double(a, b)

cdef public double C_dot(double[:] x, double[:] y):
    """
    C 接口：调用内部的 dot
    """
    return dot(x, y)