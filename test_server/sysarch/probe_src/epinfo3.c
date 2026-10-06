/*
 * epinfo3.arm -- NX500 EP / SMA / IPCC 只读探针（v3最终版）
 *
 *★★★ 本文件记录了 v1/v2 在真机上的三次崩溃与最终解法，勿删★★★
 *
 * 【崩溃档案】
 *  v1（用 printf + #include <sys/ioctl.h> + IOC 宏）
 *     → CA9 user fault signal=4(SIGILL)，每次都死在第一次 ioctl 处。
 *  v2（改用 write 自格式化，仍用 IOC 宏）
 *     → 同样 SIGILL。已排除：printf、stdio 缓冲、栈溢出、
 *       ioctl 派发路径本身、/dev/null 与 /dev/d5_sma 的区别。
 *  t3/t4（连完全虚构的 IOR('Z',77,4) 都 SIGILL，连内联 syscall 也 SIGILL）
 *     → 说明根本还没进内核。
 *  t9（★决定性★）崩溃点在 main+0x84，即【打印 ioctl 编码那段】，
 *     根本还没执行到 ioctl()。
 *
 * 【真凶】
 *  #define IOC(d,t,nr,sz) (((d)<<30)|((sz)<<16)|((t)<<8)|(nr))
 *  在 32 位 int 上 (2)<<30 = 0x80000000 是【有符号溢出】，
 *  zig 0.13 ARM 后端在 -O0 下为这条路径生成了非法指令 → SIGILL。
 *  t6/t8 用字面量 0x80506800UL 不做移位 ⇒ 全程正常。
 *
 * 【解法】EP/SMA/IPCC/LOCK 的所有 ioctl 号用 Python 预计算成字面量常量表，
 *        运行时只查表，不做任何移位。
 *
 * 【安全边界】只调查询型 ioctl。绝不调：
 *   SMA_ALLOC(5) / SMA_FREE(6,7) / SMA_CACHE_FLUSH(9) / SMA_CONTROL_PREBUFFER(10)
 *   IPCC_WRITE_PKT(7) / IPCC_READ_PKT(6) / IPCC_RESET(0) / IPCC_INIT(1)
 *   EP_IOCTL_UDD_LOCK(40) / EP_IOCTL_UDD_UNLOCK(41) / EP_IOCTL_SET_CLK_RATE(50)
 *   MPTOP_CM4_START/STOP / st firmware up
 * 另：不 mmap、不访问寄存器、不写文件。纯打印。
 *
 * 用法: epinfo3 [normal|nrscan|ep|sma|ipcc]
 */

#include <unistd.h>
#include <fcntl.h>
#include <errno.h>
#include <string.h>
#include <sys/ioctl.h>

