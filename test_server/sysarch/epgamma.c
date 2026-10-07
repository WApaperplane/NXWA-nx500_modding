/* epgamma.c — NX-KS2 2026-10-07 Q3：gamma / color / NOG 的 EP侧可读性普查
 *
 * ★★★ 本工具【全程只读】：open(O_RDONLY) + ioctl(GET_PHYS_REG_INFO) + mmap(PROT_READ)。
 *    不调用任何 libudd5 函数、不写任何寄存器、不 attach/ptrace。零破坏风险。
 *
 * ★★★ 要回答的问题（Q3 = 判定 T2"生效判据"是否可解）
 *   H1 假设：gamma/color/NOG 走 EP 寄存器直写 ⇒ EP 侧应有【可读回】的寄存器
 *   H2 假设：它们在 p7 内部消化，不进 EP 可见面 ⇒ 无读回路径
 *   ⇒ 本工具给出的判据：哪个 EP 块里有【非零且看起来像参数】的寄存器。
 *
 * ★ 判据设计（★ 铁律：不以"grep 零结果"下结论，必须自证搜索通路有效）
 *   · 正证据 = 某块寄存器里有非零值，且随场景/参数变化
 *   · 自证= 3dlut 块【必须】能读出已知值（OnOff/Cfg/Pulse/LUT0）
 *     ⇒ 若连它都读不出，说明是工具错，不是"设备里没有"
 *   · 反证= 所有块全零 ⇒ 才支持 H2
 *
 * 用法:
 *   epgamma map          打印 10 个块的基址+大小（不读内容，最快）
 *   epgamma scan         逐块只读扫描，统计非零率并dump 前 64 个非零寄存器
 *   epgamma watch<blk>   深度读单个块（全 4096B 十六进制+ 解读）
 *   epgamma diff <blk>   ★ 连读两次，报告差异寄存器（用于"改设置看哪动了"）
 *
 * ⚠ 单核相机铁律：scan 会读较多数据 ⇒ 一律 nice -n 19 + 分块usleep 让出
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <fcntl.h>
#include <time.h>
#include <sys/ioctl.h>
#include <sys/mman.h>
#include <errno.h>

#include <media/drime5/ep/d5_ep_ioctl.h>

#define NBLK 10

static const char *NAMES[NBLK] = {
    "top", "ldc", "mc", "rsz", "lvr",
    "bblt", "fd", "jpeg", "3dlut", "nog"
};

/* ★★★ 关注区：这些偏移名对应 p7 键名表里的参数，用于打印"命中提示" */
static const char *KEYS[] = {
    "GAMMA_INDEX", "TC_LOW_ANCHOR", "CC_RGBL_MAT", "CC_RGBH_MAT",
    "R2Y_MAT", "SE_MAT", "EE_GAMMA_COMP", "WB_GAIN2", "WB_OFFSET",
    "LUT_Load", "LUT_ChangeAddress", NULL
};

static struct ep_reg_info info;

static struct ep_reg_phys_info *blk(int i)
{
    return (struct ep_reg_phys_info *)((char *)&info + i * sizeof(struct ep_reg_phys_info));
}

static int fd_ep = -1;

/* ★ map_ro 返回的是【偏移到 pa 的指针】，munmap 必须用 mmap 基址。
 *   ⇒ 把基址与长度记在这里，调用方统一用 unmap_ro()。
 *   （2026-10-07 首版在调用方手算 `(char*)b - (pa & 0xfff)`，
 *     对非页对齐的 pa 算错 → 修正为不手算，见 unmap_ro）*/
static void *g_map_base[1];
static unsigned long g_map_len[1];

static void unmap_ro(void *p)
{
    if (!p || !g_map_base[0]) return;
    munmap(g_map_base[0], g_map_len[0]);
    g_map_base[0] = NULL;
}

static int get_info(void)
{
    memset(&info, 0, sizeof(info));
    if (ioctl(fd_ep, EP_IOCTL_GET_PHYS_REG_INFO, &info) < 0) {
        printf("ioctl(GET_PHYS_REG_INFO) 失败: %s\n", strerror(errno));
        return -1;
    }
    return 0;
}

