/*
 * memread.c — 直接读 /dev/mem（ISP 寄存器窗口）
 *
 * 为什么不用 /proc/pid/mem：内核不允许跨进程读设备内存映射区（read 返回 -1）
 * 为什么不用 poker：它是 ptrace 机制，同样读不到 /dev/mem 映射
 *
 * 用法: memread <phys_start_hex> <len_hex> [out_file]
 *   例: memread 0x99600000 0x800000 /mnt/mmc/regs.bin
 */
#define _GNU_SOURCE
#include <fcntl.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

int main(int argc, char **argv) {
    if (argc < 3) {
        fprintf(stderr, "用法: memread <phys_start_hex> <len_hex> [out_file]\n");
        fprintf(stderr, "说明: 物理地址 = 虚拟地址 + 0xB7FC000\n");
        return 1;
    }
    unsigned long phys = strtoul(argv[1], 0, 0);
    unsigned long len = strtoul(argv[2], 0, 0);

    int fd = open("/dev/mem", O_RDONLY);
    if (fd < 0) { perror("open /dev/mem"); return 1; }
    /* ★ 用 pread 避开 lseek 的 off_t 溢出问题 */

    unsigned char *buf = malloc(len);
    if (!buf) { fprintf(stderr, "malloc %lu 失败\n", len); close(fd); return 1; }
    ssize_t n = pread(fd, buf, len, (off_t)phys);
    close(fd);
    if (n <= 0) { fprintf(stderr, "read 失败: %zd\n", n); free(buf); return 1; }
    fprintf(stderr, "已读 %zd 字节 (物理 0x%lx)\n", n, phys);

    if (argc >= 4) {
        FILE *f = fopen(argv[3], "wb");
        if (!f) { perror("fopen"); free(buf); return 1; }
        fwrite(buf, 1, n, f);
        fclose(f);
        fprintf(stderr, "已写入 %s\n", argv[3]);
    }

    /* 顺便统计非零块，打到 stdout */
    printf("# 非零块（256B 粒度）\n");
    int blocks = 0;
    for (long i = 0; i + 256 <= n; i += 256) {
        int nz = 0;
        for (int k = 0; k < 256; k++) if (buf[i + k]) nz++;
        if (!nz) continue;
        blocks++;
        printf("0x%08lx %3d ", phys + i, nz);
        for (int k = 0; k < 16; k++) printf("%02x", buf[i + k]);
        printf("\n");
        if (blocks > 4000) { printf("...\n"); break; }
    }
    fprintf(stderr, "共 %d 个非零块\n", blocks);
    free(buf);
    return 0;
}
