/* epapi3.c —— libudd5.so EP API 探针 v3 ★只读：多形态试 handle + save_lut
 *
 * ★★★★★ 安全边界
 *   允许：open /dev/drime5_ep、ioctl(0x80506864)、d5_ep_open、d5_ep_3dl_save_lut
 *   ★禁止：d5_ep_3dl_load_lut、_udd_ep_3dl_reg_SetReg、任何其他写 EP 的函数
 *   ★禁止：往任何 ep_*_reg_base / regset 写值
 *   ⇒ 失败最坏：save_lut 返回 -1（内部校验失败），EP 状态不变
 *
 * v2 已证：save_lut(handle, lut_sel<=2, buf, buf2)，handle==0 直接返回 -1
 * 本版：遍历多个候选 handle 形态，每个都试 lut_sel = 0/1/2
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <fcntl.h>
#include <unistd.h>
#include <dlfcn.h>
#include <sys/ioctl.h>

#define EP_REGINFO_CMD 0x80506864UL

typedef int (*fn_open_t)(void);   /* ★ 反汇编证实：无参数 */
typedef int (*fn_savelut_t)(void *, int, void *, void *);

int main(int argc, char **argv)
{
    void *h;
    int i, r, epfd;
    unsigned long *ioaddr;
    void *p, *ctx = NULL, *epopen_ret;
    unsigned *bases[10];
    unsigned short buf[1024 * 3];

    setvbuf(stdout, NULL, _IOLBF, 0);
    printf("=== EP API probe v3 (READ-ONLY: handle probing + save_lut) ===\n\n");

    h = dlopen("libudd5.so", RTLD_NOW);
    if (!h) { printf("dlopen FAILED: %s\n", dlerror()); return 1; }
    printf("phase1: dlopen ok\n");

    /* ── 打开 + ioctl ── */
    epfd = open("/dev/drime5_ep", O_RDWR);
    if (epfd < 0) epfd = open("/dev/drime5_ep", O_RDONLY);
    if (epfd < 0) { printf("open /dev/drime5_ep FAILED\n"); return 2; }
    ioaddr = (unsigned long *)calloc(1, 256);
    r = ioctl(epfd, EP_REGINFO_CMD, ioaddr);
    printf("phase2: ioctl = %d, 10 blocks:\n", r);
    for (i = 0; i < 10; i++)
        printf("   [%d] 0x%08x / 0x%08x\n", i, ioaddr[i * 2], ioaddr[i * 2 + 1]);

    /* ── d5_ep_open ── */
    fn_open_t ep_open = (fn_open_t)dlsym(h, "d5_ep_open");
    if (!ep_open) { printf("dlsym(d5_ep_open) failed\n"); return 3; }
    epopen_ret = (void *)(long)ep_open();     /* ★ 反汇编: push{r4,fp,lr} 无参数 */
    printf("\nphase3: d5_ep_open() = %p  (ret<0 =失败: -1=ioctl失败, -0x63=mmap失败)\n", epopen_ret);

    /* 读回 reg_base（虚拟地址）*/
    {
        static const char *bn[10] = { "top","nog","3dlut","mc","jpeg",
                                      "lvr","ldc","rsz","fd","bblt" };
        for (i = 0; i < 10; i++) {
            char sym[48];
            snprintf(sym, sizeof(sym), "ep_%s_reg_base", bn[i]);
            bases[i] = (unsigned *)dlsym(h, sym);
        }
        printf("  reg_base after open:\n");
        for (i = 0; i < 10; i++)
            if (bases[i]) printf("    %-6s = 0x%08x\n", bn[i], *bases[i]);
    }

    /* ── 候选 handle 形态 ── */
    ctx = dlsym(h, "g_d5_dev_ctx");
    printf("\nphase3b: ep_open ret code = %ld  (0=OK, -1=ioctl fail, -0x63=-%ld mmap fail)\n",
           (long)epopen_ret, (long)epopen_ret * -1);
    printf("phase4: g_d5_dev_ctx = %p\n", ctx);
    if (ctx) {
        unsigned *c = (unsigned *)ctx;
        printf("  g_d5_dev_ctx[0..15] (u32 view):\n   ");
        for (i = 0; i < 16; i++) printf("0x%08x ", c[i]);
        printf("\n  g_d5_dev_ctx[0..15] (u8 view):\n   ");
        {
            unsigned char *b = (unsigned char *)ctx;
            for (i = 0; i < 48; i++) printf("%02x ", b[i]);
        }
        printf("\n");
    }

    /* ── phase 5: 遍历 handle × lut_sel 调 save_lut ── */
    {
        fn_savelut_t save_lut = (fn_savelut_t)dlsym(h, "d5_ep_3dl_save_lut");
        struct { const char *name; void *h; } cand[8];
        int nc = 0, s, hit = 0;

        if (!save_lut) { printf("dlsym(save_lut) failed\n"); return 4; }

        cand[nc].name = "ep_open_ret"; cand[nc++].h = epopen_ret;
        cand[nc].name = "g_d5_dev_ctx"; cand[nc++].h = ctx;
        cand[nc].name = "&g_d5_dev_ctx"; cand[nc++].h = &ctx;
        cand[nc].name = "epfd(/dev/drime5_ep)"; cand[nc++].h = (void *)(long)epfd;
        cand[nc].name = "1"; cand[nc++].h = (void *)0x1;
        cand[nc].name = "3dlut_reg_base"; cand[nc++].h = bases[2];
        cand[nc].name = "nog_reg_base"; cand[nc++].h = bases[1];

        printf("\nphase5: try %d handle candidates x 3 lut_sel (READ-ONLY)\n", nc);
        for (i = 0; i < nc; i++) {
            for (s = 0; s <= 2; s++) {
                int nz = 0, k;
                memset(buf, 0x5A, sizeof(buf));
                r = save_lut(cand[i].h, s, buf, buf);
                if (r == 0) {
                    for (k = 0; k < 1024 * 3; k++) {
                        if (buf[k] != 0x5A5A && buf[k] != 0) nz++;
                    }
                    printf("  ★★ HIT  handle=%-20s sel=%d  ret=0  nonzero=%d\n",
                           cand[i].name, s, nz);
                    printf("      lut[0..15]  : ");
                    for (k = 0; k < 16; k++) printf("0x%04x ", buf[k]);
                    printf("\n      lut[512..527]: ");
                    for (k = 512; k < 528; k++) printf("0x%04x ", buf[k]);
                    printf("\n      lut[1000..1015]: ");
                    for (k = 1000; k < 1016; k++) printf("0x%04x ", buf[k]);
                    printf("\n");
                    if (nz > 0) {
                        char path[96];
                        FILE *fp;
                        snprintf(path, sizeof(path),
                                 "/mnt/mmc/_xfer/lut_h%d_s%d.txt", i, s);
                        fp = fopen(path, "w");
                        if (fp) {
                            int j;
                            fprintf(fp, "# handle=%s sel=%d ret=0 nonzero=%d\n",
                                    cand[i].name, s, nz);
                            for (j = 0; j < 1024; j++)
                                fprintf(fp, "%4d: 0x%04x 0x%04x 0x%04x\n", j,
                                        buf[j*3], buf[j*3+1], buf[j*3+2]);
                            fclose(fp);
                            printf("      >> saved %s\n", path);
                            hit = 1;
                        }
                    }
                } else {
                    printf("     handle=%-20s sel=%d  ret=%d\n",
                           cand[i].name, s, r);
                }
            }
        }
        printf("\n=== %s ===\n", hit ? "LUT DUMPED" : "no handle worked (all returned != 0)");
    }

    if (epfd >= 0) close(epfd);
    free(ioaddr);
    printf("=== v3 done (NO writes to EP) ===\n");
    dlclose(h);
    return 0;
}