/* 只读映射一个块；返回 NULL 表示这块映射不了 */
static volatile unsigned *map_ro(int i, unsigned long *real_size)
{
    unsigned long pa   = blk(i)->reg_start_addr;
    unsigned long size = blk(i)->reg_size;
    unsigned long msize, mbase;
    volatile unsigned *p;

    if (size == 0) return NULL;
    /* ★ 铁律：mmap 的 offset 单位是字节（内核自己 >>12 转 PFN）
     *   ⇒ 必须传 phys 原值，不能传 phys>>12
     *   ★ 小于一页的块（nog 只有 0x100=256B）必须把长度向上对齐到页 */
    msize = (size + 4095) & ~4095UL;
    mbase = pa & ~4095UL;

    p = (volatile unsigned *)mmap(NULL, msize, PROT_READ, MAP_SHARED,
                                  fd_ep, (off_t)mbase);
    if (p == MAP_FAILED) return NULL;
    *real_size = msize;
    g_map_base[0] = (void *)p;
    g_map_len[0] = msize;
    /* 返回偏移到 pa 的指针 */
    return p + ((pa - mbase) / 4);
}

/* ★ 自证：3dlut 块的已知寄存器（来自 10-06 实机 regdump 双向一致）*/
typedef struct { unsigned off; const char *name; unsigned expect; } Known;

static int selftest(void)
{
    unsigned long ms;
    volatile unsigned *b;
    unsigned v_onoff, v_cfg, v_lut0;
    int ok = 0, total = 0;

    printf("=== 自证：3dlut 块必须能读出已知值 ===\n");
    printf("  已知（10-06 实机双向一致）：OnOff bit0=1 / Cfg=0x100 / LUT0=0x81115200\n\n");

    b = map_ro(8, &ms);
    if (!b) {
        printf("  ★ 3dlut 块映射失败 —— 工具/驱动问题，不是结论\n");
        return -1;
    }
    v_onoff = b[0x000 / 4];
    v_cfg   = b[0x004 / 4];
    v_lut0  = b[0x00c / 4];

    printf("  +0x000 OnOff = 0x%08x%s\n", v_onoff,
           (v_onoff & 1) ? "  ✔ bit0=1，与已知一致" : "  ✘ bit0=0");
    total++;
    if (v_onoff & 1) ok++;

    printf("  +0x004 Cfg   = 0x%08x%s\n", v_cfg,
           (v_cfg == 0x100) ? "  ✔ 与已知完全一致" : "  （与已知 0x100 不同）");
    total++;
    if (v_cfg == 0x100) ok++;

    printf("  +0x00c LUT0  = 0x%08x%s\n", v_lut0,
           (v_lut0 == 0x81115200) ? "  ✔ 与已知一致（当前肤色档）" : "  （值不同，可能是别的档）");
    total++;
    if (v_lut0 == 0x81115200) ok++;

    printf("\n  ⇒ %d/%d 项与已知一致\n", ok, total);
    unmap_ro((void *)b);
    return ok;
}

static void cmd_map(void)
{
    int i;
    printf("=== EP 10 个子块寄存器区（EP_IOCTL_GET_PHYS_REG_INFO）===\n\n");
    printf("  %-3s %-7s %-12s %-10s\n", "idx", "name", "phys_start", "size");
    printf("  %s\n", "------------------------------------------------");
    for (i = 0; i < NBLK; i++) {
        printf("  %-3d %-7s 0x%08x  0x%06x (%u)\n",
               i, NAMES[i],
               (unsigned)blk(i)->reg_start_addr,
               (unsigned)blk(i)->reg_size,
               (unsigned)blk(i)->reg_size);
    }
    printf("\n  ★ mc = Media Core⇒ gamma / color 矩阵最可能在这里\n");
    printf("  ★ nog = Noise Generator ⇒ NOG 的寄存器区（0x100 = 256B，很小）\n");
}

