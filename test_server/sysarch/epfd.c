/* epfd.c — NX-KS2 步骤 1b：读 camera app 进程里的 libudd5 全局变量（纯只读）
 *
 * ★ 目的：解决"跨进程读指针"死锁。
 *   v1 探针在自己进程里 dlopen，读到 fd_ep = -1 —— 那是**我的**地址空间，
 *   不能说明 di-camera-app 里的值。v4 探针直接解引用跨进程地址 => 死机。
 *   本探针用 lseek+read 纯读 /proc/<pid>/mem，不 ptrace、不写、不 attach。
 *
 * ★ 安全边界（硬性）：
 *   1. 只 O_RDONLY 打开 /proc/PID/mem
 *   2. 只读 4 字节，绝不写
 *   3. 读失败只报错，不重试、不改地址
 *   4. 不调用 libudd5 任何函数
 *
 * 用法:
 *   单个: ./epfd <pid> <map_base> <st_value> <seg_va_page>
 *   批量: ./epfd -B <pid> <map_base> <seg_va_page> <name=st_value> ...
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <fcntl.h>

static char path[64];

static unsigned rd32(int fd, unsigned long a)
{
    unsigned char b[4];
    if (lseek(fd, (off_t)a, SEEK_SET) == (off_t)-1) return 0xdeadbeef;
    if (read(fd, b, 4) != 4) return 0xdeadbeef;
    return (unsigned)b[0] | ((unsigned)b[1] << 8)
         | ((unsigned)b[2] << 16) | ((unsigned)b[3] << 24);
}

int main(int argc, char **argv)
{
    unsigned long pid, sb, sv;
    int fd, k;

    if (argc >= 6 && strcmp(argv[1], "-B") == 0) {
        pid = strtoul(argv[2], NULL, 0);
        sb  = strtoul(argv[3], NULL, 0);
        sv  = strtoul(argv[4], NULL, 0);
        snprintf(path, sizeof(path), "/proc/%lu/mem", pid);
        fd = open(path, O_RDONLY);
        if (fd < 0) { perror("open"); return 3; }
        printf("batch: pid=%lu seg=0x%lx va_page=0x%lx\n", pid, sb, sv);
        printf("%-36s %-10s %-10s %s\n", "symbol", "st_value", "value", "note");
        for (k = 5; k < argc; k++) {
            char *eq = strchr(argv[k], '=');
            unsigned long a;
            unsigned v;
            if (!eq) continue;
            *eq = 0;
            a = strtoul(eq + 1, NULL, 0);
            v = rd32(fd, sb + (a - sv));
            *eq = '=';
            if (v == 0xdeadbeef)
                printf("%-36s 0x%08lx  <io fail>\n", argv[k], a);
            else if (v == 0xffffffffu)
                printf("%-36s 0x%08lx  0x%08x  -1 uninit\n", argv[k], a, v);
            else if (v == 0)
                printf("%-36s 0x%08lx  0x%08x  NULL\n", argv[k], a, v);
            else if (v > 0xb0000000u)
                printf("%-36s 0x%08lx  0x%08x  ptr\n", argv[k], a, v);
            else
                printf("%-36s 0x%08lx  0x%08x  int %d\n", argv[k], a, v, (int)v);
        }
        close(fd);
        printf("\n=== end: pure read ===\n");
        return 0;
    }

    if (argc < 5) {
        printf("usage: %s <pid> <map_base> <st_value> <seg_va_page>\n", argv[0]);
        printf("  ex : %s 247 0xb0e75000 0x5556c 0x54000\n", argv[0]);
        return 1;
    }
    /* 扩展模式：<pid> <addr> <len> -D   直接 dump 任意地址的字节（十六进制+ASCII）
     * 用于反汇编 camera app 进程里的 libudd5 代码段（/dev/mem 读内核代码会 SIGBUS） */
    if (argc == 5 && strcmp(argv[4], "-D") == 0) {
        unsigned long a = strtoul(argv[2], NULL, 0);
        unsigned long n = strtoul(argv[3], NULL, 0);
        unsigned char *b;
        unsigned long i;
        if (n == 0 || n > 0x4000) { printf("bad len\n"); return 1; }
        snprintf(path, sizeof(path), "/proc/%s/mem", argv[1]);
        fd = open(path, O_RDONLY);
        if (fd < 0) { perror("open"); return 3; }
        b = malloc(n);
        if (lseek(fd, (off_t)a, SEEK_SET) == (off_t)-1) { perror("lseek"); return 5; }
        if (read(fd, b, n) != (ssize_t)n) { printf("read short\n"); return 4; }
        close(fd);
        printf("dump %lu bytes @ 0x%08lx\n\n", n, a);
        for (i = 0; i < n; i += 16) {
            unsigned k;
            printf("%08lx  ", a + i);
            for (k = 0; k < 16 && i + k < n; k++) printf("%02x ", b[i + k]);
            for (; k < 16; k++) printf("   ");
            printf(" |");
            for (k = 0; k < 16 && i + k < n; k++) {
                unsigned char c = b[i + k];
                printf("%c", (c >= 32 && c < 127) ? c : '.');
            }
            printf("|\n");
        }
        printf("\n=== end: pure read ===\n");
        free(b);
        return 0;
    }
    pid = strtoul(argv[1], NULL, 0);
    sb  = strtoul(argv[2], NULL, 0);
    sv  = strtoul(argv[4], NULL, 0);

    {
        unsigned long slot = strtoul(argv[3], NULL, 0);
        unsigned long rt;
        unsigned v;
        if (slot < sv) {
            printf("err: st_value 0x%lx < va_page 0x%lx\n", slot, sv);
            return 2;
        }
        rt = sb + (slot - sv);
        snprintf(path, sizeof(path), "/proc/%lu/mem", pid);
        fd = open(path, O_RDONLY);
        if (fd < 0) { perror("open"); return 3; }
        printf("%s opened O_RDONLY\n", path);
        printf("runtime_addr = 0x%08lx\n", rt);
        v = rd32(fd, rt);
        close(fd);
        if (v == 0xdeadbeef) { printf("io fail\n"); return 4; }
        printf("4 bytes LE u32 = 0x%08x (%d)\n", v, (int)v);
        if (v == 0xffffffffu)
            printf("=> -1  EP NOT open in that process\n");
        else if ((int)v >= 0)
            printf("=> %d  EP IS open\n", (int)v);
        else
            printf("=> %d (other negative)\n", (int)v);
    }
    printf("\n=== end: pure read ===\n");
    return 0;
}