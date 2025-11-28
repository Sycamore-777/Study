// test_linux.cpp
#include <dlfcn.h>
#include <iostream>
#include "mymath_c_api.h"

typedef int (*C_add_int_t)(int, int);
typedef double (*C_add_double_t)(double, double);

int main()
{
    // 0. 预加载 Python 动态库，解决依赖问题，如果找不到这个文件，使用python3.12-config --ldflags
    void *hpy = dlopen("libpython3.12.so", RTLD_NOW | RTLD_GLOBAL); // libpython3.12.so确保和你的封装环境一致
    if (!hpy)
    {
        std::cerr << "dlopen libpython error: " << dlerror() << std::endl;
        return 1;
    }

    // 1. 加载 so
    void *handle = dlopen("./mymath.cpython-312-x86_64-linux-gnu.so", RTLD_NOW);
    if (!handle)
    {
        std::cerr << "dlopen error: " << dlerror() << std::endl;
        return 1;
    }

    dlerror(); // 清空旧错误

    // 2. 获取符号
    C_add_int_t C_add_int_func =
        (C_add_int_t)dlsym(handle, "C_add_int");
    const char *err = dlerror();
    if (err)
    {
        std::cerr << "dlsym(C_add_int) error: " << err << std::endl;
        dlclose(handle);
        return 1;
    }

    C_add_double_t C_add_double_func =
        (C_add_double_t)dlsym(handle, "C_add_double");
    err = dlerror();
    if (err)
    {
        std::cerr << "dlsym(C_add_double) error: " << err << std::endl;
        dlclose(handle);
        return 1;
    }

    // 3. 调用
    std::cout << "C_add_int(2, 3) = " << C_add_int_func(2, 3) << std::endl;
    std::cout << "C_add_double(1.5, 2.5) = "
              << C_add_double_func(1.5, 2.5) << std::endl;

    // 4. 关闭 so
    dlclose(handle);
    return 0;
}
