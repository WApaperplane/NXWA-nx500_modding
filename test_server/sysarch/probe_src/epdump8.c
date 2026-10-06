/* epdump8.arm -- dump 全部 10 个 EP 子块（只读），★改用 pread 规避 SIGBUS★
 *
 * 用法: epdump8 <outfile-base>
 *   → /mnt/mmc/_xfer/ep_<base>.bin
 *
 * ★★★★★ 为什么放弃 mmap 改用 pread（本轮最大的坑）★★★★★
 *   1. mmap(PROT_READ) 映射设备寄存器区后**第一次触碰就可能 SIGBUS(信号7)**，
 *      内核直接杀进程，栈都来不及留。epdump6 实测：块0(0x20820000) 读第一
 *      个 word 就 signal=7，而 19:11 的 epreg 读同一地址前 1024B 是成功的
 *      ⇒ 不是"这段地址永远不可读"，是"可读性随时会消失"（ISP 状态/电源域）。
 *      ⇒ 凡是"能跑通一次"的地址都不能信，必须每次优雅降级。
 *   2. pread() 读 /dev/mem：不可读返回 -EIO，进程照常活，可记录并跳过。
 *      对本项目（判据工具必须自己有判据、失败要可解释）这是唯一正确选择。
 *
 * ★★★ 三个已定位的历史 bug（都在本文件里已修，别再犯）★★★
 *   bug1: EP_REGINFO(0x80506864, 80B) 结构是【交错】的：
 *         raw[2i]=blk_i.start, raw[2i+1]=blk_i.size
 *         写成 start[10]+size[10] ⇒ size[0] 拿到的是 blk5.start=0x20828000
 *   bug2: 逐 word 格式化成 324KB 文本写 SD 卡 ⇒ 单核相机卡死，只能拔电池
 *         ⇒ 纯二进制 44KB 一次落盘，格式化放 PC 端
 *   bug3: 把 80 字节 ioctl 结构写进 40 字节的 hs[10] ⇒ 越界踩栈 ⇒ SIGSEGV
 *
 * ★ 安全边界：只读。绝不写任何 EP 寄存器（写 EP = 不可中断 + ISP 实时驱动 = 拔电池）。
 */
#include <unistd.h>
#include <fcntl.h>
#include <errno.h>
#include <string.h>
#include <stdlib.h>

extern int ioctl(int fd, unsigned long request, ...);

static const unsigned long EP_REGINFO_CMD = 0x80506864UL;

/* 实测值（raw5/ep3_full，epinfo3 按 v[i*2]/v[i*2+1] 打印，10/10 非零）—— 兜底表 */
static const unsigned EP_START[10] = {
    0x20820000u,0x20823000u,0x20824000u,0x20826000u,0x20827000u,
    0x20828000u,0x20829000u,0x2082a000u,0x2082b000u,0x20821c00u
};
static const unsigned BLK_SIZE[10] = {
    0x1c00,0x1000,0x2000,0x1000,0x1000,0x1000,0x1000,0x1000,0x1000,0x100
};
static const char *BLK_NAME[10] = {
    "top","ldc","mc","rsz","lvr","bblt","fd","jpeg","3dlut","nog"
};

static const unsigned MAGIC = 0x45503838u;   /* '88PE' */
static const unsigned VER   = 8u;

static int ofd;
static int memfd = -1;
static unsigned char buf[1024];

/* 32 位 off_t：/dev/mem 偏移 0x20820000 在 32 位下不溢出，但显式用 int */
static int w4(unsigned v)
{
    unsigned char b[4];
    b[0]=(unsigned char)(v&0xffu);       b[1]=(unsigned char)((v>>8)&0xffu);
    b[2]=(unsigned char)((v>>16)&0xffu); b[3]=(unsigned char)((v>>24)&0xffu);
    if(write(ofd, b, 4) != 4) return -1;
    return 0;
}