static void cmd_scan(int only)
{
    int i;
    unsigned long ms, j, total_reg, nz_reg;
    volatile unsigned *b;
    int k;                    /* ★ 声明为 int：它存的是"首个非零的寄存器序号"，可为 -1 */

    printf("=== 逐块只读扫描：非零率（Q3 主判据）===\n\n");
    if (only >= 0)
        printf("  ★ 只扫 idx=%d (%s)，其余块不动（单核相机：一次只扫一块）\n\n",
               only, NAMES[only]);
    printf("  %-7s %-10s %-9s %s\n", "block", "size", "nonzero", "首个非零偏移");
    printf("  %s\n", "--------------------------------------------------------");

    for (i = 0; i < NBLK; i++) {
        unsigned long size;
        if (only >= 0 && i != only) continue;
        size = blk(i)->reg_size;
        if (size == 0) {
            printf("  %-7s %-10s (size=0，跳过)\n", NAMES[i], "0");
            continue;
        }

        b = map_ro(i, &ms);
        if (!b) {
            printf("  %-7s %-10lu %s\n", NAMES[i], size, "★ mmap 失败");
            continue;
        }
        total_reg = size / 4;
        nz_reg = 0; k = -1;
        /* ★★★ 分 256 个寄存器一段，每段之间usleep —— 铁律：
         *   2026-10-07 首版一次性扫全10 块（≈28KB 顺序读 + printf）把单核相机压到重启。
         *   读寄存器本身很轻，压死相机的是【长时间不 sleep 的连续读 + 输出】。 */
        for (j = 0; j < total_reg; j++) {
            if (b[j]) { nz_reg++; if (k < 0) k = (int)j; }
            if ((j & 0xff) == 0xff) usleep(3000);
        }
        if (k >= 0)
            printf("  %-7s %-10lu %-9lu +0x%04x\n",
                   NAMES[i], size, nz_reg, (unsigned)(k * 4));
        else
            printf("  %-7s %-10lu %-9lu (全零)\n", NAMES[i], size, nz_reg);
        fflush(stdout);
        unmap_ro((void *)b);
        usleep(50000);         /* ★ 单核相机：每块之间让出 50ms */
    }
    printf("\n  ★ 判读：非零寄存器多⇒ 该块是活跃参数面；全零 ⇒ 静态/未启用\n");
    printf("  ★ 但非零【不等于】含 gamma/color —— 需用 diff 看它随设置是否变\n");
}

static void cmd_watch(int i)
{
    unsigned long ms, size, j, nreg;
    volatile unsigned *b;

    if (i < 0 || i >= NBLK) { printf("block 0..%d\n", NBLK - 1); return; }
    size = blk(i)->reg_size;
    b = map_ro(i, &ms);
    if (!b) { printf("mmap %s 失败\n", NAMES[i]); return; }

    nreg = size / 4;
    printf("=== %s 块分段 dump（只读） phys=0x%08x size=0x%lx (%lu regs）===\n",
           NAMES[i], (unsigned)blk(i)->reg_start_addr, size, nreg);
    printf("  ★ 每 16 行一段，段间 sleep 300ms（单核相机铁律，见 scan 的注释）\n\n");

    /* ★ 分段：每段 64 个寄存器（16 行），段间 sleep 300ms
     *   ⇒ 8192B 的 mc 块从"一瞬间读完 + 数千行 printf"
     *      变成 32 段、约 10 秒、可被中断 ⇒ 不会压死相机 */
    for (j = 0; j < nreg; j += 64) {
        unsigned long k, end = j + 64;
        if (end > nreg) end = nreg;
        printf("  +0x%04lx:", j * 4);
        for (k = j; k < end; k++) {
            printf(" %08x", b[k]);
            if (((k - j) & 0xf) == 0xf && k + 1 < end) printf("\n            ");
        }
        printf("\n");
        fflush(stdout);
        usleep(300000);
    }
    printf("\n  ★ 判读：连续递增且步长均匀的一组寄存器 ⇒ 可能是 anchor 表\n");
    printf("    （对照 p7 键名表的 TC_LOW_ANCHOR_X00..X21 / Y00..Y21）\n");
    unmap_ro((void *)b);
}

