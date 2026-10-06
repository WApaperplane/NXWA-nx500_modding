/* smascan.c — SMA_ALLOC 参数扫描（★ 只分配+立即释放，零硬件风险）
 *
 * =====================================================================
 * 【目的】2026-10-06 卡死事故后，需用动态分配替代硬编码 0x94000000。
 *   首次探测：`SMA_ALLOC(16384)` 返回 EFAULT。
 *   ⇒ 不知道是 size 语义 / addr 语义 / 对齐要求哪个不对。
 *   ⇒ 本工具系统扫描参数组合，★ 每次成功都立即 SMA_FREE。
 *
 * ★ 安全性：
 *   - 不写任何 EP/3DLUT 寄存器
 *   - 不碰任何分区
 *   - 每次分配成功立即释放
 *   ⇒ 失败模式最坏是内存泄漏几KB（可重启清掉）
 *
 * ★ 已确认的编码（与 libudd5 交叉验证过）：
 *   SMA_VIRT_TO_PHYS = 0xc0047302 ★ 与反汇编一致 ⇒ 编码方式正确
 *
 * 用法: smascan
 * =====================================================================
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <fcntl.h>
#include <sys/ioctl.h>
#include <errno.h>

#define SMA_VIRT_TO_PHYS     0xc0047302UL
#define SMA_ALLOC            0xc0087305UL
#define SMA_FREE             0x40047306UL
#define SMA_FREE_PHYS        0x40047307UL
#define SMA_GET_ALLOCATED_SIZE 0x80047308UL

struct sma_buf {
    unsigned int addr;
    unsigned int size;
};

static int try_alloc(int fd, unsigned int addr_in, unsigned int size,
                     const char *tag)
{
    struct sma_buf b;
    int rc;
    b.addr = addr_in;
    b.size = size;
    rc = ioctl(fd, SMA_ALLOC, &b);
    if (rc == 0) {
        unsigned int phys = b.addr;
        int rc2 = ioctl(fd, SMA_VIRT_TO_PHYS, &phys);
        printf("  %-28s size=%-10u addr_in=0x%08x ⇒ virt 0x%08x"
               "  phys 0x%08x %s\n",
               tag, size, addr_in, b.addr, rc2 == 0 ? phys : 0,
               rc2 == 0 ? "✔" : "(phys失败)");
        /* ★ 立即释放 */
        {
            unsigned int v = b.addr;
            int r3 = ioctl(fd, SMA_FREE, &v);
            printf("  %-28s   SMA_FREE(0x%08x) = %d %s\n", "",
                   b.addr, r3, r3 < 0 ? strerror(errno) : "已释放 ✔");
        }
        return 0;
    }
    printf("  %-28s size=%-10u addr_in=0x%08x ⇒ 失败: %s\n",
           tag, size, addr_in, strerror(errno));
    return -1;
}

int main(void)
{
    int fd;
    unsigned int before = 0, after = 0;
    int ok = 0;

    fd = open("/dev/d5_sma", O_RDWR);
    if (fd < 0) { printf("open: %s\n", strerror(errno)); return 1; }
    printf("fd=%d\n", fd);

    ioctl(fd, SMA_GET_ALLOCATED_SIZE, &before);
    printf("分配前 ALLOCATED = %u KB\n\n", before / 1024);

    /* ---- 扫描 1：size 的语义（字节 vs 页）---- */
    printf("=== 扫描 1：size 语义 ===\n");
    try_alloc(fd, 0, 1, "size=1B");
    try_alloc(fd, 0, 4096, "size=1page");
    try_alloc(fd, 0, 0x1000, "size=0x1000");
    try_alloc(fd, 0, 0x2000, "size=0x2000");
    try_alloc(fd, 0, 0x4000, "size=0x4000(16K)");
    try_alloc(fd, 0, 0x10000, "size=64K");
    ok |= (try_alloc(fd, 0, 0x4000, "retry 16K") == 0);

    /* ---- 扫描 2：size=0（可能表示"自动大小"）---- */
    printf("\n=== 扫描 2：size=0（自动）===\n");
    try_alloc(fd, 0, 0, "size=0");

    /* ---- 扫描 3：addr 是否为输入 hint ---- */
    printf("\n=== 扫描 3：addr 作 hint（region 内任一地址）===\n");
    try_alloc(fd, 0x94000000, 0x1000, "addr=region_start");
    try_alloc(fd, 0x9c000000, 0x1000, "addr=region_start+64M");
    try_alloc(fd, 0x9d000000 - 0x1000, 0x1000, "addr=region_end-4K");

    /* ---- 扫描 4：大块（表只要 9826 字节，但可能内部按页/更大粒度）---- */
    printf("\n=== 扫描 4：更大尺寸 ===\n");
    try_alloc(fd, 0, 0x100000, "size=1MB");
    try_alloc(fd, 0, 0x400000, "size=4MB");

    ioctl(fd, SMA_GET_ALLOCATED_SIZE, &after);
    printf("\n分配后 ALLOCATED = %u KB（差 %+d KB）\n",
           after / 1024, (int)(after - before) / 1024);

    close(fd);
    return ok ? 0 : 2;
}
