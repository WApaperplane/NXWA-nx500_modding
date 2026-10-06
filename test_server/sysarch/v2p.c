/* v2p.c — 独立验证 SMA_VIRT_TO_PHYS（不依赖 SMA_ALLOC）
 *
 * =====================================================================
 * 【背景】SMA_ALLOC 实测全部返回 EFAULT：
 *     dmesg: d4_cma_alloc failed. Device is null or invalid argument
 *   ⇒ 三星这个驱动不给用户态分配 CMA。
 *
 * 【本工具测什么】
 *   SMA_VIRT_TO_PHYS 单独能不能用？
 *   ★ 若能用 ⇒ 我们可以走"自己 mmap 任意内存 → 问它物理地址"的路线，
 *     完全绕开 SMA_ALLOC。
 *   ★ 这正是 libudd5 的 load_lut 实际做的事：
 *       buf = 自己的内存; d5_ep_sma_virt_to_phys(buf) → DMA
 *     ⇒ 如果这条路通，import 就不需要任何"分配"，只需要拿到物理地址。
 *
 * ★★ 安全性：只做 virt→phys 查询 + 少量内存触碰，不写任何硬件寄存器。
 * =====================================================================
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <fcntl.h>
#include <sys/ioctl.h>
#include <sys/mman.h>
#include <errno.h>

#define SMA_VIRT_TO_PHYS 0xc0047302UL
#define SMA_GET_REGION_START_ADDR 0x80047304UL
#define SMA_GET_REGION_SIZE       0x80047301UL

int main(void)
{
    int fd;
    unsigned int val;
    int rc;
    void *p;
    unsigned int phys;

    fd = open("/dev/d5_sma", O_RDWR);
    if (fd < 0) { printf("open: %s\n", strerror(errno)); return 1; }

    val = 0;
    ioctl(fd, SMA_GET_REGION_START_ADDR, &val);
    printf("region start = 0x%08x\n", val);
    val = 0;
    ioctl(fd, SMA_GET_REGION_SIZE, &val);
    printf("region size  = 0x%08x\n", val);

    /* ---- 测试 1：普通 malloc 的堆内存 ---- */
    printf("\n=== 测试 1：malloc 堆内存 ===\n");
    {
        void *h = malloc(0x1000);
        unsigned int v = (unsigned)(unsigned long)h;
        printf("  malloc 0x1000 => virt 0x%08x\n", v);
        phys = v;
        rc = ioctl(fd, SMA_VIRT_TO_PHYS, &phys);
        printf("  VIRT_TO_PHYS => 0x%08x  rc=%d  %s\n", phys, rc,
               rc < 0 ? strerror(errno) : "★ 成功");
        free(h);
    }

    /* ---- 测试 2：mmap 匿名内存 ---- */
    printf("\n=== 测试 2：mmap 匿名（带标志）===\n");
    p = mmap(NULL, 0x1000, PROT_READ | PROT_WRITE,
             MAP_PRIVATE | MAP_ANONYMOUS, -1, 0);
    if (p == MAP_FAILED) { printf("  mmap 失败: %s\n", strerror(errno)); }
    else {
        unsigned int v = (unsigned)(unsigned long)p;
        *(volatile unsigned char *)p = 0xAB;
        printf("  mmap => virt 0x%08x (写入测试字节 0x%02x)\n",
               v, *(volatile unsigned char *)p);
        phys = v;
        rc = ioctl(fd, SMA_VIRT_TO_PHYS, &phys);
        printf("  VIRT_TO_PHYS => 0x%08x  rc=%d  %s\n", phys, rc,
               rc < 0 ? strerror(errno) : "★ 成功");
        munmap(p, 0x1000);
    }

    /* ---- 测试 3：mmap 到 /dev/d5_sma 的 region 物理地址 ---- */
    printf("\n=== 测试 3：mmap /dev/d5_sma @ 物理地址 0x94000000+64M ===\n");
    {
        unsigned int base;
        val = 0;
        ioctl(fd, SMA_GET_REGION_START_ADDR, &base);
        /* 选一个当前看起来空闲的偏移：+80M（0x5000000）*/
        p = mmap(NULL, 0x1000, PROT_READ | PROT_WRITE, MAP_SHARED,
                 fd, (off_t)(base + 0x5000000UL));
        if (p == MAP_FAILED) {
            printf("  mmap 失败: %s\n", strerror(errno));
        } else {
            unsigned int v = (unsigned)(unsigned long)p;
            unsigned char *u = (unsigned char *)p;
            printf("  mmap => virt 0x%08x\n", v);
            /* 只读探测，不写入 */
            printf("  该处前 8 字节（只读）:");
            printf(" %02x %02x %02x %02x %02x %02x %02x %02x\n",
                   u[0], u[1], u[2], u[3], u[4], u[5], u[6], u[7]);
            phys = v;
            rc = ioctl(fd, SMA_VIRT_TO_PHYS, &phys);
            printf("  VIRT_TO_PHYS => 0x%08x  rc=%d  %s\n", phys, rc,
                   rc < 0 ? strerror(errno) : "★ 成功");
            if (rc == 0 && phys != 0) {
                printf("  ★★ 物理地址 %s\n",
                       (phys == base + 0x5000000UL) ? "= 预期值 ✔"
                       : "≠ 预期（驱动做了偏移调整）");
            }
            munmap(p, 0x1000);
        }
    }

    close(fd);
    printf("\n★ 结论见上：VIRT_TO_PHYS 若可用 ⇒ import 不需要分配，\n");
    printf("  只要拿到任意可读写的物理地址即可。\n");
    return 0;
}
