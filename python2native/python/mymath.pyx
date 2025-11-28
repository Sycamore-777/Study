# mymath.pyx
# 简单示例：提供几个函数，演示 Cython 编译

# cpdef: 既能被 Python 调用，也能在 C层被调用（后面扩展 DLL 用得上）
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
