// mymath_c_api.h
#pragma once

#ifdef __cplusplus
extern "C"
{
#endif

    int C_add_int(int a, int b);
    double C_add_double(double a, double b);
    double C_dot(double *x, double *y, int length);

#ifdef __cplusplus
}
#endif
