#pragma once
#include <stdlib.h>
#include <stdio.h>
#include <stdarg.h>

static inline void EXIT_Error(const char *a1, ...)
{
    va_list args;

    va_start(args, a1);
    vfprintf(stderr, a1, args);
    va_end(args);
    fputc('\n', stderr);
    exit(0);
}

static inline void EXIT_Clean(void)
{
    exit(0);
}

static inline void EXIT_Install(void (*a1)(int a1))
{

}
