/* cmasafe.c — U6 CMA 落点安全闸（只读）
 * =====================================================================
 * 【为什么需要它】
 *   3D LUT 的 load/save 都要求一个「CMA 物理落点」：
 *     load 把表数据放这里，硬件从这里 DMA 读走；
 *     save 让硬件把内部表 DMA 写到这。
 *   铁律 61：探测到"空闲" ≠ 可以安全独占 —— 2026-10-06 在 0x94000000
 *   写表把整机写卡死（拔电池才恢复），那块是 ISP 的 WDMA 工作区。
 *
 *   本工具是"写之前最后一道机械闸"：
 *     1. 地址必须落在两个已知 CMA 区之一（其余一律拒绝）
 *     2. 地址必须 4KB 对齐（dd/mmap 与页粒度一致）
 *     3. 硬编码事故黑名单（0x94000000 起 0x5000）
 *     4. mmap 后逐字节扫 20480 字节，非全零 ⇒ 拒绝
 *   —— 全部通过才 exit 0。任何一条不过都给出明确原因。
 *
 * 【纪律】
 *   * 只读：open(O_RDONLY) + mmap(PROT_READ)，绝不写一个字节
 *   * 不做任何"我替你选地址"的事 —— 地址必须由操作员显式给出
 *   * 编译：zig cc -target arm-linux-gnueabi.2.15 -O0（★ -O0 必须）
 *
 * 用法:
 *   ./cmasafe.arm 0x8f808000 [bytes]      # bytes 默认 20480
 * 退出码:
 *   0 = 通过（全零 + 范围/对齐/黑名单 OK）
 *   1 = 参数错误
 *   2 = 不在已知 CMA 范围
 *   3 = 命中事故黑名单
 *   4 = 未 4KB 对齐
 *   5 = 非全零（会打印首个非零偏移与前 32B 片段）
 *   6 = open/mmap 失败
 * =====================================================================
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <fcntl.h>
#include <unistd.h>
#include <sys/mman.h>
#include <errno.h>

/* dmesg 实测（cmapick2.c 头注释同源）：
 *   cma: reserved 288 MiB at 94000000 / 72 MiB at 8f800000 */
#define CMA1_START 0x94000000UL
#define CMA1_SIZE  0x12000000UL          /* 288MB */
#define CMA2_START 0x8f800000UL
#define CMA2_SIZE  0x04800000UL          /* 72MB */

/* 事故黑名单：2026-10-06 在此写入 19712B 表 ⇒ 整机卡死。
 * 该处为 ISP WDMA 工作区，平时读出来是零 —— 正是"探测到空闲≠可独占"的标本。 */
#define ACC_START  0x94000000UL
#define ACC_END    0x94005000UL          /* 覆盖 0x4D00 表长 + 余量 */

#define DEF_BYTES  20480UL               /* 5 页：>= 19712(整槽) 且页对齐 */

