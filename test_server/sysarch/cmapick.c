/* cmapick.c — CMA 实时空闲落点选择（★ 铁律 61 的落实工具）
 *
 * =====================================================================
 * 【目的】卡死事故后，不能再用"硬编码 0x94000000"。
 *   本工具在【导入前】实时扫描 CMA 区，找出当前真正空闲的落点。
 *
 * ★ 为什么必须实时扫描
 *   之前我探测到 0x94000000..0x95300000 "全 zero"就认定可用，
 *   但那是【瞬时快照】。ISP 的 DMA 引擎随时会占用。
 *   ⇒ 每次导入前重新扫描，才有效。
 *
 * ★ 只读：只 mmap + 读，不写任何字节，不碰任何硬件寄存器。
 *
 * 用法:
 *   cmapick                 扫描并推荐落点
 *   cmapick <phys_addr>     检查指定地址是否空闲
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

#define SMA_GET_REGION_SIZE       0x80047301UL
#define SMA_GET_REGION_START_ADDR 0x80047304UL
#define SMA_VIRT_TO_PHYS          0xc0047302UL

#define STEP_MB      1        /* ★ 每 1MB 采样一次 */
#define PROBE_WORDS  16       /* 每个采样点读16 个 u32 */
#define WANT_FREE_MB 4        /* ★ 要求的连续空闲量（9826 字节需要 <1MB，但要留余量）*/
#define CANDIDATES   40

static int is_free(unsigned char *p)
{
    int i;
    for (i = 0; i < PROBE_WORDS; i++) {
        unsigned int v;
        memcpy(&v, p + i * 4, 4);
        if (v != 0) return 0;
    }
    return 1;
}

int main(int argc, char **argv)
{
    int fd;
    unsigned int base = 0, size = 0;
    unsigned int i;
    unsigned int run_start = 0;
    int run_len = 0;
    int found = 0;

    fd = open("/dev/d5_sma", O_RDWR);
    if (fd < 0) { printf("open: %s\n", strerror(errno)); return 1; }
    ioctl(fd, SMA_GET_REGION_START_ADDR, &base);
    ioctl(fd, SMA_GET_REGION_SIZE, &size);

    printf("CMA region: start 0x%08x  size 0x%08x (%u MB)\n\n",
           base, size, size / (1024 * 1024));

    /* ---- 单点查询模式 ---- */
    if (argc >= 2) {
        unsigned int pa = (unsigned)strtoul(argv[1], NULL, 0);
        void *p = mmap(NULL, 4096, PROT_READ, MAP_SHARED, fd, (off_t)pa);
        if (p == MAP_FAILED) {
            printf("mmap 0x%08x 失败: %s\n", pa, strerror(errno));
            close(fd); return 2;
        }
        printf("0x%08x: %s\n", pa, is_free((unsigned char *)p) ? "空闲 ★" : "被占用");
        munmap(p, 4096); close(fd);
        return 0;
    }

    /* ---- 扫描模式 ---- */
    printf("扫描中（每 %d MB 采样，每点 %d words）...\n\n", STEP_MB, PROBE_WORDS);
    printf("%-14s %s\n", "物理地址", "状态");
    printf("---------------------------------------\n");

    for (i = 0; i < size / (1024 * 1024); i += STEP_MB) {
        unsigned int pa = base + i * 1024 * 1024;
        void *p = mmap(NULL, 4096, PROT_READ, MAP_SHARED, fd, (off_t)pa);
        int free;

        if (p == MAP_FAILED) {
            /* mmap 失败也算"不可用" */
            free = 0;
        } else {
            free = is_free((unsigned char *)p);
            munmap(p, 4096);
        }

        if (free) {
            if (run_len == 0) run_start = pa;
            run_len++;
            if (run_len == 1) printf("0x%08x  空闲 ★\n", pa);
            if (run_len == WANT_FREE_MB && !found) {
                printf("\n★★★ 推荐落点: 0x%08x  （连续 %d MB 空闲）\n",
                       run_start, WANT_FREE_MB);
                printf("    ★ 导入后请立即释放，不要让硬件长期引用\n");
                found = 1;
            }
        } else {
            if (run_len > 0) {
                printf("0x%08x  被占用  ← 连续空闲段结束（%d MB）\n", pa, run_len);
                run_len = 0;
            } else if (i % 8 == 0) {
                printf("0x%08x  被占用\n", pa);
            }
        }
    }

    if (run_len >= WANT_FREE_MB && !found) {
        printf("\n★★★ 推荐落点: 0x%08x  （连续 %d MB 空闲）\n",
               run_start, run_len);
        found = 1;
    }

    printf("\n=======================================\n");
    if (found) {
        printf("★ 有可用落点。★ 注意：这是【瞬时】结果，\n");
        printf("  导入前应重新跑一次本工具确认。\n");
    } else {
        printf("★★ 无可用落点（无 %d MB 连续空闲区）\n", WANT_FREE_MB);
        printf("  ⇒ CMA 已被占满，此时导入【必然卡死】\n");
        printf("  ⇒ 【不要尝试导入】\n");
    }
    close(fd);
    return found ? 0 : 3;
}
