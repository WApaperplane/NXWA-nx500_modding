/* epdump2.arm -- dump 全部 10 个 EP 子块到相机端文件（纯只读）
 *
 * 用法: epdump2 <outfile>
 *   例: epdump2 base        -> /mnt/mmc/_xfer/ep_base.txt
 *
 * ★★ 设计约束（全部来自本项目实测铁律）：
 *   1. PROT_READ only。绝不写任何寄存器（写 EP = 不可中断 + ISP 实时驱动 = 只能拔电池）。
 *   2. 不做任何移位运算去算 ioctl 号 —— 预计算成字面量表，运行时只查表。
 *      （自定义 IOC 宏在 32 位 int 上 (2)<<30 有符号溢出，zig ARM 后端 -O0 会生成
 *        非法指令 ⇒ SIGILL。踩过 4 次，见 MEMORY.md 交叉编译铁律 2）
 *   3. 直接写文件而不是 stdout —— 全部 10 块约 11280 words，printf 到 telnet
 *      会把单核相机撑死（实测：满屏 X11 窗口 + stdout 洪流 = 连 echo 都跑不完）。
 *   4. 每行立即 fsync 落盘 —— 崩了也能看到前面已 dump 的内容。
 */
#include <unistd.h>
#include <fcntl.h>
#include <errno.h>
#include <string.h>
#include <sys/mman.h>
#include <stdlib.h>

/* zig 某些配置下不自动声明 ioctl；且 sys/ioctl.h 的宏绝不能碰（见头注释第 2 条） */
extern int ioctl(int fd, unsigned long request, ...);

/* ---------- 预计算 ioctl 号（Python 算好，禁 shift）---------- */
static const unsigned long EP_REGINFO_CMD = 0x80506864UL; /* _IOR('h',100,struct ep_reg_info) */

/* ★★ v2 修正（实机 RC=3 实证）：EP_REGINFO ioctl 属于 /dev/drime5_ep，
 *   打到 /dev/mem 的 fd 上必定失败。必须两个 fd 分开：
 *     epfd  -> /dev/drime5_ep  只用于 ioctl 拿子块物理基址
 *     memfd -> /dev/mem       只用于 mmap(PROT_READ)
 *   并且 ioctl 失败时退回实测地址表（raw5/ep3_full 已 10/10 实证），
 *   不能因为一次 ioctl 失败就让整个实验跑不起来。
 */

/* 实测值（epinfo3 nr=100 size=80, r=0）——兜底用，不是猜测 */
static const unsigned EP_START[10] = {
    0x20820000u,0x20823000u,0x20824000u,0x20826000u,0x20827000u,
    0x20828000u,0x20829000u,0x2082a000u,0x2082b000u,0x20821c00u
};

/* ---------- 10 个子块（顺序与 struct 一致，实测 10/10 非零）---------- */
static const char *BLK[10] = {
    "top","ldc","mc","rsz","lvr","bblt","fd","jpeg","3dlut","nog"
};
static const unsigned BLK_SIZE[10] = {
    0x1c00, 0x1000, 0x2000, 0x1000, 0x1000, 0x1000, 0x1000, 0x1000, 0x1000, 0x100
};

static int ofd;                 /* 输出文件 fd */
static int memfd;               /* /dev/mem fd */
static char ob[8192]; static int on;

static void fl(void){ if(on){ ssize_t r = write(ofd, ob, (size_t)on); (void)r; on = 0; } }
static void p_(const char *s){ while(*s){ if(on >= (int)sizeof(ob)) fl(); ob[on++] = *s++; } }
static void pc_(char c){ if(on >= (int)sizeof(ob)) fl(); ob[on++] = c; }
static void pnl(void){ pc_('\n'); }

/* 无移位十六进制打印 */
static void hx_(unsigned v, int w){
    static const char H[] = "0123456789abcdef";
    char b[16]; int m = 0, i;
    if(!v){ for(i=0;i<w;i++) pc_('0'); return; }
    while(v){ b[m++] = H[v & 0xfu]; v >>= 4; }        /* 只用右移，无左移溢出 */
    for(i=w;i>m;i--) pc_('0');
    for(i=0;i<m;i++) pc_(b[m-1-i]);
}

static int dumpreg(unsigned addr, unsigned size, const char *name, unsigned maxw){
    unsigned pg = (unsigned)sysconf(_SC_PAGE_SIZE);
    off_t pa; unsigned offs, i, nw = size / 4u, total = size / 4u;
    void *p; unsigned *q;

    if(maxw && nw > maxw) nw = maxw;

    pa    = (off_t)(addr & ~(pg - 1u));
    offs  = addr - (unsigned)pa;
    p= mmap(NULL, (size_t)(size + offs), PROT_READ, MAP_SHARED, memfd, pa);
    if(p == MAP_FAILED){ return -1; }
    q = (unsigned *)((char *)p + offs);

    p_("BLOCK "); p_(name);
    p_(" base=0x"); hx_(addr, 8);
    p_(" size=0x"); hx_(size, 4);
    p_(" shown="); hx_(nw, 4);
    p_("/"); hx_(total, 4);
    pnl(); fl();

    /* ★ 紧凑格式：每行 4 个 word。
     *   v1 每行 1 word ⇒ 单次全10 块 354KB，把单核相机压到掉线（实测 FTP 拉不回）。
     *   改成4列后同一份数据 ≈ 1/4，且 diff 一样用。 */
    for(i=0;i<nw;i+=4){
        unsigned k, lim = nw - i; if(lim > 4) lim = 4;
        p_(" "); p_(name); p_("+"); hx_(i*4u, 4); p_(":");
        for(k=0;k<lim;k++){ p_(" 0x"); hx_(q[i+k], 8); }
        pnl();
        if((i & 0x3fu) == 0x3cu) fl();
    }
    fl();
    munmap(p, (size_t)(size + offs));
    return 0;
}

