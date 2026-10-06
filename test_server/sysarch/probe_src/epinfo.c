/*
 * epinfo.arm -- NX500 EP / SMA / IPCC 只读能力探针（v2：零 printf）
 *
 * v1 崩溃原因：static glibc 的 printf 变参处理在 NX500 上出错
 *   （报CA9 user fault signal=4 + "arc = 5, optind = 5"）。
 *   ⇒ v2 完全不用 printf，全部用 write(2) 自己格式化十六进制。
 *
 * 目标（全部只读，不写硬件）：
 *   1. NX500 内核真实 ioctl ABI 是否 == NX1 GPL 头文件
 *   2. EP 3DLUT / NOG 寄存器物理基址能否拿到
 *   3. SMA 共享内存区域范围
 *   4. IPCC 跨核邮箱可用量
 *
 * 用法: epinfo [normal|nrscan|sma|ipcc]
 *   normal = 全部（默认）
 *   nrscan = 只扫 EP nr 空间
 *   sma/ipcc = 只跑对应段（用于二分定位崩溃）
 */

#include <string.h>
#include <errno.h>
#include <fcntl.h>
#include <unistd.h>
#include <sys/ioctl.h>
#include <stdlib.h>

/* ---- asm-generic ioctl 编码 ---- */
#define _IOC(dir, type, nr, size) \
    (((dir) << 30) | ((size) << 16) | ((type) << 8) | (nr))
#define MY_IOR(type, nr, size)  _IOC(2, type, nr, sizeof(size))
#define MY_IOWR(type, nr, size) _IOC(3, type, nr, sizeof(size))

#define EP_MAGIC   'h'
#define EP_NR_REG  100
#define SMA_MAGIC  's'
#define IPCC_MAGIC 't'

struct ep_phys { unsigned int start, size; };
struct ep_reg_info_80 {
    struct ep_phys top, ldc, mc, rsz, lvr, bblt, fd, jpeg, lut3d, nog;
};
struct ipcc_available_info { int core_id; int ret; };

static char obuf[4096];
static int  opos;

static void flushout(void)
{
    if (opos > 0) { write(1, obuf, opos); opos = 0; }
}

static void os_(const char *s)
{
    while (*s) {
        if (opos >= (int)sizeof(obuf)) flushout();
        obuf[opos++] = *s++;
    }
}

static const char hexd[] = "0123456789abcdef";

static void ox32(unsigned int v, int width)
{
    char t[16];
    int i = 0, j;
    for (j = 0; j < width; j++) t[j] = '0';
    j = width;
    while (v && j > 0) { t[--j] = hexd[v & 0xf]; v >>= 4; }
    for (i = 0; i < width; i++) os_(t + i);
}

static void odec(int v)
{
    char t[16];
    int i = 0;
    int neg = 0;
    unsigned int u;
    if (v < 0) { neg = 1; u = (unsigned)(-(long)v); } else u = (unsigned)v;
    if (u == 0) { os_("0"); return; }
    while (u) { t[i++] = (char)('0' + (u % 10)); u /= 10; }
    if (neg) os_("-");
    while (i > 0) os_(t + --i);
}

static void ospace(int n) { while (n-- > 0) os_(" "); }
static void onl(void) { os_("\n"); }
static void ohr(const char *t) { os_("\n===== "); os_(t); os_(" =====\n"); }

static const char *ep_names[10] = {
    "top", "ldc", "mc", "rsz", "lvr", "bblt", "fd", "jpeg", "3DLUT", "NOG"
};

static void ophys(const char *nm, unsigned int start, unsigned int size)
{
    os_("  "); os_(nm); os_(" : start=0x"); ox32(start, 8);
    os_("  size=0x"); ox32(size, 8);
    os_("  ("); odec((int)size); os_(")\n");
}

static void pr_res(const char *tag, unsigned long cmd, int r)
{
    os_("  "); os_(tag); os_(" cmd=0x"); ox32((unsigned int)cmd, 8);
    os_(" -> r="); odec(r);
    if (r < 0) { os_(" errno="); odec(errno); os_(" ("); os_(strerror(errno)); os_(")"); }
    onl();
}

