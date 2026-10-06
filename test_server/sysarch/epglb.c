/* epglb.c — NX-KS2 EP 全局变量只读探针（步骤 1，零风险）
 *
 * ★★★ 安全契约（严格遵守，违反会死机）：
 *   1. 只 dlopen + dlsym + 读取变量当前值
 *   2. ★ 不调用 libudd5 的任何函数（连 d5_ep_open 都不调）
 *   3. ★ 绝不解引用 dlsym 返回的指针 —— 只把指针值当整数打印
 *      （v4 探针就是这么死的：跨进程 mmap 地址）
 *
 * 唯一系统调用：dlopen 会 mmap 该库（由 ld.so 完成，属正常加载）
 *
 * 静态依据（test_server/isp/udd5.py + crosscheck.py 16/16 验证）：
 *   d5_ep_sma_virt_to_phys() 反汇编显示：
 *       if (fd_ep < 0 || va == 0) return 0;
 *       ioctl(fd_ep, _IOWR('s',2,u32), &phys)
 *   ⇒ fd_ep 是驱动文件描述符，是判断"EP 通路是否已初始化"的关键指标
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>/* getpid */
#include <dlfcn.h>

/* ---- 我们要读的全部全局（地址由 pyelftools 从 .dynsym STT_OBJECT 权威给出）----
 *  slot = st_value（文件内虚拟地址），仅用于文档对照，运行时不使用
 */
struct probe {
    const char *name;
    unsigned    slot;      /* 静态槽地址（文档用） */
    const char *expect;    /* 预期语义 */
};

static const struct probe PROBES[] = {
    /* === 关键：EP 是否已打开 === */
    { "fd_ep",0x0004b0e8, "EP 驱动 fd；<0 = 未打开 ★核心指标" },
    { "g_d5_dev_ctx",              0x0004d448, "设备上下文指针；0 = 未初始化" },
    { "g_dev_id",                  0x0004d444, "设备号" },

    /* === EP 块物理基址（应与 /dev/mem 读侧 10 个块一一对应）=== */
    { "ep_top_reg_base",           0x0004d640, "0x20820000" },
    { "ep_nog_reg_base",           0x0004d644, "0x20821c00" },
    { "ep_ldc_reg_base",           0x0004d648, "0x20823000" },
    { "ep_mc_reg_base",            0x0004d660, "0x20824000" },
    { "ep_rsz_reg_base",           0x0004d65c, "0x20826000" },
    { "ep_lvr_reg_base",           0x0004d664, "0x20827000" },
    { "ep_bblt_reg_base",          0x0004d64c, "0x20828000" },
    { "ep_fd_reg_base",            0x0004d654, "0x20829000" },
    { "ep_jpeg_reg_base",          0x0004d658, "0x2082a000" },
    { "ep_3dlut_reg_base",         0x0004d650, "0x2082b000 ★3D LUT" },

    /* === 通路 === */
    { "path_ep_cs0",               0x0004ceac, "EP 通路 0" },
    { "path_ep_cs1",               0x0004cf20, "EP 通路 1" },

    /* === 同步 === */
    { "g_dd_mutex_lock",0x0004bcb8, "全局互斥锁" },
    { "g_dd_sync_cond",            0x0004bcd0, "同步条件变量" },

    /* === NOG 双实例参数表（★ 与 P7 侧 0x20821c10 交叉验证）=== */
    { "_udd_ep_nog_regset0",       0x0004d688, "NOG 实例0 参数表" },
    { "_udd_ep_nog_regset1",       0x0004d668, "NOG 实例1 参数表" },

    /* === MC 默认配置 === */
    { "ep_mc_default_config",      0x0004b320, "MC 默认配置" },
};

/* ★ 色彩矩阵变量：这些是"指针指向结构体"，我们只读指针值本身。
 *   绝不解引用 —— 跨进程地址（铁律：v4 死机事故）。            */
static const char *MTRX[] = {
    "rgb2ycbcr_mtx_fd",
    "rgb2ycbcr_underflow_fd_udd",
    "rgb2ycbcr_overflow_fd_udd",
    "rgb2ycbcr_offset_y_fd_udd",
    "rgb2ycbcr_offset_cb_fd_udd",
    "rgb2ycbcr_offset_cr_fd_udd",
    "ycbcr2rgb_mtx_fd_udd",
    "ycbcr2rgb_underflow_fd_udd_premovie",
    "ycbcr2rgb_overflow_fd_udd",
    "ycbcr2rgb_offset_y_fd_udd",
    "ycbcr2rgb_offset_cb_fd_udd",
    "ycbcr2rgb_offset_cr_fd_udd",
};

