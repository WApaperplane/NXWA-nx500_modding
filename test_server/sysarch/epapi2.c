/* epapi2.c —— libudd5.so EP API 探针 v2★★ 只读，只 save_lut，绝不 load★
 *
 * ★★★★★ 安全边界（v2 严格遵守）
 *   允许：open("/dev/drime5_ep")  ioctl(0x80506864)  d5_ep_open()  d5_ep_3dl_save_lut()
 *   ★禁止：d5_ep_3dl_load_lut() / _udd_ep_3dl_reg_SetReg() / 任何写 EP 的函数
 *   ★禁止：直接改写 _udd_ep_nog_regset0/1 等库内部变量
 *   ⇒ 失败最坏：ioctl/open 失败 → 退出码非 0；EP 硬件状态不变
 *
 * 编译：
 *   zig cc -target arm-linux-gnueabi.2.15 -O0 -I$ROOTFS/include \
 *       -mfloat-abi=soft -fno-stack-protector -s -rdynamic epapi2.c -o epapi2.arm -ldl
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <fcntl.h>
#include <unistd.h>
#include <dlfcn.h>
#include <sys/ioctl.h>

/* EP_IOCTL_GET_PHYS_REG_INFO（epinfo3 实测值）*/
#define EP_REGINFO_CMD 0x80506864UL

typedef int (*fn_open_t)(void *);
typedef int (*fn_close_t)(void *);
typedef int (*fn_savelut_t)(void *);
typedef int (*fn_nogt_t)(int, int);

/* EP 物理信息：20 个 u32 = 10 组 (start, size) */
struct ep_reg_info {
    unsigned hw[20];
};

