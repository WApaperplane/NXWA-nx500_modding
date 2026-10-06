/* nogdump.c —— NOG / EP 寄存器只读 dump（NX500）★★v2 修正版
 *
 * ★★★ 安全等级：纯只读。全程 PROT_READ，绝不写任何 EP 寄存器。
 *
 * ★★★★★ v2 的关键修正（2026-10-06，v1 SIGBUS 根因定位）
 *
 * v1 用了 "mmap(4096 一页) + memcpy 整页"，SIGBUS(135)。
 * 对照实验发现：`raw5/epreg_all`（历史唯一真成功产物）用的是
 *
 *     pa_off = addr & ~(pg-1);          // 页对齐物理地址
 *     offs   = addr - pa_off;           // 页内偏移
 *     p = mmap(0, len + offs, PROT_READ, MAP_SHARED, memfd, pa_off);
 *     q = p + offs;                      // 只访问 [offs, offs+len)
 *
 * ⇒ ★★ 差异不在 offset（两者数值相同），**在 mmap 的 length**。
 *   v1 映射 `PAGE`(4096) 整页 ⇒ 当 offs=0xc00 时映射区尾部越过了
 *   设备寄存器有效范围，触碰即bus error。
 *   v2 严格照抄成功版姿势：**length = need + offs**，**只访问需要的字节**。
 *
 * ★ 另一个 v1 的 bug：跨页 memcpy 用了自重叠的 `memcpy(b, b+off, ...)`。
 *   v2 改成逐字节取，不再碰缓冲区。
 *
 * 用法: ./nogdump <tag>     输出 /mnt/mmc/_xfer/nog_<tag>.txt
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <fcntl.h>
#include <unistd.h>
#include <sys/mman.h>

static int memfd = -1;
static FILE *out;

/* ★ 照抄 raw5/epreg_all 的成功姿势。
 * ★★★★ v4 关键修正：mmap 的 length **必须 >= 一个整页**。
 *   v3 用 need+offs（首地址恰好页对齐时 = 4 字节）⇒ SIGBUS。
 *   raw5/epreg_all 用的是【块大小】(0x100/0x1000/0x1c00) ⇒ 成功。
 *   ⇒ 内核 3.5 的 /dev/mem direct_poke 需要整页才建立设备映射，
 *     映射不足一页时 mmap 成功但触碰即 bus error（**mmap 成功 ≠ 可读**）。
 *   ⇒ 姿势：length = round_up(offs + need, PAGE)，然后只访问 [offs, offs+need)。
 */
#define PGSZ 4096u
static int peek(unsigned long addr, unsigned need, unsigned char *dst)
{
    off_t pa_off = (off_t)(addr & ~(unsigned long)(PGSZ - 1));
    unsigned offs = (unsigned)(addr - (unsigned long)pa_off);
    unsigned len  = (offs + need + PGSZ - 1u) & ~(PGSZ - 1u);  /* ★ 向上取整到整页 */
    unsigned char *p;

    p = (unsigned char *)mmap((void *)0, (size_t)len, PROT_READ,
                              MAP_SHARED, memfd, pa_off);
    if (p == MAP_FAILED) return -1;
    {
        unsigned i;
        for (i = 0; i < need; i++) dst[i] = p[offs + i];
    }
    (void)munmap(p, (size_t)len);
    return 0;
}

/* 读 4 字节；跨页安全（逐字节） */
static int read32(unsigned long phys, unsigned *val)
{
    unsigned char b[4];
    int i;
    if (peek(phys, 4u, b) != 0) return -1;
    *val = 0u;
    for (i = 3; i >= 0; i--) *val = (*val << 8) | b[i];
    return 0;
}

/* ★★ NOG 寄存器全表（来源：FUN_004aff08 / FUN_004afe3c / FUN_004afd58 反编译）*/
static const unsigned NOG_A[] = { 0x00, 0x04, 0x08, 0x0c,
                                  0x10, 0x14, 0x18, 0x1c };  /* 实例0 */
static const unsigned NOG_B[] = { 0x40, 0x44, 0x48, 0x4c };  /* 实例1 (+0x30 起算 0x10) */
#define NOG_BASE 0x20821c00UL

/* ★ 3 字节/项 × 32 项 的表（FUN_004afe3c 的源表）*/
static unsigned char nogtab[32 * 3];