int main(int argc, char **argv)
{
    unsigned long phys, bytes, i;
    int fd;
    unsigned char *m;
    unsigned long first_nz = 0, nz = 0;
    int in_cma = 0;

    if (argc < 2) {
        printf("用法: %s <phys 0x...> [bytes=%lu]\n", argv[0], DEF_BYTES);
        printf("  只读安全闸：CMA 范围 + 黑名单 + 对齐 + 全零(20480B)\n");
        return 1;
    }
    phys  = strtoul(argv[1], NULL, 0);
    bytes = argc > 2 ? strtoul(argv[2], NULL, 0) : DEF_BYTES;
    if (!phys || bytes == 0 || bytes > 0x100000UL) {
        printf("★ 参数不合法: phys=0x%lx bytes=%lu\n", phys, bytes);
        return 1;
    }

    printf("=== cmasafe：CMA 落点安全闸（只读） ===\n");
    printf("  目标 phys = 0x%08lx  检查 %lu 字节\n", phys, bytes);

    /* 1. CMA 范围 */
    if (phys >= CMA1_START && phys + bytes <= CMA1_START + CMA1_SIZE) {
        in_cma = 1;
        printf("  [1] 范围: CMA#1 (0x%08lx+%luMB) OK\n",
               (unsigned long)CMA1_START, (unsigned long)(CMA1_SIZE >> 20));
    }
    if (phys >= CMA2_START && phys + bytes <= CMA2_START + CMA2_SIZE) {
        in_cma = 1;
        printf("  [1] 范围: CMA#2 (0x%08lx+%luMB) OK\n",
               (unsigned long)CMA2_START, (unsigned long)(CMA2_SIZE >> 20));
    }
    if (!in_cma) {
        printf("  [1] ★★ 不在已知 CMA 范围 —— 拒绝\n");
        printf("      CMA#1 = 0x%08lx..0x%08lx\n", (unsigned long)CMA1_START,
               (unsigned long)(CMA1_START + CMA1_SIZE));
        printf("      CMA#2 = 0x%08lx..0x%08lx\n", (unsigned long)CMA2_START,
               (unsigned long)(CMA2_START + CMA2_SIZE));
        return 2;
    }

    /* 2. 4KB 对齐 */
    if (phys & 0xFFFUL) {
        printf("  [2] ★★ 未 4KB 对齐 —— 拒绝（dd/mmap 页粒度会错位）\n");
        return 4;
    }
    printf("  [2] 4KB 对齐 OK\n");

    /* 3. 黑名单 */
    if (phys >= ACC_START && phys < ACC_END) {
        printf("  [3] ★★★★ 命中事故黑名单 0x%08lx..0x%08lx\n",
               (unsigned long)ACC_START, (unsigned long)ACC_END);
        printf("      2026-10-06 在此写表 ⇒ 整机卡死（ISP WDMA 工作区）。\n");
        printf("      ⇒ 换 cmapick 的『4KB 粒度命中』给的地址。\n");
        return 3;
    }
    printf("  [3] 黑名单 OK（避开 0x%08lx..0x%08lx）\n",
           (unsigned long)ACC_START, (unsigned long)ACC_END);

    /* 4. 全零（只读 mmap） */
    fd = open("/dev/mem", O_RDONLY);
    if (fd < 0) {
        printf("  [4] ★★ open /dev/mem 失败: %s\n", strerror(errno));
        return 6;
    }
    m = (unsigned char *)mmap(NULL, bytes, PROT_READ, MAP_SHARED, fd, (off_t)phys);
    if (m == MAP_FAILED) {
        printf("  [4] ★★ mmap 0x%08lx(%luB) 失败: %s\n", phys, bytes,
               strerror(errno));
        printf("      ⇒ 该地址可能不可读（不在内核 memory map 内）。\n");
        close(fd);
        return 6;
    }
    for (i = 0; i < bytes; i++) {
        if (m[i]) {
            if (!nz) first_nz = i;
            nz++;
        }
    }
    if (nz) {
        unsigned long k, lim = first_nz + 32;
        if (lim > bytes) lim = bytes;
        printf("  [4] ★★ 非全零: %lu/%lu 字节非零，首个 @ +0x%lx\n", nz, bytes,
               first_nz);
        printf("      前 32B 片段(自首个非零起): ");
        for (k = first_nz; k < lim; k++) printf("%02x", m[k]);
        printf("\n      ⇒ 拒绝。重新 cmapick 找一个全零落点。\n");
        munmap(m, bytes);
        close(fd);
        return 5;
    }
    printf("  [4] 全零 OK（%lu 字节逐字节扫过）\n", bytes);
    munmap(m, bytes);
    close(fd);

    printf("*** cmasafe 通过：0x%08lx 可作一次性落点 ***\n", phys);
    printf("    ★ 提醒：本闸只证『此刻全零』，不证『长期可独占』（铁律 61）。\n");
    printf("    ★ 落点选用后应尽快完成 load/save，不要隔很久再回来用。\n");
    return 0;
}
