/* NX-KS2 阶段2A：第一个 ARM 交叉编译验证程序
 * 验证工具链 + EABI5 softfp ABI + glibc 动态链接 */
#include <stdio.h>

int main(void) {
    float pi = 3.14159265f;
    double e = 2.718281828;
    printf("[NX-KS2] ARM ELF OK: pi=%.5f e=%.6f (softfp EABI5)\n", pi, e);
    return 0;
}
