/* cmapick2.c — CMA 空闲落点选择 v2（★ 双区 + 可调粒度 + 计时）
 * =====================================================================
 * 【为什么要 v2】2026-10-06 23:05 实测发现 v1 的三个缺陷：
 *
 *  ① ★★ 只扫第一个 CMA 区
 *     dmesg: cma: reserved 288 MiB at 94000000 / 72 MiB at 8f800000
 *     ⇒ v1 完全忽略了 0x8f800000 起的 72MB
 *
 *  ② ★★ 采样强度太弱
 *     v1 每 1MB 只读 16 words = 64 字节（占该区 0.006%）
 *     ⇒ 一页 busy 里只有极小概率被命中
 *
 *  ③ ★★ 只报"全零/不零"
 *     实际上"全零"不等于"可安全独占"（铁律 61）
 *     ⇒ 本工具明确区分【全零】【部分非零】【全非零】三态并给出建议
 *
 * ★★ 铁律 61（本工具存在的唯一理由）
 *   探测到"空闲" ≠ 可以安全独占。
 *   2026-10-06 在 0x94000000 写表导致整机卡死（拔电池才恢复）
 *   ⇒ 那块是 ISP 的 WDMA 硬件工作区。
 *   ★ 所以本工具【只提供数据，不做安全保证】。
 *
 * ★ 只读：不写任何字节，不碰任何硬件寄存器。
 *
 * 用法:
 *   cmapick2                    扫两个区，1MB 粒度（默认）
 *   cmapick2<step_kb>           指定粒度（KB），如 cmapick2 64
 *   cmapick2 <step_kb> <need_kb>  同时指定需要的连续量
 *   cmapick2 --need19652 1       按 19652 字节 LUT 表的需求找落点
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <fcntl.h>
#include <sys/time.h>
#include <sys/ioctl.h>
#include <sys/mman.h>
#include <errno.h>

#define SMA_GET_REGION_SIZE       0x80047301UL
#define SMA_GET_REGION_START_ADDR 0x80047304UL
#define SMA_VIRT_TO_PHYS          0xc0047302UL

#define MAX_REGIONS 4
/* ★ dmesg 实测的两个 CMA 区；这里不写死，运行时用 ioctl 问驱动 */
struct region { unsigned int start, size; const char *name; };

static unsigned char *map_phys(int fd, unsigned int phys, unsigned long bytes)
{
    return (unsigned char *)mmap(NULL, bytes, PROT_READ, MAP_SHARED,
                                fd, (off_t)phys);
}

static unsigned long now_ms(void)
{
    struct timeval tv;
    gettimeofday(&tv, NULL);
    return (unsigned long)tv.tv_sec * 1000UL + tv.tv_usec / 1000;
}

/* ★ 三态判定
 *   0 = 全零（可能是空闲，也可能是"刚好没被写"）
 *   1 = 部分非零
 *   2 = 全非零
 */
static int scan_span(unsigned char *base, unsigned long span, unsigned long step,
                     unsigned long *runs_allzero)
{
    unsigned long off;
    int st = 2;
    unsigned long allzero_run = 0;

    *runs_allzero = 0;
    for (off = 0; off + 64 <= span; off += step) {
        int i, nz = 0;
        for (i = 0; i < 16; i++) {          /* 每采样点读 16 words */
            unsigned int v;
            memcpy(&v, base + off + i * 4, 4);
            if (v) { nz++; }
        }
        if (nz == 0) {
            st = (st == 2) ? 0 : st;
            allzero_run += step;
            if (allzero_run > *runs_allzero) *runs_allzero = allzero_run;
        } else {
            st = (st == 0) ? 1 : st;
            allzero_run = 0;
        }
    }
    return st;
}