static void cmd_diff(int i)
{
    unsigned long ms, size, j, nreg;
    volatile unsigned *b;
    int ndiff = 0;
    /* ★ 快照走 malloc 不走 static：static 在 .bss 且本程序 -O0，
     *   大缓冲 + 未初始化路径在实机上有踩到未初始化页的风险 */
    unsigned *snap;

    if (i < 0 || i >= NBLK) { printf("block 0..%d\n", NBLK - 1); return; }
    size = blk(i)->reg_size;
    b = map_ro(i, &ms);
    if (!b) { printf("mmap 失败\n"); return; }
    nreg = size / 4;
    if (nreg == 0 || nreg > 65536) {
        printf("块 %s size=%lu 不适合 diff\n", NAMES[i], size);
        unmap_ro((void *)b);
        return;
    }

    printf("=== %s 块：连读两次比较（间隔 20s，请在这期间用机身改设置）===\n", NAMES[i]);
    printf("  ★ 建议同时改：拍摄模式 / 白平衡 / 降噪开关 / 色调\n");
    printf("  ★ 若列出变化的寄存器 ⇒ 该设置在这个块里有【可读回痕迹】\n\n");

    snap = (unsigned *)malloc(nreg * sizeof(unsigned));
    if (!snap) {
        printf("malloc %lu 失败\n", nreg * sizeof(unsigned));
        unmap_ro((void *)b);
        return;
    }
    for (j = 0; j < nreg; j++) snap[j] = b[j];

    /* ★★ 分段等待 + 每段 usleep，让出CPU（单核铁律：不能长时间占着进程）*/
    {
        int k;
        for (k = 0; k < 20; k++) { usleep(1000000); printf("."); fflush(stdout); }
        printf("\n  等待结束，开始比对\n\n");
    }

    for (j = 0; j < nreg; j++) {
        unsigned now = b[j];
        if (now != snap[j]) {
            printf("  +0x%04lx: 0x%08x -> 0x%08x  (^0x%x)\n",
                   j * 4, snap[j], now, now ^ snap[j]);
            ndiff++;
        }
    }
    printf("\n  ⇒ %d 个寄存器发生变化\n", ndiff);
    if (ndiff == 0)
        printf("  ★ 无变化 ⇒ 该块不随这些设置变化\n");

    free(snap);
    unmap_ro((void *)b);
}

int main(int argc, char **argv)
{
    const char *cmd = (argc > 1) ? argv[1] : "map";

    /* ★ 单核相机铁律：一律降优先级 */
    nice(19);

    fd_ep = open("/dev/drime5_ep", O_RDONLY);   /* ★ 只读，绝不O_RDWR */
    if (fd_ep < 0) {
        printf("open(/dev/drime5_ep, O_RDONLY) 失败: %s\n", strerror(errno));
        return 2;
    }
    printf("open(/dev/drime5_ep, O_RDONLY) = fd %d  ★全程只读\n\n", fd_ep);

    if (get_info() < 0) { close(fd_ep); return 3; }

    if (!strcmp(cmd, "map"))       cmd_map();
    else if (!strcmp(cmd, "scan")) {
        selftest();
        /* ★ 默认只扫 mc（idx=2）：首版扫全 10 块把单核相机压到重启。
         *   要扫别块用 `scan <idx>`，全扫用 `all`（不建议）。 */
        cmd_scan(argc > 2 ? atoi(argv[2]) : 2);
    }
    else if (!strcmp(cmd, "all"))  { selftest(); cmd_scan(-1); }
    else if (!strcmp(cmd, "watch")) cmd_watch(argc > 2 ? atoi(argv[2]) : 2);
    else if (!strcmp(cmd, "diff"))  cmd_diff(argc > 2 ? atoi(argv[2]) : 2);
    else { printf("用法: %s map|scan[blk]|all|watch<blk>|diff<blk>\n", argv[0]); }

    close(fd_ep);
    return 0;
}
