/*
 * epreg.arm -- EP 寄存器块只读访问验证
 *
 * ★★ 这是 handle 墙绕道的决定性实验 ★★
 *  epinfo3 已经证明：EP_IOCTL_GET_PHYS_REG_INFO 能拿到 EP 十个子块的物理基址，
 *  其中 3DLUT = 0x2082b000/0x1000，NOG = 0x20821c00/0x100。
 *  现在的问题只有一个：这些地址能不能从 Linux 侧 mmap 读到？
 *    - 能读到（值不是全 0/全 F）=> 3D LUT / NOG 有可能在不改固件的前提下使用
 *    - mmap 失败 / 读到全 F => 这些地址在 ISP 核的地址空间，Linux 侧不可达
 *
 * ★ 安全边界（不可放宽）★
 *   PROT_READ only，绝不 PROT_WRITE。只 read()，绝不往映射区写。
 *   不调用 st readl/writel，不调用任何驱动提供的配置 ioctl。
 *   mmap 失败就跳过，绝不重试超过一次。
 *
 * 用法: epreg [addr_hex] [len_hex] ...
 *   不带参数 = 跑内置默认表
 */
#include <unistd.h>
#include <fcntl.h>
#include <errno.h>
#include <string.h>
#include <sys/mman.h>
#include <stdlib.h>

static int on;
static char ob[8192];
static void fl(void){ if(on){ write(1,ob,on); on=0; } }
static void p_(const char*s){ while(*s){ if(on>=(int)sizeof(ob))fl(); ob[on++]=*s++; } }
static void pc_(char c){ if(on>=(int)sizeof(ob))fl(); ob[on++]=c; }
static void pnl(void){ pc_('\n'); }
static void de_(int v){
    char b[16]; int m=0,i; unsigned u;
    if(v<0){ pc_('-'); u=(unsigned)(-v); } else u=(unsigned)v;
    if(u==0){ pc_('0'); return; }
    while(u){ b[m++]=(char)('0'+u%10); u/=10; }
    for(i=m;i>0;i--) pc_(b[i-1]);
}
static void hx_(unsigned v,int w){
    static const char H[]="0123456789abcdef";
    char b[16]; int m=0,i;
    if(v==0){ for(i=0;i<w;i++) pc_('0'); return; }
    while(v){ b[m++]=H[v%16u]; v/=16u; }
    for(i=w;i>m;i--) pc_('0');
    for(i=0;i<m;i++) pc_(b[m-1-i]);
}

struct tgt { const char *name; unsigned addr; unsigned len; };

/* epinfo3 实测值 + ge0rg liveview 已知可用地址做对照 */
static struct tgt TBL[] = {
    { "EP_top",    0x20820000UL, 0x1c00 },
    { "EP_NOG",    0x20821c00UL, 0x0100 },
    { "EP_3DLUT",  0x2082b000UL, 0x1000 },
    { "EP_jpeg",   0x2082a000UL, 0x1000 },
    { "EP_fd",     0x20829000UL, 0x1000 },
    { "EP_mc",     0x20824000UL, 0x2000 },
    { "LV_ref1",   0xbbaea500UL, 0x1000 },   /* ge0rg liveview.c 实测可用 */
    { "LV_ref2",   0xbbb68e00UL, 0x1000 },
};
#define NT ((int)(sizeof(TBL)/sizeof(TBL[0])))

static int memfd = -1;

static void try_one(const char *nm, unsigned addr, unsigned len)
{
    unsigned pg;
    off_t pa_off, offs;
    void *p;
    unsigned char *q;
    unsigned v0, v1, v2, v3;
    int i, allf = 1, allz = 1, nz = 0;

    pg = (unsigned)sysconf(_SC_PAGE_SIZE);
    p_(nm); p_("  addr=0x"); hx_(addr, 8); p_(" len=0x"); hx_(len, 4);
    p_("\n");

    if(memfd < 0){
        memfd = open("/dev/mem", O_RDONLY);
        if(memfd < 0){
            p_("  /dev/mem open FAILED: "); p_(strerror(errno)); pnl(); fl(); return;
        }
        p_("  /dev/mem opened RO\n");
    }

    /* ★ ge0rg liveview.c 的做法：物理地址可能不对齐，
     *   映射要从向下取整的页边界开始，访问时再加上页内偏移。 */
    pa_off = (off_t)(addr & ~(pg - 1));
    offs   = (off_t)(addr - (unsigned)pa_off);
    p_("  page_off=0x"); hx_((unsigned)offs, 4);

    /* ★ 只读映射，PROT_READ 一个字节都不多给 */
    p = mmap((void*)0, len + (unsigned)offs, PROT_READ, MAP_SHARED, memfd, pa_off);
    if(p == MAP_FAILED){
        p_("  mmap FAILED: "); p_(strerror(errno)); pnl(); fl(); return;
    }
    p_("  mmap OK -> base 0x"); hx_((unsigned)(unsigned long)p, 8);
    p_("  (+0x"); hx_((unsigned)offs, 4); p_(")\n"); fl();

    q = (unsigned char *)((char*)p + offs);
    v0 = ((unsigned*)q)[0];
    v1 = ((unsigned*)q)[1];
    v2 = ((unsigned*)q)[2];
    v3 = ((unsigned*)q)[3];
    p_("  [+0x00] 0x"); hx_(v0,8);
    p_("   [+0x04] 0x"); hx_(v1,8);
    p_("   [+0x08] 0x"); hx_(v2,8);
    p_("   [+0x0c] 0x"); hx_(v3,8); pnl();

    for(i=0; i<(int)(len/4) && i<256; i++){
        unsigned v = ((unsigned*)q)[i];
        if(v != 0xFFFFFFFFUL) allf = 0;
        if(v != 0x00000000UL) allz = 0;
        if(v != 0xFFFFFFFFUL && v != 0x00000000UL) nz++;
    }
    p_("  first256 words: nonZeroNonAllF="); de_(nz);
    p_("  allFF="); de_(allf); p_("  allZero="); de_(allz); pnl();

    /* ★★★ FULL=1 时逐 word 打印全部值（做差分采样用）—— epfull 扩展 */
    if(getenv("EPFULL")){
        int nw = (int)(len/4); if(nw > 1024) nw = 1024;
        p_("FULLDUMP\n");
        for(i=0; i<nw; i++){
            unsigned v = ((unsigned*)q)[i];
            p_("W"); hx_((unsigned)(offs + i*4), 4);
            p_("="); hx_(v, 8); pnl();
            if((i & 31) == 31) fl();     /* ★ 每32 行落盘，SIGBUS 不丢现场 */
        }
        fl();
    }

    munmap(p, len + (unsigned)offs);
    fl();
}

int main(int argc, char **argv)
{
    int i;
    p_("NX500 EP register read-only probe\n");
    p_("mmap PROT_READ only, no writes, no register config\n"); fl();

    if(argc > 1){
        for(i=1; i<argc; i++){
            unsigned a = (unsigned)strtoul(argv[i], 0, 16);
            try_one("arg", a, 0x1000);
        }
    } else {
        for(i=0; i<NT; i++)
            try_one(TBL[i].name, TBL[i].addr, TBL[i].len);
    }

    if(memfd >= 0) close(memfd);
    p_("\n===== done =====\n"); fl();
    return 0;
}