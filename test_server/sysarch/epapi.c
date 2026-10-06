/* epapi.c —— libudd5.so EP 编程 API 探针★★ v1：纯只读，只做 dlsym 符号解析
 *
 * ★★★ 安全边界（v1 绝不违反）
 *   本版本【不调用】任何 d5_ep_* 函数，不 open /dev/drime5_ep，不碰任何 EP 寄存器。
 *   只做 dlopen + dlsym，把符号是否存在、地址多少打印出来。
 *   ⇒ 零风险：最坏情况是 dlopen 失败。
 *
 * 用法: ./epapi            → 列出全部 EP 相关导出符号
 *编译: zig cc -target arm-linux-gnueabi.2.15 -O0 ... （见 README）
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <dlfcn.h>

/* 魔灯关心的符号清单（★ 全部来自 libudd5.so 的 .dynsym 实测导出） */
static const char *WANT[] = {
    /* ── 3D LUT（魔灯核心）── */
    "d5_ep_3dl_load_lut",
    "d5_ep_3dl_save_lut",
    "d5_ep_3dlut_op_init",
    "_udd_ep_3dl_reg_SetReg",
    "_udd_ep_3dl_reg_GetReg",
    "_udd_ep_3dl_reg_SetAddress",
    "_udd_ep_3dl_reg_SelLUT",
    "_udd_ep_3dl_reg_SetColorFormat_LUT0",
    "_udd_ep_3dl_reg_SetColorFormat_LUT1",
    "_udd_ep_3dl_reg_rw_Start",
    "_udd_ep_3dl_reg_OnOff",
    "_udd_ep_3dl_reg_Acc_OnOff",
    "_udd_ep_3dl_ctrl_ConfigAccessMode",
    "_udd_ep_3dl_ctrl_ConfigProcessMode",
    "_udd_ep_3dl_ctrl_ConfigBypassMode",
    /* ── NOG 颗粒 ── */
    "d5_ep_nog_set_noisegen",
    "d5_ep_nog_set_bypass",
    "_udd_ep_nog_set_gamma",
    "_udd_ep_nog_set_std_sigma",
    "_udd_ep_nog_set_random_seed",
    "_udd_ep_nog_select_rv_type",
    "_udd_ep_nog_seed_load_switch",
    "_udd_ep_nog_reg_struct_init",
    /* ── 色彩矩阵 ── */
    "d5_ep_mc_set_custom_param_yccmixer",
    "d5_ep_mc_get_default_param",
    "d5_ep_mc_set_default_config",
    /* ── EP 基础 ── */
    "d5_ep_open",
    "d5_ep_close",
    "d5_ep_sma_virt_to_phys",
    /* ── 数据符号（NOG 参数表，★ 直接可读）── */
    "_udd_ep_nog_regset0",
    "_udd_ep_nog_regset1",
    "ep_nog_reg_base",
    "ep_3dlut_reg_base",
    "ep_top_reg_base",
    "g_d5_dev_ctx",
};
#define NWANT ((int)(sizeof(WANT) / sizeof(WANT[0])))

int main(int argc, char **argv)
{
    void *h;
    int i, nfound = 0;

    setvbuf(stdout, NULL, _IOLBF, 0);

    printf("=== NX500 libudd5.so EP API probe v1 (READ-ONLY) ===\n");
    printf("phase1: dlopen\n");

    h = dlopen("libudd5.so", RTLD_NOW);
    if (!h) {
        printf("  dlopen(libudd5.so) FAILED: %s\n", dlerror());
        /* 试带路径 */
        h = dlopen("/usr/lib/libudd5.so", RTLD_NOW);
        if (!h) {
            printf("  dlopen(/usr/lib/libudd5.so) FAILED: %s\n", dlerror());
            return 1;
        }
        printf("  ok with /usr/lib/libudd5.so\n");
    } else {
        printf("  ok\n");
    }

    printf("\nphase2: dlsym (NOT calling anything)\n");
    printf("%-42s %-12s %s\n", "symbol", "found", "addr");
    for (i = 0; i < NWANT; i++) {
        void *a = dlsym(h, WANT[i]);
        if (a) {
            nfound++;
            printf("  %-40s %-12s %p\n", WANT[i], "YES", a);
        } else {
            printf("  %-40s %-12s\n", WANT[i], "no", "-");
        }
    }
    printf("\n=== %d / %d symbols resolved ===\n", nfound, NWANT);

    /* NOG 参数表当前值（★ 只读！这正是 p7 侧 FUN_004aff08 的源数据）*/
    printf("\nphase3: read NOG param tables (READ-ONLY, 32 bytes each)\n");
    {
        unsigned *r0 = (unsigned *)dlsym(h, "_udd_ep_nog_regset0");
        unsigned *r1 = (unsigned *)dlsym(h, "_udd_ep_nog_regset1");
        unsigned *base = (unsigned *)dlsym(h, "ep_nog_reg_base");
        if (base) printf("  ep_nog_reg_base  = 0x%08x\n", *base);
        else        printf("  ep_nog_reg_base  = <not found>\n");

        if (r0) {
            printf("  _udd_ep_nog_regset0[0..7]: ");
            for (i = 0; i < 8; i++) printf("0x%08x ", r0[i]);
            printf("\n");
        } else printf("  regset0 <not found>\n");
        if (r1) {
            printf("  _udd_ep_nog_regset1[0..7]: ");
            for (i = 0; i < 8; i++) printf("0x%08x ", r1[i]);
            printf("\n");
        } else printf("  regset1 <not found>\n");
    }

    /* EP 3DLUT 基址（★ 与我们 /dev/mem 读到的 0x2082b000 对照）*/
    printf("\nphase4: EP block base addresses (READ-ONLY)\n");
    {
        static const char *nm[] = { "ep_top_reg_base", "ep_nog_reg_base",
                                    "ep_3dlut_reg_base", "ep_mc_reg_base",
                                    "ep_jpeg_reg_base", "ep_lvr_reg_base",
                                    "ep_ldc_reg_base", "ep_rsz_reg_base",
                                    "ep_fd_reg_base", "ep_bblt_reg_base" };
        int n = (int)(sizeof(nm) / sizeof(nm[0]));
        for (i = 0; i < n; i++) {
            unsigned *p = (unsigned *)dlsym(h, nm[i]);
            if (p) printf("  %-20s = 0x%08x\n", nm[i], *p);
            else    printf("  %-20s = <not found>\n", nm[i]);
        }
    }

    printf("\n=== probe done (nothing was called, nothing written) ===\n");
    dlclose(h);
    return 0;
}