int main(int argc, char **argv)
{
    void *h;
    int i, r, epfd = -1;
    unsigned long *ioaddr;
    void *p;

    setvbuf(stdout, NULL, _IOLBF, 0);

    printf("=== NX500 EP API probe v2 (READ-ONLY: open+ioctl+open_ep+save_lut) ===\n\n");

    /* ── phase 1: dlopen ── */
    h = dlopen("libudd5.so", RTLD_NOW);
    if (!h) {
        printf("dlopen FAILED: %s\n", dlerror());
        return 1;
    }
    printf("phase1: dlopen ok\n");

    /* ── phase 2: open + ioctl（只读）── */
    epfd = open("/dev/drime5_ep", O_RDWR);
    if (epfd < 0) {
        epfd = open("/dev/drime5_ep", O_RDONLY);
        printf("phase2: open(O_RDWR) failed, fallback O_RDONLY\n");
    }
    if (epfd < 0) {
        printf("phase2: open /dev/drime5_ep FAILED\n");
        return 2;
    }
    printf("phase2: /dev/drime5_ep opened (fd=%d)\n", epfd);

    ioaddr = (unsigned long *)malloc(256);
    memset(ioaddr, 0, 256);
    r = ioctl(epfd, EP_REGINFO_CMD, ioaddr);
    printf("  ioctl(0x%08lx) = %d\n", EP_REGINFO_CMD, r);
    printf("  raw ioctl buffer (20 x u32):\n   ");
    for (i = 0; i < 20; i++) {
        printf("0x%08x%s", ioaddr[i], (i % 5 == 4) ? "\n   " : " ");
    }
    printf("\n");

    /* 解析成 10 组 (base, size) */
    {
        static const char *nm[10] = {
            "top", "ldc", "mc", "rsz", "lvr", "bblt", "fd", "jpeg", "3dlut", "nog"
        };
        struct ep_reg_info *ri = (struct ep_reg_info *)ioaddr;
        printf("  parsed EP blocks:\n");
        for (i = 0; i < 10; i++) {
            printf("    [%d] %-6s base=0x%08x size=0x%08x\n",
                   i, nm[i], ri->hw[i * 2], ri->hw[i * 2 + 1]);
        }
    }

    /* ── phase 3: d5_ep_open ── */
    p = dlsym(h, "d5_ep_open");
    if (!p) { printf("phase3: dlsym(d5_ep_open) failed\n"); return 3; }
    {
        fn_open_t ep_open = (fn_open_t)p;
        void *handle = NULL;
        r = ep_open((void *)ioaddr);
        handle = (void *)(long)r;
        printf("\nphase3: d5_ep_open() = 0x%08x\n", r);
        if (r == 0) {
            printf("  ★ returned 0 —— 可能需要不同的参数形式\n");
        }

        /* 立即回读 reg_base 验证是否被填上 */
        {
            static const char *bn[10] = {
                "top", "nog", "3dlut", "mc", "jpeg", "lvr", "ldc", "rsz", "fd", "bblt"
            };
            int j;
            printf("  ep_*_reg_base after open:\n");
            for (j = 0; j < 10; j++) {
                char sym[48];
                unsigned *bp;
                snprintf(sym, sizeof(sym), "ep_%s_reg_base", bn[j]);
                bp = (unsigned *)dlsym(h, sym);
                if (bp) printf("    %-20s = 0x%08x\n", sym, *bp);
                else    printf("    %-20s = <not found>\n", sym);
            }
        }
        /* NOG 参数表 */
        {
            unsigned *r0 = (unsigned *)dlsym(h, "_udd_ep_nog_regset0");
            unsigned *r1 = (unsigned *)dlsym(h, "_udd_ep_nog_regset1");
            if (r0) {
                printf("    _udd_ep_nog_regset0: ");
                for (i = 0; i < 8; i++) printf("0x%08x ", r0[i]);
                printf("\n    _udd_ep_nog_regset1: ");
                for (i = 0; i < 8; i++) printf("0x%08x ", r1[i]);
                printf("\n");
            }
        }

        /* ── phase 4: save_lut（纯读）── */
        p = dlsym(h, "d5_ep_3dl_save_lut");
        if (p) {
            fn_savelut_t save_lut = (fn_savelut_t)p;
            unsigned short lut[1024 * 3];
            memset(lut, 0xAA, sizeof(lut));
            r = save_lut(handle);
            printf("\nphase4: d5_ep_3dl_save_lut() = %d\n", r);
            {
                int nz = 0;
                for (i = 0; i < 1024 * 3 && i < 300; i++) {
                    if (lut[i] != 0xAAAA && lut[i] != 0) nz++;
                }
                printf("  lut[0..299] non-default count = %d\n", nz);
                printf("  lut[0..15]: ");
                for (i = 0; i < 16; i++) printf("0x%04x ", lut[i]);
                printf("\n  lut[256..271]: ");
                for (i = 256; i < 272; i++) printf("0x%04x ", lut[i]);
                printf("\n  lut[512..527]: ");
                for (i = 512; i < 528; i++) printf("0x%04x ", lut[i]);
                printf("\n");
                /* dump 完整 LUT */
                {
                    FILE *fp = fopen("/mnt/mmc/_xfer/lut_dump.txt", "w");
                    if (fp) {
                        fprintf(fp, "# d5_ep_3dl_save_lut dump, ret=%d\n", r);
                        for (i = 0; i < 1024; i++) {
                            fprintf(fp, "%4d: 0x%04x 0x%04x 0x%04x\n",
                                    i, lut[i * 3], lut[i * 3 + 1], lut[i * 3 + 2]);
                        }
                        fclose(fp);
                        printf("  >> saved /mnt/mmc/_xfer/lut_dump.txt (1024 lines)\n");
                    }
                }
            }
        } else {
            printf("phase4: dlsym(d5_ep_3dl_save_lut) failed\n");
        }

        /* ── phase 5: 关闭 ── */
        p = dlsym(h, "d5_ep_close");
        if (p) {
            fn_close_t ep_close = (fn_close_t)p;
            r = ep_close(handle);
            printf("\nphase5: d5_ep_close() = %d\n", r);
        }
    }

    if (epfd >= 0) close(epfd);
    free(ioaddr);
    printf("\n=== v2 done (NO writes to EP were performed) ===\n");
    dlclose(h);
    return 0;
}
