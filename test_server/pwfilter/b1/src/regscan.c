/*
 * regscan.c — 扫描 ISP 寄存器窗口，找非零区域
 *
 * 用途：reg_base = 0x0103b7f 已知，但 Samsung ISP 寄存器编码的位域不明。
 * 做法：直接扫 /dev/mem 映射的 8MB 窗口，看哪些区域有数据。
 *
 * 用法: regscan <pid> <start_hex> <len_hex>
 *   读 /proc/<pid>/mem 而非 /dev/mem（无需 root 设备节点）
 */
#define _GNU_SOURCE
#include <fcntl.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

int main(int argc, char **argv) {
    if (argc < 4) {
        fprintf(stderr, "用法: regscan <pid> <start_hex> <len_hex>\n");
        return 1;
    }
    int pid = atoi(argv[1]);
    unsigned long start = strtoul(argv[2], 0, 0);
    unsigned long len = strtoul(argv[3], 0, 0);

    char path[64];
    snprintf(path, sizeof(path), "/proc/%d/mem", pid);
    int fd = open(path, O_RDONLY);
    if (fd < 0) { perror("open"); return 1; }
    if (lseek(fd, (off_t)start, SEEK_SET) < 0) { perror("lseek"); close(fd); return 1; }

    unsigned char *buf = malloc(len);
    if (!buf) { fprintf(stderr, "malloc失败\n"); close(fd); return 1; }
    ssize_t n = read(fd, buf, len);
    close(fd);
    if (n <= 0) { fprintf(stderr, "read失败: %zd\n", n); free(buf); return 1; }
    fprintf(stderr, "已读 %zd 字节 0x%lx-0x%lx\n", n, start, start + n);

    /* 按 256 字节块统计非零率，输出有数据的块 */
    printf("# 非零块（256B 粒度），只列有数据的\n");
    printf("# 格式: 虚拟地址  非零字节数  前16字节hex\n");
    int blocks = 0;
    for (long i = 0; i + 256 <= n; i += 256) {
        int nz = 0;
        for (int k = 0; k < 256; k++)
            if (buf[i + k]) nz++;
        if (nz == 0) continue;
        blocks++;
        printf("0x%08lx  %3d/256  ", start + i, nz);
        for (int k = 0; k < 16; k++) printf("%02x", buf[i + k]);
        printf("\n");
        if (blocks > 3000) { printf("... 太多\n"); break; }
    }
    fprintf(stderr, "共 %d 个非零块\n", blocks);
    free(buf);
    return 0;
}