/* ============ EP ============ */
static void probe_ep(int nrscan)
{
    int fd;
    int i;
    os_("open /dev/drime5_ep\n");
    fd = open("/dev/drime5_ep", O_RDWR);
    if (fd < 0) { fd = open("/dev/drime5_ep", O_RDONLY); os_("O_RDWR failed, tried O_RDONLY\n"); }
    if (fd < 0) { os_("  FAILED: "); os_(strerror(errno)); onl(); flushout(); return; }
    os_("  fd="); odec(fd); onl();

    if (nrscan) {
        int nr, hits = 0;
        os_("--- nr scan magic='h' size=80---\n");
        flushout();
        for (nr = 1; nr < 128; nr++) {
            unsigned char buf[80];
            unsigned long cmd;
            memset(buf, 0, 80);
            cmd = MY_IOR(EP_MAGIC, nr, unsigned char[80]);
            if (ioctl(fd, cmd, buf) == 0) {
                os_("  nr="); odec(nr); os_(" OK  u32:");
                for (i = 0; i < 20; i++) {
                    os_(" 0x"); ox32(((unsigned int *)buf)[i], 8);
                    if (i % 4 == 3) onl(); else os_("");
                }
                onl();
                hits++;
                flushout();
            }
        }
        os_("  hits="); odec(hits); onl();
        close(fd);
        flushout();
        return;
    }

    {
        int sizes[3];
        sizes[0] = 80; sizes[1] = 72; sizes[2] = 40;
        for (i = 0; i < 3; i++) {
            unsigned char buf[80];
            unsigned long cmd;
            int r;
            memset(buf, 0, 80);
            cmd = 0x80000000UL | ((unsigned long)sizes[i] << 16)
                | ((unsigned long)EP_MAGIC << 8) | (unsigned long)EP_NR_REG;
            r = ioctl(fd, cmd, buf);
            pr_res("EP_GET_PHYS_REG_INFO", cmd, r);
            if (r == 0 && sizes[i] == 80) {
                struct ep_reg_info_80 *e = (struct ep_reg_info_80 *)buf;
                struct ep_phys *v = &e->top;
                int k, nz = 0;
                os_("  --- 10 sub-blocks ---\n");
                for (k = 0; k < 10; k++) {
                    ophys(ep_names[k], v[k].start, v[k].size);
                    if (v[k].start || v[k].size) nz++;
                }
                os_("  non-zero blocks: "); odec(nz); os_("/10\n");
            }
            flushout();
        }
    }
    close(fd);
    flushout();
}

/* ============ SMA ============ */
static void probe_sma(void)
{
    int fd;
    unsigned int v;
    int r;
    os_("open /dev/d5_sma\n");
    fd = open("/dev/d5_sma", O_RDWR);
    if (fd < 0) fd = open("/dev/d5_sma", O_RDONLY);
    if (fd < 0) { os_("  FAILED: "); os_(strerror(errno)); onl(); flushout(); return; }
    os_("  fd="); odec(fd); onl();

    v = 0; r = ioctl(fd, MY_IOR(SMA_MAGIC, 1, unsigned int), &v);
    os_("  SMA_GET_REGION_SIZE       "); pr_res("", MY_IOR(SMA_MAGIC,1,unsigned int), r);
    os_("        val=0x"); ox32(v, 8); os_(" ("); odec((int)v); os_(")\n");

    v = 0; r = ioctl(fd, MY_IOR(SMA_MAGIC, 4, unsigned int), &v);
    os_("  SMA_GET_REGION_START_ADDR "); pr_res("", MY_IOR(SMA_MAGIC,4,unsigned int), r);
    os_("        val=0x"); ox32(v, 8); onl();

    v = 0; r = ioctl(fd, MY_IOR(SMA_MAGIC, 8, unsigned int), &v);
    os_("  SMA_GET_ALLOCATED_SIZE    "); pr_res("", MY_IOR(SMA_MAGIC,8,unsigned int), r);
    os_("        val=0x"); ox32(v, 8); os_(" ("); odec((int)v); os_(")\n");

    os_("  SMA_VIRT_TO_PHYS          SKIPPED (IOWR, 不在本轮只读范围)\n");
    close(fd);
    flushout();
}

