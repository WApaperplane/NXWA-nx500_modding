/* cmaprobe.c — NX-KS2：只读探测 CMA 区（零风险）
 *
 * ★ 目的：判断 CMA 区（0x94000000..0x9d000000）里是否有正在使用的数据。
 *   - 若有大量非零 ⇒ 内核/ISP 正在用，直接"借用"风险高
 *   - 若大面积为零 ⇒ 说明是预留但未用，借用一块风险低
 *
 * ★★ 只读：PROT_READ，绝不写。
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <fcntl.h>
#include <sys/ioctl.h>
#include <sys/mman.h>
#include <errno.h>

#include <media/drime5/sma/d5_sma_ioctl.h>

#define CMA_START 0x94000000UL
#define CMA_SIZE  0x09000000UL   /* 144 MB */

int main(int argc, char **argv)
{
    int fd;
    unsigned long addr;
    unsigned long probe = 0;
    unsigned long step = 0x100000;      /* 每 1MB 采一个点 */
    unsigned long nz = 0, total = 0;
    unsigned long first_nz = 0, last_nz = 0;
    int found;

    fd = open("/dev/d5_sma", O_RDONLY);
    if (fd < 0) { printf("open d5_sma: %s\n", strerror(errno)); return 2; }
    {
        unsigned rs = 0, rz = 0;
        if (ioctl(fd, SMA_GET_REGION_START_ADDR, &rs) == 0)
            printf("ioctl region start = 0x%08x\n", rs);
        if (ioctl(fd, SMA_GET_REGION_SIZE, &rz) == 0)
            printf("ioctl region size  = 0x%08x\n", rz);
    }
    printf("\n");

    fd = open("/dev/mem", O_RDONLY | O_SYNC);
    if (fd < 0) { printf("open /dev/mem: %s\n", strerror(errno)); return 3; }

    printf("--- CMA 区采样（每 1MB 取16 words）---\n");
    printf("区间 0x%08lx .. 0x%08lx (%lu MB)\n\n",
           CMA_START, CMA_START + CMA_SIZE, CMA_SIZE >> 20);

    found = 0;
    for (addr = CMA_START; addr < CMA_START + CMA_SIZE; addr += step) {
        volatile unsigned *p;
        int i, any = 0;
        unsigned long sum = 0;

        p = mmap(NULL, 4096, PROT_READ, MAP_SHARED, fd, (off_t)addr);
        if (p == MAP_FAILED) {
            printf("  0x%08lx  <mmap fail: %s>\n", addr, strerror(errno));
            continue;
        }
        for (i = 0; i < 16; i++) { sum += p[i]; if (p[i]) any = 1; }
        munmap((void *)p, 4096);

        total++;
        if (any) {
            nz++;
            if (!found) { first_nz = addr; found = 1; }
            last_nz = addr;
            if (nz <= 30)
                printf("  0x%08lx  ★非零 sum=%lu\n", addr, sum);
        } else if (nz <= 30) {
            printf("  0x%08lx  zero\n", addr);
        }
    }

    printf("\n--- 统计 ---\n");
    printf("  采样点= %lu\n", total);
    printf("  非零点 = %lu (%.1f%%)\n", nz, total ? (double)nz * 100.0 / total : 0.0);
    if (found) {
        printf("  非零范围= 0x%08lx .. 0x%08lx\n", first_nz, last_nz);
        printf("  ⇒★ CMA 区【正在使用】\n");
        printf("     直接 mmap 借用风险高（可能撞上正在跑的 DMA 缓冲）\n");
    } else {
        printf("  ⇒ ★★★ CMA 区【完全空闲】！\n");
        printf("     可以在此安全分配 LUT 缓冲（先写 identity 验证）\n");
    }

    close(fd);
    return 0;
}