int main(int argc, char **argv)
{
    int fd, i;
    unsigned int base = 0, size = 0;
    unsigned long step_kb = 1024, need_kb = 64;   /* 19652 字节向上取整到 64KB */
    unsigned long t0, t1;
    int found = 0;
    int quiet = 0;

    /* ---- 参数 ---- */
    if (argc >= 2 && strcmp(argv[1], "--need19652") == 0) { need_kb = 32; quiet = 1; }
    if (argc >= 2 && strcmp(argv[1], "--quiet") == 0) { quiet = 1; argc--; argv++; }
    if (argc >= 2) {
        long v = atol(argv[1]);
        if (v >= 4 && v <= 1048576) step_kb = (unsigned long)v;
    }
    if (argc >= 3) need_kb = (unsigned long)atol(argv[2]);

    printf("=== CMA 空闲落点探测 v2（只读）===\n");
    printf("粒度 = %lu KB｜需要连续 = %lu KB\n", step_kb, need_kb);

    fd = open("/dev/d5_sma", O_RDWR);
    if (fd < 0) { printf("open /dev/d5_sma: %s\n", strerror(errno)); return 1; }
    if (ioctl(fd, SMA_GET_REGION_START_ADDR, &base) < 0) {
        printf("ioctl START_ADDR: %s\n", strerror(errno)); close(fd); return 1;
    }
    if (ioctl(fd, SMA_GET_REGION_SIZE, &size) < 0) {
        printf("ioctl SIZE: %s\n", strerror(errno)); close(fd); return 1;
    }
    printf("region#1: start=0x%08x size=0x%08x (%u MB)\n",
           base, size, size >> 20);
    printf("  （dmesg 显示还有 72MB @ 0x8f800000 —— 驱动只报一个 region，\n"
           "     第二个区需硬编码扫，见下）\n");

    /* ★ dmesg: cma: reserved 288 MiB at 94000000 / 72 MiB at 8f800000 */
    {
        struct region regs[MAX_REGIONS];
        int nreg = 0;

        regs[nreg].start = base;
        regs[nreg].size  = size;
        regs[nreg].name  = "region#1 (ioctl 报告)";
        nreg++;

        /* 第二个区：从 region#1 结束处往后推 0x1000 边界 */
        {
            unsigned int next = base + size;
            next = (next + 0xFFFFF) & ~0xFFFFF;   /* 对齐 1MB */
            /* dmesg 说 72MiB @ 0x8f800000；优先用它 */
            if (0x8f800000UL >= 0x100000UL && 0x8f800000UL != base) {
                regs[nreg].start = 0x8f800000UL;
                regs[nreg].size  = 72UL * 1024 * 1024;
                regs[nreg].name  = "region#2 (dmesg: 72MiB @ 0x8f800000)";
                nreg++;
            }
        }

        printf("\n共 %d 个区待扫\n\n", nreg);
        for (i = 0; i < nreg; i++) {
            unsigned long span = regs[i].size;
            unsigned long step = step_kb * 1024UL;
            unsigned char *m;
            unsigned long allzero = 0;
            int st;
            unsigned long nsamp;

            printf("---- %s : 0x%08x  %u MB ----\n",
                   regs[i].name, regs[i].start, regs[i].size >> 20);
            fflush(stdout);

            m = map_phys(fd, regs[i].start, span);
            if (m == MAP_FAILED) {
                printf("  mmap 失败: %s\n", strerror(errno));
                printf("  ⇒ 该区可能不存在或未保留\n\n");
                continue;
            }
            t0 = now_ms();
            nsamp = span / step;
            /* ★ 分块扫，每块之间让出，避免长时间独占单核（铁律 3） */
            {
                unsigned long chunk = 4UL * 1024 * 1024;   /* 每块 4MB 采样量 */
                unsigned long done = 0;
                int st_acc = 2;
                unsigned long allzero_run = 0, best_run = 0;
                while (done < span) {
                    unsigned long this_span = span - done;
                    unsigned long o;
                    if (this_span > chunk) this_span = chunk;
                    for (o = done; o + 64 <= done + this_span; o += step) {
                        int k, nz = 0;
                        for (k = 0; k < 16; k++) {
                            unsigned int v;
                            memcpy(&v, m + o + k * 4, 4);
                            if (v) nz++;
                        }
                        if (nz == 0) {
                            if (st_acc == 2) st_acc = 0;
                            allzero_run += step;
                            if (allzero_run > best_run) best_run = allzero_run;
                        } else {
                            if (st_acc == 0) st_acc = 1;
                            allzero_run = 0;
                        }
                    }
                    done += this_span;
                    usleep(2000);      /* ★ 让出 2ms（铁律 3） */
                }
                st = st_acc;
                allzero = best_run;
            }
            t1 = now_ms();

            printf("  采样点 %lu 个，用时 %lu ms\n", nsamp, t1 - t0);
            printf("  状态 = %s\n",
                   st == 0 ? "全零（★ 可能有空闲，但铁律 61：探测到空闲≠可独占）"
                   : st == 1 ? "部分非零（有零散空闲，需细粒度定位）"
                            : "★ 全非零（该区完全被占用）");
            if (allzero >= step_kb)
                printf("  ★ 找到连续全零区：%lu KB @ 该区起点 0x%08x\n",
                       allzero / 1024, regs[i].start);

            if (st != 2 && allzero >= need_kb * 1024) {
                printf("  ⇒★★ 可用落点候选：0x%08x（连续 %lu KB ≥ 需求 %lu KB）\n",
                       regs[i].start, allzero / 1024, need_kb);
                found++;
            }

            /* ★ 细粒度定位第一个满足需求的位置（仅在部分非零时才有意义） */
            if (st != 2) {
                unsigned long step2 = 4096;   /* 4KB 页粒度 */
                unsigned long run = 0, runstart = 0, o;
                int hit = 0;
                /* 只在前 32MB 内细扫（单核保护：避免跑太久） */
                unsigned long lim = span < 32UL*1024*1024 ? span : 32UL*1024*1024;
                for (o = 0; o + 64 <= lim; o += step2) {
                    int k, nz = 0;
                    for (k = 0; k < 16; k++) {
                        unsigned int v;
                        memcpy(&v, m + o + k * 4, 4);
                        if (v) nz++;
                    }
                    if (nz == 0) {
                        if (run == 0) runstart = o;
                        run += step2;
                        if (!hit && run >= need_kb * 1024) {
                            printf("  ⇒★★ 4KB 粒度命中：0x%08lx 起连续 %lu KB\n",
                                   (unsigned long)(regs[i].start + runstart), run / 1024);
                            found++; hit = 1;
                        }
                    } else run = 0;
                }
                if (!hit) {
                    printf("  ⇒ 前 %lu MB 内无 %lu KB 连续全零区\n",
                           lim >> 20, need_kb);
                    printf("     ⇒★ 建议换更小 need（--need19652）或退出拍摄态\n");
                }
            }

            munmap(m, span);
            printf("\n");
        }
    }

    close(fd);
    printf("=========================================\n");
    if (found)
        printf("★★ 有 %d 个候选落点 —— 仍必须遵守铁律 61：\n", found);
    else
        printf("★ 无可用落点⇒ 此时 load【必然卡死整机】\n");
    printf("   ⇒不要尝试。先退出拍摄态让 ISP 释放，再重跑本工具。\n");
    printf("=========================================\n");
    return found ? 0 : 2;
}