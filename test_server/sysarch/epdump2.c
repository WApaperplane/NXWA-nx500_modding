/* epdump2.c — NX-KS2 步骤 2b：mmap EP 块并 dump 现状（只读，零风险）
 *
 * ★ 承接 epinfo.c 的成果：内核已权威给出 10 个块的 phys_start + size。
 *   本步用 mmap 把 3DLUT 块（魔灯目标）映射进本进程并**只读** dump 现有值。
 *
 * ★★★ 关键：d5_ep_mmap 的实现是
 *      io_remap_pfn_range(vma, vm_start, vm_pgoff, size, ...)
 *   ⇒ vm_pgoff 就是物理页帧号 ⇒ mmap 的 offset 参数 = phys_start >> 12
 *   ⇒ 不需要任何偏移猜测，一次成功。
 *
 * ★ 安全边界：
 *   1. open 用 O_RDONLY
 *   2. mmap 用 PROT_READ（★不可写）
 *   3. 只读、只打印，一个字节都不写
 *   4. 不调用 libudd5 任何函数
 *
 * 用法: epdump2 [block_index]   默认 8 (=3dlut)
 *   block: 0=top 1=ldc 2=mc 3=rsz 4=lvr 5=bblt 6=fd 7=jpeg 8=3dlut 9=nog
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <fcntl.h>
#include <sys/ioctl.h>
#include <sys/mman.h>
#include <errno.h>

#include <media/drime5/ep/d5_ep_ioctl.h>

static const char *NAMES[] = {
    "top", "ldc", "mc", "rsz", "lvr", "bblt", "fd", "jpeg", "3dlut", "nog"
};
#define NBLK ((int)(sizeof(NAMES) / sizeof(NAMES[0])))

static struct ep_reg_phys_info *blk(struct ep_reg_info *p, int i)
{
    return (struct ep_reg_phys_info *)((char *)p + i * sizeof(struct ep_reg_phys_info));
}

int main(int argc, char **argv)
{
    struct ep_reg_info info;
    int fd, i, ret, want, full = 0;
    unsigned pgoff;
    volatile unsigned *map_base; unsigned long map_len;
    unsigned long pa, size;
    volatile unsigned *p;
    unsigned nonzero;

    if (argc > 1 && strcmp(argv[1], "all") == 0) {
        want = 8;/* 3dlut 全量 baseline */
        full = 1;
    } else
    want = (argc > 1) ? atoi(argv[1]) : 8;
    if (want < 0 || want >= NBLK) {
        printf("block index 0..%d\n", NBLK - 1);
        return 1;
    }

    printf("=== NX-KS2 EP 块 mmap dump（只读）===\n");
    printf("目标块: %s (index %d)\n\n", NAMES[want], want);

    fd = open("/dev/drime5_ep", O_RDONLY);
    if (fd < 0) { printf("open failed: %s\n", strerror(errno)); return 2; }
    printf("open(/dev/drime5_ep, O_RDONLY) = fd %d ★\n", fd);

    memset(&info, 0, sizeof(info));
    ret = ioctl(fd, EP_IOCTL_GET_PHYS_REG_INFO, &info);
    if (ret < 0) { printf("ioctl failed: %s\n", strerror(errno)); close(fd); return 3; }
    printf("ioctl(GET_PHYS_REG_INFO) OK\n\n");

    pa   = blk(&info, want)->reg_start_addr;
    size = blk(&info, want)->reg_size;
    pgoff = (unsigned)(pa >> 12);
    printf("phys_start = 0x%08lx\n", pa);
    printf("size       = 0x%08lx (%lu bytes)\n", size, size);
    printf("want pgoff = phys>>12 = 0x%05x（内核 vm_pgoff 要的是 PFN）\n\n", pgoff);

    /* ★★★ 只读映射，绝不给写权限
     * ★★ mmap 的 offset 参数单位是【字节】，内核会自己 >>PAGE_SHIFT 转成 PFN。
     *    所以这里必须传 phys_start【原值】，不能传 phys_start>>12
     *    （传 PFN 会导致 vm_pgoff 少 12 位 => EINVAL）。
     * ★★ 小于一页的块（如 nog 只有 0x100 = 256B）必须把【长度】向上对齐到页，
     *    否则 io_remap_pfn_range 按整页处理会 EINVAL。 */
    {
        unsigned long msize = (size + 4095) & ~4095UL;
        unsigned long mbase = pa & ~4095UL;

        p = mmap(NULL, msize, PROT_READ, MAP_SHARED, fd, (off_t)mbase);
        if (p == MAP_FAILED) {
            printf("mmap(PROT_READ) 失败: %s\n", strerror(errno));
            printf("  · errno=%d  EACCES=%d / ENODEV=%d=驱动未绑定\n",
                   errno, EACCES, ENODEV);
            close(fd);
            return 4;
        }
        if (msize != size)
            printf("  ★ size 0x%lx < 一页，已向上对齐到 0x%lx（页内偏移 0x%lx）\n",
                   size, msize, pa - mbase);
        map_base = p;                 /* munmap 用 */
        map_len  = msize;
        p += (pa - mbase) / 4;         /* ★ 跳过页内偏移（word 数） */
        printf("mmap(PROT_READ, MAP_SHARED, fd, 0x%08lx) = %p  ★成功\n\n",
               mbase, (void *)map_base);
    }

    /* ---- dump 前 64 个word ---- */
    printf("--- %s ---\n", full ? "全量 baseline（所有 words）" : "前 256 字节（64 words）");
    for (i = 0; (full ? ((unsigned long)i * 4 < size) : (i < 64)) && (unsigned long)i * 4 < size; i++) {
        unsigned v = p[i];
        printf("  +0x%03x  0x%08x  %10u  %s\n",
               i * 4, v, v,
               v == 0 ? "(zero)" : "");
        if ((i % 4) == 3) printf("\n");
    }

    /* ---- 统计 ---- */
    nonzero = 0;
    for (i = 0; (unsigned long)i * 4 < size; i++)
        if (p[i]) nonzero++;
    printf("\n--- 统计 ---\n");
    printf("  总 words   = %lu\n", size / 4);
    printf("  非零 words = %u\n", nonzero);
    if (nonzero == 0)
        printf("  ★ 全零 => 该块从未被配置（EP 通路确实未启用）\n");
    else
        printf("  ★ 有非零值 => 该块已被配置过\n");

    munmap((void *)map_base, map_len);
    close(fd);
    printf("\n=== 结束：PROT_READ 映射，未写任何寄存器 ===\n");
    return 0;
}