/* ============ IPCC ============ */
static void probe_ipcc(void)
{
    int fd, cid;
    os_("open /dev/d5_ipcc\n");
    fd = open("/dev/d5_ipcc", O_RDWR);
    if (fd < 0) fd = open("/dev/d5_ipcc", O_RDONLY);
    if (fd < 0) { os_("  FAILED: "); os_(strerror(errno)); onl(); flushout(); return; }
    os_("  fd="); odec(fd); onl();
    os_("  cmds: W=0x"); ox32((unsigned int)MY_IOWR(IPCC_MAGIC,3,struct ipcc_available_info), 8);
    os_(" R=0x"); ox32((unsigned int)MY_IOWR(IPCC_MAGIC,4,struct ipcc_available_info), 8);
    os_(" L=0x"); ox32((unsigned int)MY_IOWR(IPCC_MAGIC,5,struct ipcc_available_info), 8);
    onl();

    for (cid = 0; cid < 8; cid++) {
        struct ipcc_available_info a;
        int r;
        a.core_id = cid; a.ret = -999;
        r = ioctl(fd, MY_IOWR(IPCC_MAGIC, 3, struct ipcc_available_info), &a);
        os_("  core="); odec(cid); os_(" write_avail: r="); odec(r);
        os_(" ret="); odec(a.ret);
        if (r < 0) { os_(" ("); os_(strerror(errno)); os_(")"); }
        onl();

        a.core_id = cid; a.ret = -999;
        r = ioctl(fd, MY_IOWR(IPCC_MAGIC, 4, struct ipcc_available_info), &a);
        os_("  core="); odec(cid); os_(" read_avail : r="); odec(r);
        os_(" ret="); odec(a.ret);
        if (r < 0) { os_(" ("); os_(strerror(errno)); os_(")"); }
        onl();

        a.core_id = cid; a.ret = -999;
        r = ioctl(fd, MY_IOWR(IPCC_MAGIC, 5, struct ipcc_available_info), &a);
        os_("  core="); odec(cid); os_(" pkt_len    : r="); odec(r);
        os_(" ret="); odec(a.ret);
        if (r < 0) { os_(" ("); os_(strerror(errno)); os_(")"); }
        onl();
        flushout();
    }
    close(fd);
    flushout();
}

int main(int argc, char **argv)
{
    const char *m = (argc > 1) ? argv[1] : "normal";
    int do_ep = 1, do_sma = 1, do_ipcc = 1;

    if (!strcmp(m, "nrscan")) { do_sma = 0; do_ipcc = 0; }
    else if (!strcmp(m, "sma"))   { do_ep = 0; do_ipcc = 0; }
    else if (!strcmp(m, "ipcc"))  { do_ep = 0; do_sma = 0; }
    else if (!strcmp(m, "ep"))    { do_sma = 0; do_ipcc = 0; }

    os_("NX500 EP/SMA/IPCC read-only probe v2\n");
    os_("mode="); os_(m); onl();
    os_("EP magic='h' nr=100 | SMA magic='s' | IPCC magic='t'\n");
    os_("sizeof(ep_phys)="); odec((int)sizeof(struct ep_phys));
    os_(" x10="); odec((int)sizeof(struct ep_reg_info_80));
    os_(" sizeof(ipcc_available_info)=");
    odec((int)sizeof(struct ipcc_available_info)); onl();
    flushout();

    if (do_ep) { ohr("1. EP  /dev/drime5_ep");  probe_ep(!strcmp(m, "nrscan")); }
    if (do_sma){ ohr("2. SMA /dev/d5_sma");    probe_sma(); }
    if (do_ipcc){ohr("3. IPCC /dev/d5_ipcc");   probe_ipcc(); }
    ohr("done");
    flushout();
    return 0;
}