# setup.py
from setuptools import setup, Extension
from Cython.Build import cythonize
import sys

# 如果你以后要用 C++，可以把 language 改成 "c++"
extensions = [
    Extension(
        name="encrypt_customer",  # 编译后模块名：import mymath
        sources=["encrypt_customer.pyx"],  # Cython 源文件
        language="c",  # 或 "c++"
    ),
    Extension(
        name="license_guard",  # 编译后模块名：import mymath
        sources=["license_guard.py"],  # Cython 源文件
        language="c",  # 或 "c++"
    ),
]

setup(
    name="encrypt_customer",
    version="1.0.0",
    ext_modules=cythonize(
        extensions,
        compiler_directives={
            "language_level": "3",  # 使用 Python 3 语法
            "boundscheck": False,  # 关闭边界检查以提高性能（示例中可开可关）
            "wraparound": False,  # 关闭负索引支持
        },
        build_dir="build/cython",
    ),
)