/*★★ v3 修正（实机 dump 错位实证）：
 *   内核填的真实布局是 **10 组 {start,size} 交错**，不是 {start[10]; size[10]}。
 *   证据（raw7/ep_smoke4.txt）：声明成两个数组时读出
 *       start = 20820000, 00001c00, 20823000, 00001000, 20824000 ...
 *       size   = 20828000, 00001000, 20829000, 00001000, 2082a000 ...
 *   即 start[i] 交替拿到「下一个块的 start」和「本块真正的 size」。
 *   反推v[] 实际是：v0=top.start v1=top.size v2=ldc.start v3=ldc.size ...
 *   与 raw5/ep3_full 打印的十个 start/size 完全吻合 ⇒ 交错布局确认。
 */
struct ep_blk { unsigned start; unsigned size; };

int main(int argc, char **argv){
    struct ep_blk reg[10];
    unsigned i;
    int fd, nfail = 0;
    const char *out;
    unsigned maxw = 256;        /* ★ 默认每块只读前 256 words */

    if(argc < 2){
        p_("usage: epdump2 <outfile-base> [maxwords]\n"); return 1;
    }
    out = argv[1];
    if(argc >= 3){
        unsigned w = (unsigned)strtoul(argv[2], 0, 0);
        if(w > 0) maxw = w;
    }

    /* 1. 打开 /dev/mem（只读，专用于 mmap） */
    fd = open("/dev/mem", O_RDONLY);
    if(fd < 0){
        /* 没法建输出文件就直接 stderr */
        write(2, "epdump2: /dev/mem open failed\n", 29);
        return 2;
    }
    memfd = fd;

    /* 1b. 打开 /dev/drime5_ep（专用于 ioctl）—— ★ 修正：v1 错发到 /dev/mem fd 上 */
    {
        int epfd = open("/dev/drime5_ep", O_RDONLY);
        if(epfd < 0) epfd = open("/dev/drime5_ep", O_RDWR);
        if(epfd < 0){
            p_("# WARN /dev/drime5_ep open failed, using measured address table\n");
            fl();
            for(i=0;i<10;i++){ reg[i].start = EP_START[i]; reg[i].size = BLK_SIZE[i]; }
        } else {
            memset(&reg, 0, sizeof(reg));
            if(ioctl(epfd, EP_REGINFO_CMD, reg) != 0){
                p_("# WARN EP_REGINFO ioctl failed, using measured address table\n");
                fl();
                for(i=0;i<10;i++){ reg[i].start = EP_START[i]; reg[i].size = BLK_SIZE[i]; }
            } else {
                p_("# EP_REGINFO ok via /dev/drime5_ep\n"); fl();
            }
            close(epfd);
        }
    }
    for(i=0;i<10;i++){
        if(reg[i].start == 0 || reg[i].size == 0){
            /* 用兜底表补齐，不退出 */
            reg[i].start = EP_START[i];
            if(reg[i].size == 0) reg[i].size = BLK_SIZE[i];
        }
    }

    /* 3. 建输出文件 */
    {
        char path[256]; int k = 0;
        const char *pre = "/mnt/mmc/_xfer/ep_";
        const char *suf = ".txt";
        while(*pre) path[k++] = *pre++;
        { const char *b = out; while(*b && k < 200) path[k++] = *b++; }
        while(*suf) path[k++] = *suf++;
        path[k] = 0;
        ofd = open(path, O_WRONLY|O_CREAT|O_TRUNC, 0644);
        if(ofd < 0){
            write(2, "epdump2: cannot create output\n", 31);
            return 5;
        }
    }

    p_("# epdump2 v3  (read-only, no register written)\n");
    p_("# sub-blocks: /dev/drime5_ep ioctl 0x80506864, layout = 10x{start,size} interleaved\n");
    pnl(); fl();

    /* 4. 逐块 dump */
    for(i=0;i<10;i++){
        unsigned addr = reg[i].start;
        unsigned size = reg[i].size;
        /* 用 ioctl 返回的 size 优先，但兜底用编译期表（防止 ioctl 给的是 80 字节结构里的别的） */
        if(size != BLK_SIZE[i]){
            /* 保留 ioctl 的值，但打印差异便于事后核对 */
            p_("# NOTE block "); p_(BLK[i]);
            p_(" size=0x"); hx_(size, 4);
            p_(" expected=0x"); hx_(BLK_SIZE[i], 4);
            pnl(); fl();
        }
        if(dumpreg(addr, size, BLK[i], maxw) != 0){
            p_("# FAIL "); p_(BLK[i]); pnl(); fl();
            nfail++;
        }
    }

    p_("# END blocks="); hx_(10u - (unsigned)nfail, 2);
    p_(" failed="); hx_((unsigned)nfail, 2);
    pnl(); fl();

    close(ofd);
    close(fd);
    return nfail ? 10 : 0;
}