/* ============ 预计算 ioctl 号（Python 生成，勿手改） ============ */
static const unsigned long EP_CMD[128] = {
    0, 0x80506801UL,0x80506802UL,0x80506803UL,0x80506804UL,0x80506805UL,0x80506806UL,0x80506807UL,
    0x80506808UL,0x80506809UL,0x8050680aUL,0x8050680bUL,0x8050680cUL,0x8050680dUL,0x8050680eUL,0x8050680fUL,
    0x80506810UL,0x80506811UL,0x80506812UL,0x80506813UL,0x80506814UL,0x80506815UL,0x80506816UL,0x80506817UL,
    0x80506818UL,0x80506819UL,0x8050681aUL,0x8050681bUL,0x8050681cUL,0x8050681dUL,0x8050681eUL,0x8050681fUL,
    0x80506820UL,0x80506821UL,0x80506822UL,0x80506823UL,0x80506824UL,0x80506825UL,0x80506826UL,0x80506827UL,
    0x80506828UL,0x80506829UL,0x8050682aUL,0x8050682bUL,0x8050682cUL,0x8050682dUL,0x8050682eUL,0x8050682fUL,
    0x80506830UL,0x80506831UL,0x80506832UL,0x80506833UL,0x80506834UL,0x80506835UL,0x80506836UL,0x80506837UL,
    0x80506838UL,0x80506839UL,0x8050683aUL,0x8050683bUL,0x8050683cUL,0x8050683dUL,0x8050683eUL,0x8050683fUL,
    0x80506840UL,0x80506841UL,0x80506842UL,0x80506843UL,0x80506844UL,0x80506845UL,0x80506846UL,0x80506847UL,
    0x80506848UL,0x80506849UL,0x8050684aUL,0x8050684bUL,0x8050684cUL,0x8050684dUL,0x8050684eUL,0x8050684fUL,
    0x80506850UL,0x80506851UL,0x80506852UL,0x80506853UL,0x80506854UL,0x80506855UL,0x80506856UL,0x80506857UL,
    0x80506858UL,0x80506859UL,0x8050685aUL,0x8050685bUL,0x8050685cUL,0x8050685dUL,0x8050685eUL,0x8050685fUL,
    0x80506860UL,0x80506861UL,0x80506862UL,0x80506863UL,0x80506864UL,0x80506865UL,0x80506866UL,0x80506867UL,
    0x80506868UL,0x80506869UL,0x8050686aUL,0x8050686bUL,0x8050686cUL,0x8050686dUL,0x8050686eUL,0x8050686fUL,
    0x80506870UL,0x80506871UL,0x80506872UL,0x80506873UL,0x80506874UL,0x80506875UL,0x80506876UL,0x80506877UL,
    0x80506878UL,0x80506879UL,0x8050687aUL,0x8050687bUL,0x8050687cUL,0x8050687dUL,0x8050687eUL,0x8050687fUL
};
/* EP 同 magic 但不同 size：40 / 72 / 44（判断NX500 结构体大小是否与 NX1 一致） */
static const unsigned long EP_CMD_S40 = 0x80286864UL;
static const unsigned long EP_CMD_S72 = 0x80486864UL;
static const unsigned long EP_CMD_S44 = 0x802c6864UL;

/* SMA _IOR('s',nr,4) */
static const unsigned long SMA_R[16] = {
    0, 0x80047301UL,0x80047302UL,0x80047303UL,0x80047304UL,
    0x80047305UL,0x80047306UL,0x80047307UL,0x80047308UL,
    0x80047309UL,0x8004730aUL,0x8004730bUL,0x8004730cUL,0x8004730dUL,0x8004730eUL,0x8004730fUL
};
/*★★ 实测结论（2026-10-05，NX500 真机）★★
 *   _IOWR('t',nr,8)  （size=8，即 NX1 头文件 struct ipcc_available_info 的 8 字节）
 *       -> nr=3/4/5 一进 ioctl 就 SIGILL 打死进程。
 *   _IOWR('t',nr,4)  （size=4）
 *       -> nr=2/3/4/5 全部安全返回 r=0，且内核【完全不写缓冲】（保持 0xAA）。
 *   => NX500 的 IPCC ioctl 只接受 size=4 的编码；size=8 走错误分支直接死。
 *      而且即便 size=4，内核也不回填任何数值 => 这些查询接口在 NX500 上是空壳。
 *      跨核数据面仍然只走 EP（drime5_ep 中断 1490995 次）+ SMA 共享内存。
 */
/* IPCC _IOWR('t',nr,4)  安全版 */
static const unsigned long IPCC_W4[20] = {
    0xc0047400UL,0xc0047401UL,0xc0047402UL,0xc0047403UL,0xc0047404UL,
    0xc0047405UL,0xc0047406UL,0xc0047407UL,0xc0047408UL,0xc0047409UL,
    0xc004740aUL,0xc004740bUL,0xc004740cUL,0xc004740dUL,0xc004740eUL,
    0xc004740fUL,0xc0047410UL,0xc0047411UL,0xc0047412UL,0xc0047413UL
};