/* 读一个块：成功返回 0，部分/失败返回负数（已把能读的写进 ofd 并填了 0） */
static int readblk(unsigned addr, unsigned size)
{
    unsigned done = 0u, n;
    int r;

    while(done < size){
        n = size - done;
        if(n > (unsigned)sizeof(buf)) n = (unsigned)sizeof(buf);
        /* ★ pread 而不是 mmap：失败只返回负 errno，不杀进程 */
        r = (int)pread(memfd, buf, n, (off_t)(addr + done));
        if(r <= 0){
            /* 读不动了：把剩余部分填 0，保证文件结构完整、PC 端可判读 */
            unsigned left = size - done;
            memset(buf, 0, sizeof(buf));
            while(left){
                n = left > (unsigned)sizeof(buf) ? (unsigned)sizeof(buf) : left;
                if(write(ofd, buf, n) != (int)n) return -3;
                left -= n;
            }
            return (r == 0) ? -1 : -2;   /* -1=EOF 读到头 -2=errno */
        }
        if(write(ofd, buf, r) != r) return -3;
        done = done + (unsigned)r;
    }
    return 0;
}

int main(int argc, char **argv)
{
    unsigned raw[20];
    unsigned hs[10], hz[10];
    unsigned i, nfail;
    int epfd, k;

    if(argc < 2){ (void)write(2, "usage: epdump8 <base>\n", 24); return 1; }

    {
        char path[256];
        const char *pre = "/mnt/mmc/_xfer/ep_";
        k = 0;
        while(*pre) path[k++] = *pre++;
        { const char *b = argv[1]; while(*b && k < 240) path[k++] = *b++; }
        { const char *s = ".bin"; while(*s) path[k++] = *s++; }
        path[k] = 0;
        ofd = open(path, O_WRONLY|O_CREAT|O_TRUNC, 0644);
        if(ofd < 0){ (void)write(2, "epdump8: cannot create\n", 25); return 2; }
    }

    memfd = open("/dev/mem", O_RDONLY);
    if(memfd < 0){ (void)w4(0xDEAD0001u); (void)close(ofd); return 3; }

    epfd = open("/dev/drime5_ep", O_RDONLY);
    if(epfd < 0) epfd = open("/dev/drime5_ep", O_RDWR);
    memset(raw, 0, sizeof(raw));
    if(epfd >= 0){
        if(ioctl(epfd, EP_REGINFO_CMD, raw) != 0) memset(raw, 0, sizeof(raw));
        (void)close(epfd);
    }
    /* ★ 交化解包 */
    for(i=0;i<10;i++){
        hs[i] = raw[2*i];
        hz[i] = raw[2*i+1];
        if(hs[i]==0u || hz[i]==0u){ hs[i]=EP_START[i]; hz[i]=BLK_SIZE[i]; }
    }

    /* header: magic,ver,nblk,total,then start[10],size[10] */
    { unsigned tot = 0u; for(i=0;i<10;i++) tot += hz[i];
      if(w4(MAGIC)!=0)  return 4;
      if(w4(VER)!=0)    return 4;
      if(w4(10u)!=0)    return 4;
      if(w4(tot)!=0)    return 4; }
    for(i=0;i<10;i++) if(w4(hs[i])!=0) return 4;
    for(i=0;i<10;i++) if(w4(hz[i])!=0) return 4;

    nfail = 0u;
    for(i=0;i<10;i++){
        int r = readblk(hs[i], hz[i]);
        if(r != 0){
            nfail = nfail + 1u;
            (void)w4(0xDEAD0000u | (unsigned)(-r));   /* 该块失败 + 原因 */
        }
        (void)w4(0xA5A50000u | i);                    /* 进度标记 */
    }
    (void)w4(0x600D0000u | nfail);
    (void)close(ofd);
    (void)close(memfd);
    (void)write(1, "DONE\n", 5);
    return (int)nfail;
}