/* smaalloc.c — NX-KS2 CMA 动态分配验证工具
 *
 * =====================================================================
 * ★★★ 2026-10-06 卡死事故后的正解
 *---------------------------------------------------------------------
 * 【事故】硬编码 `0x94000000` 写 LUT ⇒ 相机卡死（拔电池才恢复）
 *   根因：那块内存是 ISP 的 WDMA 硬件工作区，"探测空闲"≠ 可安全独占
 *
 * 【正解】用官方 SMA_ALLOC 动态分配，让内核保证不冲突
 *
 * ★ 官方接口（NX1 GPL 包，头文件是权威，不是我猜的）：
 *   .uploads/nx1_open/rootfs_dev/.../media/drime5/sma/d5_sma_ioctl.h
 *     #define SMA_MAGIC 's'
 *     SMA_GET_REGION_SIZE        _IOR('s', 1, unsigned int)
 *     SMA_VIRT_TO_PHYS_IOWR('s', 2, unsigned int)★ libudd5 用的就是这个
 *     SMA_SET_CACHE              _IOWR('s', 3, int)
 *     SMA_GET_REGION_START_ADDR  _IOR('s', 4, unsigned int)
 *     SMA_ALLOC                  _IOWR('s', 5, struct SMA_Buffer_Info)  ★ 本工具核心
 *     SMA_FREE                   _IO('s', 6, unsigned int)   ← 虚拟地址
 *     SMA_FREE_PHYS              _IO('s', 7, unsigned int)   ← 物理地址
 *     SMA_GET_ALLOCATED_SIZE     _IOR('s', 8, unsigned int)
 *     SMA_CACHE_FLUSH            _IOWR('s', 9, struct SMA_Buffer_Info)  ★ DMA 前必须
 *
 *   struct SMA_Buffer_Info { unsigned int addr; unsigned int size; };
 *
 * ★★ 交叉验证（已做）：
 *   按_IOWR('s',2,4) 算出 0xc0047302，与 libudd5 反汇编里
 *   `d5_ep_sma_virt_to_phys` 用的号完全一致 ⇒ 编码方式正确
 *
 * 用法:
 *   smaallocprobe              ★ 只探测（分配+读回+释放，不写硬件）
 *   smaalloc alloc <size>      分配并打印地址
 *   smaalloc free  <virt>      按虚拟地址释放
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

/* ★ ioctl 号：自己算，不用宏（宏会 32 位溢出）*/
#define SMA_MAGIC          's'
#define SMA_GET_REGION_SIZE      0x80047301UL
#define SMA_VIRT_TO_PHYS 0xc0047302UL
#define SMA_GET_REGION_START_ADDR 0x80047304UL
#define SMA_ALLOC          0xc0087305UL
#define SMA_FREE           0x40047306UL
#define SMA_FREE_PHYS      0x40047307UL
#define SMA_GET_ALLOCATED_SIZE   0x80047308UL
#define SMA_CACHE_FLUSH    0xc0087309UL

struct sma_buf {
    unsigned int addr;
    unsigned int size;
};