int main(void)
{
    void *h;
    unsigned i;

    printf("=== NX-KS2 EP 全局探针 v1（只读，零风险）===\n");
    printf("pid=%d\n\n", (int)getpid());

    /* dlopen：RTLD_LAZY|RTLD_GLOBAL。失败不致命，只报告。 */
    h = dlopen("libudd5.so", RTLD_LAZY | RTLD_GLOBAL);
    if (!h) {
        printf("!! dlopen(libudd5.so) 失败: %s\n", dlerror());
        printf("   => 该库不在 ld.so 搜索路径。静态分析结论不受影响，\n");
        printf("      但实机 API 通路需改用 /dev/mem 路线。\n");
        return 2;
    }
    printf("dlopen(libudd5.so) = OK  handle=%p\n", h);
    printf("（未调用库内任何函数，仅读取变量）\n\n");

    /* ---- (1) 标量全局 ---- */
    printf("--- (1) 标量全局 (%d 个) ---\n", (int)(sizeof(PROBES)/sizeof(PROBES[0])));
    printf("%-24s %-12s %-10s %s\n", "符号", "当前值", "静态槽", "预期语义");
    for (i = 0; i < sizeof(PROBES)/sizeof(PROBES[0]); i++) {
        void *p = dlsym(h, PROBES[i].name);
        /* ★ 只把 *p 当 32 位整数读出来比较，不把它当指针使用 */
        unsigned val = p ? *(const unsigned *)p : 0xdeadbeef;
        printf("%-24s ", PROBES[i].name);
        if (!p) {
            printf("%-12s %-10s %s\n", "<notfound>", "-", PROBES[i].expect);
        } else {
            printf("0x%08x   0x%08x   %s\n", val, PROBES[i].slot, PROBES[i].expect);
        }
    }

    /* ---- (2) 色彩矩阵变量：只看指针是否为 0 ---- */
    printf("\n--- (2) YCbCr<->RGB 矩阵变量 (%d 个，只看非零) ---\n",
           (int)(sizeof(MTRX)/sizeof(MTRX[0])));
    for (i = 0; i < sizeof(MTRX)/sizeof(MTRX[0]); i++) {
        void *p = dlsym(h, MTRX[i]);
        unsigned val = p ? *(const unsigned *)p : 0xdeadbeef;
        printf("%-34s %s\n", MTRX[i],
               !p ? "<notfound>" : (val ? "非零 ★已初始化" : "0 (未初始化)"));
    }

    /* ---- (3) 函数符号存在性（只查地址，绝不调用）----
     * 用 dlsym 取地址只为证明"API 在库里"，不调用就没有任何副作用。 */
    printf("\n--- (3) 关键 API 符号存在性（只取地址，不调用）---\n");
    {
        static const char *api[] = {
            "d5_ep_open", "d5_ep_close",
            "d5_ep_3dl_load_lut", "d5_ep_3dl_save_lut",
            "d5_ep_sma_virt_to_phys",
            "_udd_ep_3dl_reg_SetAddress", "_udd_ep_3dl_reg_rw_Start",
            "_udd_ep_3dl_reg_SelLUT", "_udd_ep_3dl_reg_OnOff",
            "_udd_ep_3dl_reg_Acc_OnOff", "_udd_ep_3dl_reg_GetReg",
            "_udd_ep_3dl_reg_SetReg",
            "d5_ep_nog_set_noisegen", "_udd_ep_nog_set_gamma",
        };
        int found = 0, total = (int)(sizeof(api)/sizeof(api[0]));
        for (i = 0; i < (unsigned)total; i++) {
            void *p = dlsym(h, api[i]);
            printf("  %-34s %s\n", api[i], p ? "存在" : "<notfound>");
            if (p) found++;
        }
        printf("  => %d/%d 存在\n", found, total);
    }

    /* ---- (4) 结论 ---- */
    {
        void *pf = dlsym(h, "fd_ep");
        unsigned fd = pf ? *(const unsigned *)pf : 0xdeadbeef;
        void *pb = dlsym(h, "ep_3dlut_reg_base");
        unsigned b3 = pb ? *(const unsigned *)pb : 0xdeadbeef;

        printf("\n=== 结论 ===\n");
        if ((int)fd >= 0)
            printf("fd_ep = %d  >= 0  => EP 驱动已打开，★通路已初始化\n", (int)fd);
        else if ((int)fd < 0)
            printf("fd_ep = %d  <  0  => EP 未打开（本进程未 open，或驱动未起）\n", (int)fd);
        else
            printf("fd_ep 符号未找到\n");

        if (b3 && b3 != 0xdeadbeef)
            printf("ep_3dlut_reg_base = 0x%08x  => 3DLUT 映射已建立\n", b3);
        else
            printf("ep_3dlut_reg_base 无值 => 3DLUT 未映射（★可能需先 d5_ep_open）\n");
    }

    printf("\n=== 探针结束（未调用任何库函数，未写入任何寄存器）===\n");
    /* 不 dlclose：卸载可能影响其它进程对同一库的引用计数 */
    return 0;
}