/* ============ 无 shift 的输出工具 ============ */
static int oton;
static char obuf[8192];
static void fl(void){ if(oton){ write(1,obuf,oton); oton=0; } }
static void p_(const char *s){ while(*s){ if(oton>=(int)sizeof(obuf))fl(); obuf[oton++]=*s++; } }
static void pc(char c){ if(oton>=(int)sizeof(obuf))fl(); obuf[oton++]=c; }
static void pnl(void){ pc('\n'); }
static void pdec(int v){
    char b[16]; int m=0,i; unsigned u;
    if(v<0){ pc('-'); u=(unsigned)(-v); } else u=(unsigned)v;
    if(u==0){ pc('0'); return; }
    while(u){ b[m++]=(char)('0'+u%10); u/=10; }
    for(i=m;i>0;i--) pc(b[i-1]);
}
/* 十六进制：只用除法，无移位 */
static void phx(unsigned v,int w){
    static const char H[]="0123456789abcdef";
    char b[16]; int m=0,i;
    if(v==0){ for(i=0;i<w;i++) pc('0'); return; }
    while(v){ b[m++]=H[v%16u]; v/=16u; }
    for(i=w;i>m;i--) pc('0');
    for(i=m;i>0;i--) pc(b[i-1]);
}
static void pphys(const char*nm,unsigned st,unsigned sz){
    p_("  "); p_(nm); p_(" : start=0x"); phx(st,8);
    p_("  size=0x"); phx(sz,8); p_("  ("); pdec((int)sz); p_(")\n");
}

static const char *EPN[10]={
    "top","ldc","mc","rsz","lvr","bblt","fd","jpeg","3DLUT","NOG"
};

struct ai { int core_id; int ret; };

static void res(const char *tag, unsigned long cmd, int r){
    p_("  "); if(*tag) p_(tag);
    p_(" cmd=0x"); phx((unsigned)cmd,8);
    p_(" r="); pdec(r);
    if(r<0){ p_(" errno="); pdec(errno); p_(" ("); p_(strerror(errno)); p_(")"); }
    pnl();
}

static void probe_ep(int nrscan)
{
    int fd, i, nr;
    p_("open /dev/drime5_ep\n"); fl();
    fd = open("/dev/drime5_ep", O_RDWR);
    if(fd<0){ fd=open("/dev/drime5_ep", O_RDONLY); p_("  O_RDWR failed -> O_RDONLY\n"); }
    if(fd<0){ p_("  FAILED: "); p_(strerror(errno)); pnl(); fl(); return; }
    p_("  fd="); pdec(fd); pnl(); fl();

    if(nrscan){
        int hits=0;
        p_("--- nr scan: magic='h' size=80, nr=1..127 ---\n"); fl();
        for(nr=1;nr<128;nr++){
            unsigned char buf[80];
            int r;
            memset(buf,0,80);
            r = ioctl(fd, EP_CMD[nr], buf);
            if(r==0){
                p_("  nr="); pdec(nr); p_(" OK  u32[0..19]:");
                for(i=0;i<20;i++){ pc(' '); phx(((unsigned*)buf)[i],8); }
                pnl(); hits++; fl();
            }
        }
        p_("  hits="); pdec(hits); pnl(); fl();
        close(fd); return;
    }

    {
        unsigned char buf[80];
        unsigned long cmds[3];
        const char *tag[3];
        int k;
        cmds[0]=EP_CMD[100]; tag[0]="EP nr=100 size=80 (NX1 spec)";
        cmds[1]=EP_CMD_S44;  tag[1]="EP nr=100 size=44";
        cmds[2]=EP_CMD_S40;  tag[2]="EP nr=100 size=40";
        for(k=0;k<3;k++){
            int r;
            memset(buf,0,80);
            r = ioctl(fd, cmds[k], buf);
            res(tag[k], cmds[k], r);
            if(r==0 && k==0){
                unsigned *v = (unsigned*)buf;
                int nz=0;
                p_("  --- 10 sub-blocks ---\n");
                for(i=0;i<10;i++){ pphys(EPN[i], v[i*2], v[i*2+1]); if(v[i*2]||v[i*2+1]) nz++; }
                p_("  non-zero: "); pdec(nz); p_("/10\n");
            }
            fl();
        }
        cmds[0]=EP_CMD_S72;
        memset(buf,0,80);
        res("EP nr=100 size=72", cmds[0], ioctl(fd, cmds[0], buf));
        fl();
    }
    close(fd); fl();
}

