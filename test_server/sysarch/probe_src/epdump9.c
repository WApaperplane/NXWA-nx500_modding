/* epdump9.arm -- dump 全部 10 个 EP 子块（只读）★★逐页 mmap，规避 SIGBUS★★
 *
 * 用法: epdump9 <outfile-base>
 *   → /mnt/mmc/_xfer/ep_<base>.bin
 *
 * ★★★★★ 三种访问方式的实测结论（本轮踩了 6 个版本才收敛）★★★★★
 *
 *  (A) mmap 整块（0x1c00 / 0x2000 一次映射）  → SIGBUS(信号7) 杀进程
 *      epdump6 实测：块0 第一个 word 就 signal=7。内核在设备寄存器区
 *      mmap 出来的页不具备普通读写语义，触碰即 bus error。
 *  (B) pread(/dev/mem)                        → 一律 -EIO，10/10 块全失败
 *      epdump8 实测：RC=10，每块 dead0002。内核 3.5 的 /dev/mem 走
 *      `mmap` 语义下的 direct_poke/read，pread 这条路对设备区无效。
 *  (C) mmap 4096 (一页) + memcpy               → epreg 当年成功
 *      raw5/epreg_all 实测：top/mc/3dlut/jpeg 都读到非零非FF 数据。
 *      ⇒ 唯一可行姿势：**按页映射，读完立刻 munmap，绝不跨越页边界 memcpy**。
 *
 * ★ 对每页单独 try：某页 SIGBUS 就没法优雅降级（SIGBUS 不可屏蔽），
 *   所以做法是"先探测该页可读性，再决定要不要 dump"—— 用 sigsetjmp
 *   捕获 SIGBUS 是不行的（内核直接杀线程）。
 *   实际策略：每页先 read 1 字节做探针(单独进程由 shell 分段执行)，
 *   探针失败就不 dump 该页。这里本程序一次性 dump，探针在 PC 端做。
 *
 *   → 实际实现：mmap 一页 → memcpy → munmap，逐页推进。
 *     若某页触发 SIGBUS，本进程死；由 PC 端检测到"文件长度不足"后
 *     重跑并跳过该页（记录黑名单）。这样单次最多损失一个页。
 *
 * ★ 安全边界：PROT_READ only。绝不写任何 EP 寄存器。
 */
#include <unistd.h>
#include <fcntl.h>
#include <errno.h>
#include <string.h>
#include <sys/mman.h>
#include <stdlib.h>

extern int ioctl(int fd, unsigned long request, ...);

static const unsigned long EP_REGINFO_CMD = 0x80506864UL;

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

static const unsigned MAGIC = 0x45503939u;   /* '99PE' */
static const unsigned VER   = 9u;

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

/* 只读一页（4096）并 memcpy 出；返回 0 成功，-1 mmap 失败 */
static int readpage(unsigned page, unsigned char *dst)
{
    void *p = mmap((void*)0, 4096u, PROT_READ, MAP_SHARED, memfd, (off_t)page);
    if(p == MAP_FAILED) return -1;
    memcpy(dst, (unsigned char *)p, 4096u);
    (void)munmap(p, 4096u);
    return 0;
}

int main(int argc, char **argv)
{
    unsigned raw[20];
    unsigned hs[10], hz[10];
    unsigned i, nfail, tot;
    int epfd, k;

    if(argc < 2){ (void)write(2, "usage: epdump9 <base>\n", 24); return 1; }

    {
        char path[256];
        const char *pre = "/mnt/mmc/_xfer/ep_";
        k = 0;
        while(*pre) path[k++] = *pre++;
        { const char *b = argv[1]; while(*b && k < 240) path[k++] = *b++; }
        { const char *s = ".bin"; while(*s) path[k++] = *s++; }
        path[k] = 0;
        ofd = open(path, O_WRONLY|O_CREAT|O_TRUNC, 0644);
        if(ofd < 0){ (void)write(2, "epdump9: cannot create\n", 25); return 2; }
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
    for(i=0;i<10;i++){
        hs[i] = raw[2*i];
        hz[i] = raw[2*i+1];
        if(hs[i]==0u || hz[i]==0u){ hs[i]=EP_START[i]; hz[i]=BLK_SIZE[i]; }
    }

    tot = 0u; for(i=0;i<10;i++) tot += hz[i];
    if(w4(MAGIC)!=0) return 4;
    if(w4(VER)!=0)   return 4;
    if(w4(10u)!=0)   return 4;
    if(w4(tot)!=0)   return 4;
    for(i=0;i<10;i++) if(w4(hs[i])!=0) return 4;
    for(i=0;i<10;i++) if(w4(hz[i])!=0) return 4;

    nfail = 0u;
    for(i=0;i<10;i++){
        unsigned addr = hs[i], size = hz[i];
        unsigned done = 0u;
        while(done < size){
            unsigned page = (addr + done) & ~4095u;
            unsigned off  = (addr + done) - page;
            unsigned n    = 4096u - off;
            if(n > size - done) n = size - done;
            if(readpage(page, buf) != 0){
                /* 该页 mmap 失败：填 0 占位，文件保持完整 */
                unsigned left = size - done;
                memset(buf, 0, sizeof(buf));
                while(left){
                    unsigned m = left > sizeof(buf) ? (unsigned)sizeof(buf) : left;
                    if(write(ofd, buf, m) != (int)m) return 5;
                    left -= m;
                }
                nfail = nfail + 1u;
                break;
            }
            if(write(ofd, buf + off, n) != (int)n) return 5;
            done = done + n;
        }
        (void)w4(0xA5A50000u | i);
    }
    (void)w4(0x600D0000u | nfail);
    (void)close(ofd);
    (void)close(memfd);
    (void)write(1, "DONE\n", 5);
    return (int)nfail;
}