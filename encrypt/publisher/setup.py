# setup.py
from setuptools import setup, Extension
from Cython.Build import cythonize
import sys

# 如果你以后要用 C++，可以把 language 改成 "c++"
extensions = [
    Extension(
        name="encrypt_publisher_pkg",  # 编译后的模块名,import 时使用
        sources=["encrypt_publisher.pyx"],  # Cython 源文件
        language="c",  # 或 "c++"
    ),
    Extension(
        name="issue_keys",  # 编译后的模块名,import 时使用
        sources=["issue_keys.py"],  # Cython 源文件
        language="c",  # 或 "c++"
    ),
    Extension(
        name="issue_license",  # 编译后的模块名,import 时使用
        sources=["issue_license.py"],  # Cython 源文件
        language="c",  # 或 "c++"
    ),
    Extension(
        name="publisher_init",  # 编译后的模块名,import 时使用
        sources=["publisher_init.py"],  # Cython 源文件
        language="c",  # 或 "c++"
    ),
]

setup(
    name="encrypt_publisher",
    version="1.0.0",
    ext_modules=cythonize(
        extensions,
        compiler_directives={
            "language_level": "3",  # 使用 Python 3 语法
            "boundscheck": False,  # 关闭边界检查以提高性能（示例中可开可关）
            "wraparound": False,  # 关闭负索引支持
            "binding": True,
            "always_allow_keywords": True,  # 允许关键字注参
        },
        build_dir="build/cython",
    ),
)
