/*
 * heapscan.c — 在指定内存段里搜 4 字节目标值
 *
 * 思路：直接从 /proc/<pid>/mem 读（比 poker 逐个读快几万倍）
 *用法: heapscan <pid> <start_hex> <end_hex> <target_hex> [max_hits]
 *
 * 例: heapscan 252 0x0049e000 0x007ff000 0xb4c6b0f8
 */
#define _GNU_SOURCE
#include <fcntl.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

int main(int argc, char **argv) {
    if (argc < 5) {
        emit_usage:
        fprintf(stderr, "用法: heapscan <pid> <start_hex> <end_hex> <target_hex>\n");
        return 1;
    }
    int pid = atoi(argv[1]);
    unsigned long start = strtoul(argv[2], 0, 0);
    unsigned long end = strtoul(argv[3], 0, 0);
    unsigned long target = strtoul(argv[4], 0, 0);

    char path[64];
    snprintf(path, sizeof(path), "/proc/%d/mem", pid);
    int fd = open(path, O_RDONLY);
    if (fd < 0) { perror("open mem"); return 1; }
    if (lseek(fd, (off_t)start, SEEK_SET) < 0) { perror("lseek"); close(fd); return 1; }

    unsigned long len = end - start;
    if (len > 64UL * 1024 * 1024) len = 64UL * 1024 * 1024;  /* 上限 64MB */
    unsigned char *buf = malloc(len);
    if (!buf) { fprintf(stderr, "malloc %lu 失败\n", len); close(fd); return 1; }

    ssize_t n = read(fd, buf, len);
    close(fd);
    if (n <= 0) { fprintf(stderr, "read 失败: %zd\n", n); free(buf); return 1; }
    fprintf(stderr, "已读 %zd 字节 (0x%lx-0x%lx)，搜索 0x%lx\n", n, start, start + n, target);

    unsigned char pat[4];
    pat[0] = target & 0xff;
    pat[1] = (target >> 8) & 0xff;
    pat[2] = (target >> 16) & 0xff;
    pat[3] = (target >> 24) & 0xff;

    int hits = 0;
    for (long i = 0; i + 4 <= n; i += 4) {
        if (buf[i] == pat[0] && buf[i+1] == pat[1] &&
            buf[i+2] == pat[2] && buf[i+3] == pat[3]) {
            printf("HIT 0x%08lx  (段内偏移 +0x%lx)\n", start + i, i);
            hits++;
            /* 打印上下文 16 字节 */
            long s = i - 16 < 0 ? 0 : i - 16;
            fprintf(stderr, "     上下文:");
            for (long k = s; k < i + 20 && k < n; k++)
                fprintf(stderr, " %02x", buf[k]);
            fprintf(stderr, "\n");
            if (hits >= 40) { fprintf(stderr, "... 太多，停止\n"); break; }
        }
    }
    fprintf(stderr, "共 %d 个命中\n", hits);
    free(buf);
    return 0;
}