int main(int argc, char **argv)
{
    char path[256];
    const char *pre = "/mnt/mmc/_xfer/nog_";
    const char *tag = (argc > 1) ? argv[1] : "x";
    int i, k, nzero, nz, nff;
    unsigned v;

    k = 0;
    while (*pre) path[k++] = *pre++;
    while (*tag && k < 240) path[k++] = *tag++;
    path[k++] = '.'; path[k++] = 't'; path[k++] = 'x'; path[k++] = 't'; path[k] = 0;

    out = fopen(path, "w");
    if (!out) { (void)write(2, "nogdump: cannot create\n", 24); return 2; }
    /* ★★★ 关键：行缓冲 + 立即 flush。
     * SIGBUS 会直接杀进程，缓冲里的内容全部丢失 ⇒
     * 每写一行就fflush，这样崩溃点能被精确定位（v2 首跑0 字节就是没做这个）。*/
    setvbuf(out, NULL, _IOLBF, 0);

    memfd = open("/dev/mem", O_RDONLY);
    fprintf(out, "# NX500 NOG/EP read-only dump v4\n");
    fprintf(out, "# mmap length = need+offs (照抄 raw5 成功姿势)\n");
    fprintf(out, "# stdio line-buffered + fflush 每行\n");
    if (memfd < 0) { fprintf(out, "!! /dev/mem open FAILED\n"); fclose(out); return 3; }
    fprintf(out, "# /dev/mem opened RO\n");
    fprintf(out, "# ---- probe: 逐个物理地址测试可读性 ----\n");
    fflush(out);

    /* ---- 0. 可读性扫描：先搞清哪些地址能碰（这是诊断的核心）---- */
    {
        static const unsigned long T[] = {
            0x20820000UL, 0x20821000UL, 0x20821c00UL, 0x20821c10UL,
            0x20822000UL, 0x20823000UL, 0x20824000UL, 0x20826000UL,
            0x20829000UL, 0x2082a000UL, 0x2082b000UL
        };
        int t;
        for (t = 0; t < (int)(sizeof(T) / sizeof(T[0])); t++) {
            unsigned char b4[4];
            if (peek(T[t], 4u, b4) == 0)
                fprintf(out, "  PEER-OK   0x%08lx  %02x%02x%02x%02x\n",
                        T[t], b4[3], b4[2], b4[1], b4[0]);
            else
                fprintf(out, "  PEER-FAIL 0x%08lx  (mmap returned MAP_FAILED)\n", T[t]);
            fflush(out);
        }
    }

    /* ---- 1. NOG 实例0 ---- */
    fprintf(out, "=== NOG instance0 @ 0x%08lx ===\n", NOG_BASE);
    for (i = 0; i < 8; i++) {
        fflush(out);
        unsigned long a = NOG_BASE + NOG_A[i];
        if (read32(a, &v) == 0) fprintf(out, "  +0x%02x  0x%08x  %10u\n", NOG_A[i], v, v);
        else                   fprintf(out, "  +0x%02x  <MMAP-FAIL>\n", NOG_A[i]);
    }

    /* ---- 2. NOG 实例1 ---- */
    fprintf(out, "\n=== NOG instance1 (+0x30) ===\n");
    for (i = 0; i < 4; i++) {
        unsigned long a = NOG_BASE + NOG_B[i];
        if (read32(a, &v) == 0) fprintf(out, "  +0x%02x  0x%08x  %10u\n", NOG_B[i], v, v);
        else                   fprintf(out, "  +0x%02x  <MMAP-FAIL>\n", NOG_B[i]);
    }

    /* ---- 3. 0x20821c00 整块 0x100 字节（找那张 3B×32 表）---- */
    fprintf(out, "\n=== block 0x20821c00..0x20821cff (raw words) ===\n");
    nzero = nz = nff = 0;
    for (i = 0; i < 0x100 / 4; i++) {
        unsigned long a = NOG_BASE + (unsigned)i * 4u;
        if (read32(a, &v) != 0) { fprintf(out, "  +0x%03x  <FAIL>\n", i * 4); continue; }
        fprintf(out, "  +0x%03x  0x%08x\n", i * 4, v);
        if (v == 0u) nzero++; else nz++;
        if (v == 0xffffffffu) nff++;
    }
    fprintf(out, "  -- nonzero=%d zero=%d allFF=%d\n", nz, nzero, nff);

    /* ---- 4. 3B×32 表（FUN_004afe3c 的 DAT_004afefc + idx*3）---- */
    fprintf(out, "\n=== 3B x 32 table (nogtab) ===\n");
    if (peek(NOG_BASE + 0x100u, 96u, nogtab) == 0) {
        for (i = 0; i < 32; i++) {
            fprintf(out, "  [%2d]  %3u %3u %3u\n", i,
                    nogtab[i*3], nogtab[i*3+1], nogtab[i*3+2]);
        }
    } else {
        fprintf(out, "  <MMAP-FAIL>\n");
    }

    /* ---- 5. 对照：EP top / 3DLUT 头 4 word（证明通路本身是通的）---- */
    {
        static const unsigned long CHK[] = { 0x20820000UL, 0x2082b000UL, 0x2082a000UL };
        static const char *NM[] = { "EP_top", "EP_3DLUT", "EP_jpeg" };
        fprintf(out, "\n=== control: other EP blocks (proves path works) ===\n");
        for (i = 0; i < 3; i++) {
            fprintf(out, "  %-9s @0x%08lx :", NM[i], CHK[i]);
            for (k = 0; k < 4; k++) {
                if (read32(CHK[i] + (unsigned)k * 4u, &v) == 0) fprintf(out, " 0x%08x", v);
                else                                            fprintf(out, " <FAIL>");
            }
            fprintf(out, "\n");
        }
    }

    fclose(out);
    (void)close(memfd);
    return 0;
}
