/* epdump7.arm -- dump 全部 10 个 EP 子块（只读，原始二进制）
 *
 * 用法: epdump7 <outfile-base>
 *   → /mnt/mmc/_xfer/ep_<base>.bin
 *
 * ★★★ v7 修正了两个致命 bug（都是本项目记忆里"自己造的新坑"）★★★
 *
 * 【bug 1】EP_REGINFO 的结构是【交错】的，不是分离的：
 *     真实布局  struct { unsigned start, size; } blk[10];
 *               即 v[0]=blk0.start v[1]=blk0.size v[2]=blk1.start ...
 *     我写成 struct { unsigned start[10]; unsigned size[10]; }
 *     ⇒ size[0] 实际读到的是 v[10] = blk5.start = 0x20828000
 *     ⇒ 块0 去 mmap 0x20828000 字节 ⇒ 崩。
 *     证据：epdump6 打印 size=0x20828000，恰是 epinfo3 表里块5 的 start。
 *     正确表见 raw5/ep3_full（epinfo3 用 v[i*2]/v[i*2+1] 打印，10/10 正确）。
 *
 * 【bug 2】v2 把 11072 个寄存器格式化成 324KB 文本写 SD 卡 ⇒ 单核相机卡死，
 *     只能拔电池。v3+ 改为纯二进制 44KB 一次落盘，格式化全部放 PC 端。
 *
 * 【bug 3】v3/v4 把 80 字节的 ioctl 结构写进 40 字节的 hs[10] ⇒ 越界踩栈 ⇒ SIGSEGV。
 *
 * ★ 安全边界：PROT_READ only，绝不写任何 EP 寄存器（写 EP = 不可中断 + ISP 实时驱动）。
 * ★ 实测 ioctl：nr=100 size=80 → r=0，10/10 非零。size=44/40/72 也 r=0 但只填部分字段，不可信。
 */
#include <unistd.h>
#include <fcntl.h>
#include <string.h>
#include <sys/mman.h>
#include <stdlib.h>

extern int ioctl(int fd, unsigned long request, ...);

static const unsigned long EP_REGINFO_CMD = 0x80506864UL;

/* 实测值（raw5/ep3_full，epinfo3 v[i*2]/v[i*2+1]，10/10 非零）—— 兜底表 */
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

static const unsigned MAGIC = 0x45503737u;   /* '77PE' */
static const unsigned VER   = 7u;

static int ofd;
static int memfd = -1;
static unsigned char buf[4096];

static int w4(unsigned v)
{
    unsigned char b[4];
    b[0]=(unsigned char)(v&0xffu);       b[1]=(unsigned char)((v>>8)&0xffu);
    b[2]=(unsigned char)((v>>16)&0xffu); b[3]=(unsigned char)((v>>24)&0xffu);
    if(write(ofd, b, 4) != 4) return -1;
    return 0;
}

static int dumpblk(unsigned addr, unsigned size)
{
    unsigned pg = (unsigned)sysconf(_SC_PAGE_SIZE);
    unsigned page = addr & ~(pg - 1u);
    unsigned offs = addr - page;
    unsigned done = 0u, n;
    void *p;
    unsigned char *base;

    p = mmap((void*)0, (size_t)size + (size_t)offs, PROT_READ, MAP_SHARED,
             memfd, (off_t)page);
    if(p == MAP_FAILED) return -1;
    base = (unsigned char *)p;
    base = base + offs;

    while(done < size){
        n = size - done;
        if(n > (unsigned)sizeof(buf)) n = (unsigned)sizeof(buf);
        memcpy(buf, base + done, n);
        if(write(ofd, buf, n) != (int)n){ (void)munmap(p,(size_t)size+(size_t)offs); return -2; }
        done = done + n;
    }
    (void)munmap(p, (size_t)size + (size_t)offs);
    return 0;
}

int main(int argc, char **argv)
{
    /* ★ 交错的 80 字节结构：start,size,start,size,... 共 10 对 */
    unsigned raw[20];
    unsigned hs[10], hz[10];
    unsigned i, nfail;
    int epfd, k;

    if(argc < 2){ (void)write(2, "usage: epdump7 <base>\n", 24); return 1; }

    {
        char path[256];
        const char *pre = "/mnt/mmc/_xfer/ep_";
        k = 0;
        while(*pre) path[k++] = *pre++;
        { const char *b = argv[1]; while(*b && k < 240) path[k++] = *b++; }
        { const char *s = ".bin"; while(*s) path[k++] = *s++; }
        path[k] = 0;
        ofd = open(path, O_WRONLY|O_CREAT|O_TRUNC, 0644);
        if(ofd < 0){ (void)write(2, "epdump7: cannot create\n", 25); return 2; }
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
    /* ★ 交化解包：raw[2i]=start, raw[2i+1]=size */
    for(i=0;i<10;i++){
        hs[i] = raw[2*i];
        hz[i] = raw[2*i+1];
        if(hs[i]==0u || hz[i]==0u){ hs[i]=EP_START[i]; hz[i]=BLK_SIZE[i]; }
    }

    /* header: magic,ver,nblk, then name-offset table, start[10], size[10] */
    if(w4(MAGIC)!=0) return 4;
    if(w4(VER)!=0)   return 4;
    if(w4(10u)!=0)   return 4;
    for(i=0;i<10;i++) if(w4(hs[i])!=0) return 4;
    for(i=0;i<10;i++) if(w4(hz[i])!=0) return 4;

    nfail = 0u;
    for(i=0;i<10;i++){
        int r = dumpblk(hs[i], hz[i]);
        if(r != 0){
            nfail = nfail + 1u;
            (void)w4(0xDEAD0000u | i);      /* 该块失败标记 */
        }
        (void)w4(0xA5A50000u | i);          /* 进度标记 */
    }
    (void)w4(0x600D0000u | nfail);
    (void)close(ofd);
    (void)close(memfd);
    (void)write(1, "DONE\n", 5);
    return (int)nfail;
}