int main(int argc, char **argv)
{
    int fd;
    unsigned int val = 0;
    int rc;

    if (argc >= 2 && strcmp(argv[1], "alloc") == 0) {
        unsigned int sz = (argc > 2) ? (unsigned)atoi(argv[2]) : 0x3000;
        struct sma_buf b;
        b.addr = 0;
        b.size = sz;
        fd = open("/dev/d5_sma", O_RDWR);
        if (fd < 0) { printf("open: %s\n", strerror(errno)); return 1; }
        rc = ioctl(fd, SMA_ALLOC, &b);
        if (rc < 0) { printf("SMA_ALLOC failed: %s\n", strerror(errno)); close(fd); return 2; }
        printf("SMA_ALLOC size=%u => virt 0x%08x\n", sz, b.addr);
        close(fd);
        return 0;
    }

    if (argc >= 3 && strcmp(argv[1], "free") == 0) {
        unsigned int v = (unsigned)strtoul(argv[2], NULL, 0);
        fd = open("/dev/d5_sma", O_RDWR);
        if (fd < 0) { printf("open: %s\n", strerror(errno)); return 1; }
        rc = ioctl(fd, SMA_FREE, &v);
        printf("SMA_FREE(0x%08x) = %d %s\n", v, rc, rc < 0 ? strerror(errno) : "OK");
        close(fd);
        return rc < 0 ? 3 : 0;
    }

    /* ============ 默认：探测模式（只读+临时分配，安全）============ */
    printf("==== SMA (Shared Memory Allocator) 探测 ====\n\n");

    fd = open("/dev/d5_sma", O_RDWR);
    if (fd < 0) { printf("open /dev/d5_sma: %s\n", strerror(errno)); return 1; }
    printf("设备打开成功 fd=%d\n", fd);

    /* ---- 区域信息 ---- */
    val = 0;
    rc = ioctl(fd, SMA_GET_REGION_START_ADDR, &val);
    printf("\n[1] SMA_GET_REGION_START_ADDR => 0x%08x  (rc=%d) %s\n",
           val, rc, rc < 0 ? strerror(errno) : "");

    val = 0;
    rc = ioctl(fd, SMA_GET_REGION_SIZE, &val);
    printf("[2] SMA_GET_REGION_SIZE       => 0x%08x (%u KB)  (rc=%d) %s\n",
           val, val / 1024, rc, rc < 0 ? strerror(errno) : "");

    val = 0;
    rc = ioctl(fd, SMA_GET_ALLOCATED_SIZE, &val);
    printf("[3] SMA_GET_ALLOCATED_SIZE    => 0x%08x (%u KB)  (rc=%d) %s\n",
           val, val / 1024, rc, rc < 0 ? strerror(errno) : "");

    /* ---- ★核心：动态分配 ---- */
    {
        struct sma_buf b;
        unsigned int want = 0x4000;          /* 16 KB，够放 9826 字节表 */
        unsigned int phys;

        b.addr = 0;
        b.size = want;
        printf("\n[4] ★ SMA_ALLOC 动态分配 %u 字节 ...\n", want);
        rc = ioctl(fd, SMA_ALLOC, &b);
        if (rc < 0) {
            printf("    SMA_ALLOC 失败: %s\n", strerror(errno));
            printf("    ★ 可能 CMA 内存不足（dmesg 见 MemFree）\n");
            close(fd);
            return 2;
        }
        printf("    ★ 分配成功: virt 0x%08x\n", b.addr);

        /* ---- 虚拟 → 物理 ---- */
        phys = b.addr;
        rc = ioctl(fd, SMA_VIRT_TO_PHYS, &phys);
        printf("[5] SMA_VIRT_TO_PHYS          => phys 0x%08x  (rc=%d) %s\n",
               phys, rc, rc < 0 ? strerror(errno) : "");
        if (rc == 0 && phys != 0) {
            printf("    ★★ 物理地址 0x%08x\n", phys);
            printf("        落在 region [0x%08x] 内 ?\n", val);
        }

        /* ---- 写签名并回读，验证可读写 ---- */
        if (b.addr) {
            void *p = mmap(NULL, want, PROT_READ | PROT_WRITE, MAP_SHARED,
                           fd, (off_t)b.addr);
            if (p != MAP_FAILED) {
                unsigned char *u = (unsigned char *)p;
                int i;
                for (i = 0; i < 64; i++) u[i] = (unsigned char)(i * 7 + 1);
                printf("[6] 写入签名后回读:");
                for (i = 0; i < 16; i++) printf(" %02x", u[i]);
                printf("\n");
                /* cache flush（DMA 前必须）*/
                {
                    struct sma_buf fb;
                    fb.addr = b.addr;
                    fb.size = want;
                    rc = ioctl(fd, SMA_CACHE_FLUSH, &fb);
                    printf("[7] SMA_CACHE_FLUSH= %d %s\n",
                           rc, rc < 0 ? strerror(errno) : "OK ★");
                }
                munmap(p, want);
            } else {
                printf("[6] mmap 自身缓冲失败: %s\n", strerror(errno));
                printf("    ★ 正常：SMA 内存只能通过 phys 访问，不能直接 mmap\n");
            }
        }

        /* ---- 立即释放，不占用 ---- */
        {
            unsigned int v = b.addr;
            rc = ioctl(fd, SMA_FREE, &v);
            printf("[8] SMA_FREE(0x%08x)         = %d %s\n",
                   b.addr, rc, rc < 0 ? strerror(errno) : "OK ★ 已释放");
        }
    }

    /* ---- 分配后总占用 ---- */
    val = 0;
    rc = ioctl(fd, SMA_GET_ALLOCATED_SIZE, &val);
    printf("\n[9] 释放后 SMA_GET_ALLOCATED_SIZE = %u KB (rc=%d)\n", val / 1024, rc);

    close(fd);
    printf("\n★ 结论：动态分配【可用】⇒ 以后 LUT 落地用它，不再硬编码物理地址。\n");
    return 0;
}