static void probe_sma(void)
{
    int fd; unsigned int v; int r;
    p_("open /dev/d5_sma\n"); fl();
    fd = open("/dev/d5_sma", O_RDWR);
    if(fd<0) fd=open("/dev/d5_sma", O_RDONLY);
    if(fd<0){ p_("  FAILED: "); p_(strerror(errno)); pnl(); fl(); return; }
    p_("  fd="); pdec(fd); pnl();

    v=0; r=ioctl(fd,SMA_R[1],&v);
    p_("  SMA_GET_REGION_SIZE       "); res("",SMA_R[1],r);
    p_("      -> 0x"); phx(v,8); p_("  ("); pdec((int)v); p_(")\n"); fl();

    v=0; r=ioctl(fd,SMA_R[4],&v);
    p_("  SMA_GET_REGION_START_ADDR "); res("",SMA_R[4],r);
    p_("      -> 0x"); phx(v,8); pnl(); fl();

    v=0; r=ioctl(fd,SMA_R[8],&v);
    p_("  SMA_GET_ALLOCATED_SIZE    "); res("",SMA_R[8],r);
    p_("      -> 0x"); phx(v,8); p_("  ("); pdec((int)v); p_(")\n"); fl();

    p_("  SMA_VIRT_TO_PHYS(2) / ALLOC(5) : SKIPPED (IOWR, 有副作用)\n");
    close(fd); fl();
}

static void probe_ipcc(void)
{
    int fd, cid, nr;
    p_("open /dev/d5_ipcc\n"); fl();
    fd = open("/dev/d5_ipcc", O_RDWR);
    if(fd<0) fd=open("/dev/d5_ipcc", O_RDONLY);
    if(fd<0){ p_("  FAILED: "); p_(strerror(errno)); pnl(); fl(); return; }
    p_("  fd="); pdec(fd); pnl(); fl();

    /* 只用 size=4 的安全编码。传 int 缓冲，填 0xA5A5A5A5，
     * 看内核到底回填哪个字段。*/
    p_("  cmds(sz4): W=0x"); phx((unsigned)IPCC_W4[3],8);
    p_(" R=0x"); phx((unsigned)IPCC_W4[4],8);
    p_(" L=0x"); phx((unsigned)IPCC_W4[5],8); pnl(); fl();

    for(nr=3; nr<=5; nr++){
        for(cid=0; cid<8; cid++){
            int buf[4];
            int r, i, chg=0;
            for(i=0;i<4;i++) buf[i]=(int)0xA5A5A5A5;
            buf[0]=cid;
            r = ioctl(fd, IPCC_W4[nr], buf);
            for(i=0;i<4;i++) if(buf[i]!=(int)0xA5A5A5A5) chg=1;
            p_("  nr="); pdec(nr); p_(" core="); pdec(cid);
            p_(" r="); pdec(r);
            if(r<0){ p_(" ("); p_(strerror(errno)); p_(")"); }
            p_(" ret="); pdec(buf[1]);
            p_("  buf[0..3]=");
            for(i=0;i<4;i++){ pc(' '); phx((unsigned)buf[i],8); }
            p_(chg?"  CHANGED":"  untouched");
            pnl(); fl();
        }
    }
    close(fd); fl();
}

int main(int argc, char **argv)
{
    const char *m = (argc>1)?argv[1]:"normal";
    int d_ep=1,d_sma=1,d_ip=1;
    if(!strcmp(m,"nrscan")){ d_sma=0; d_ip=0; }
    else if(!strcmp(m,"sma")){ d_ep=0; d_ip=0; }
    else if(!strcmp(m,"ipcc")){ d_ep=0; d_sma=0; }
    else if(!strcmp(m,"ep")){ d_sma=0; d_ip=0; }

    p_("NX500 EP/SMA/IPCC read-only probe v3 (precomputed ioctl consts)\n");
    p_("mode="); p_(m); pnl();
    p_("EP magic='h' nr=100 | SMA magic='s' | IPCC magic='t'\n"); fl();

    if(d_ep){ p_("\n===== 1. EP  /dev/drime5_ep=====\n");  probe_ep(!strcmp(m,"nrscan")); }
    if(d_sma){p_("\n===== 2. SMA /dev/d5_sma =====\n");    probe_sma(); }
    if(d_ip){ p_("\n===== 3. IPCC /dev/d5_ipcc=====\n");   probe_ipcc(); }
    p_("\n===== done =====\n"); fl();
    return 0;
}