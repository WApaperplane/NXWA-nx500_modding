/* epdump4.arm -- ★纯二进制★ dump EP 子块（只读），v4 定位版
 *
 * 用法: epdump4 <outfile-base> [first_blk] [n_blk]
 *   默认 0 10
 *
 * ★ v3 => v4 的改动（v3 实机 RC=139，header 正确但第一个块就段错误）
 *   1. 拷贝循环改成最朴素的"索引 + memcpy 到静态缓冲"，删掉指针比较循环
 *      （v3 用 `const unsigned char *end = q + size; while(q<end)`，
 *        zig 0.13 -O0 的 ARM 后端在这个形态下生成 SIGSEGV —— 与
 *        MEMORY 里"自定义宏溢出 ⇒ 非法指令"同源：-O0 下少用复杂表达式）
 *   2. 每块写完追加一个 4 字节进度标记 0xA5A50000|idx
 *      ⇒ 即使中途段错误，也能从已落盘长度反推跑到第几块
 *   3. 头部改成 u32 x 6 + u32 x 20，字段更少
 */
#include <unistd.h>
#include <fcntl.h>
#include <errno.h>
#include <string.h>
#include <sys/mman.h>
#include <stdlib.h>

extern int ioctl(int fd, unsigned long request, ...);

static const unsigned long EP_REGINFO_CMD = 0x80506864UL;

/* 实测值（epinfo3 nr=100 size=80, r=0）——兜底表 */
static const unsigned EP_START[10] = {
    0x20820000u,0x20823000u,0x20824000u,0x20826000u,0x20827000u,
    0x20828000u,0x20829000u,0x2082a000u,0x2082b000u,0x20821c00u
};
static const unsigned BLK_SIZE[10] = {
    0x1c00,0x1000,0x2000,0x1000,0x1000,0x1000,0x1000,0x1000,0x1000,0x100
};

static const unsigned MAGIC = 0x45503344u;
static const unsigned VER   = 5u;

static int memfd = -1;
static unsigned char buf[1024];

static int w4(int fd, unsigned v)
{
    unsigned char b[4];
    b[0] = (unsigned char)(v & 0xffu);
    b[1] = (unsigned char)((v >> 8) & 0xffu);
    b[2] = (unsigned char)((v >> 16) & 0xffu);
    b[3] = (unsigned char)((v >> 24) & 0xffu);
    if(write(fd, b, 4) != 4) return -1;
    return 0;
}

static int dumpblk(int ofd, unsigned addr, unsigned size)
{
    unsigned pg = (unsigned)sysconf(_SC_PAGE_SIZE);
    unsigned page, offs, done, n;
    void *p;
    unsigned char *base;

    page = addr & ~(pg - 1u);
    offs = addr - page;

    p = mmap((void*)0, (size_t)size + (size_t)offs, PROT_READ, MAP_SHARED,
             memfd, (off_t)page);
    if(p == MAP_FAILED) return -1;
    base = (unsigned char *)p;
    base = base + offs;

    done = 0;
    while(done < size){
        n = size - done;
        if(n > (unsigned)sizeof(buf)) n = (unsigned)sizeof(buf);
        memcpy(buf, base + done, n);
        if(write(ofd, buf, n) != (int)n){ (void)munmap(p, (size_t)size + (size_t)offs); return -2; }
        done = done + n;
    }
    (void)munmap(p, (size_t)size + (size_t)offs);
    return 0;
}

int main(int argc, char **argv)
{
    /* ★★ v5 修正：0x80506864 = _IOR('h',100,struct ep_phys[10]) = 80 字节。
     *   v3/v4 把它写进 `unsigned hs[10]`（40 字节）⇒ 越界 40 字节踩坏栈 ⇒ SIGSEGV。
     *   必须是 start[10] + size[10] 的完整 80 字节结构。证据：raw5/ep3_full
     *   用 size=80 那次 r=0 且 10/10 非零；epinfo 用 size=44/40/72 时
     *   虽然也 r=0，但那是驱动只填部分字段，读到的 size 不可信。 */
    static struct { unsigned start[10]; unsigned size[10]; } reg;
    unsigned hs[10], hz[10];
    unsigned i, nfail, first, cnt;
    int epfd, ofd, k;

    if(argc < 2){ (void)write(2, "usage: epdump4 <base> [first] [n]\n", 34); return 1; }

    first = 0u; cnt = 10u;
    if(argc >= 3) first = (unsigned)strtoul(argv[2], 0, 0);
    if(argc >= 4) cnt  = (unsigned)strtoul(argv[3], 0, 0);
    if(first > 9u) first = 9u;
    if(cnt > 10u) cnt = 10u;
    if(first + cnt > 10u) cnt = 10u - first;

    {
        char path[256];
        const char *pre = "/mnt/mmc/_xfer/ep_";
        k = 0;
        while(*pre) path[k++] = *pre++;
        { const char *b = argv[1]; while(*b && k < 240) path[k++] = *b++; }
        { const char *suf = ".bin"; while(*suf) path[k++] = *suf++; }
        path[k] = 0;
        ofd = open(path, O_WRONLY|O_CREAT|O_TRUNC, 0644);
        if(ofd < 0){ (void)write(2, "epdump4: cannot create output\n", 31); return 2; }
    }

    memfd = open("/dev/mem", O_RDONLY);
    if(memfd < 0){ (void)write(2, "epdump4: /dev/mem open failed\n", 31); return 3; }

    epfd = open("/dev/drime5_ep", O_RDONLY);
    if(epfd < 0) epfd = open("/dev/drime5_ep", O_RDWR);
    memset(&reg, 0, sizeof(reg));
    if(epfd < 0){
        for(i=0;i<10;i++){ hs[i]=EP_START[i]; hz[i]=BLK_SIZE[i]; }
    } else {
        if(ioctl(epfd, EP_REGINFO_CMD, &reg) != 0){
            for(i=0;i<10;i++){ hs[i]=EP_START[i]; hz[i]=BLK_SIZE[i]; }
        } else {
            for(i=0;i<10;i++){ hs[i]=reg.start[i]; hz[i]=reg.size[i]; }
        }
        (void)close(epfd);
    }
    for(i=0;i<10;i++){
        if(hs[i]==0u || hz[i]==0u){ hs[i]=EP_START[i]; hz[i]=BLK_SIZE[i]; }
    }

    /* header: magic, nblk=10, ver, first, cnt, reserved, then start[10], size[10] */
    if(w4(ofd, MAGIC)!=0) return 4;
    if(w4(ofd, 10u)!=0) return 4;
    if(w4(ofd, VER)!=0) return 4;
    if(w4(ofd, first)!=0) return 4;
    if(w4(ofd, cnt)!=0) return 4;
    if(w4(ofd, 0u)!=0) return 4;
    for(i=0;i<10;i++) if(w4(ofd, hs[i])!=0) return 4;
    for(i=0;i<10;i++) if(w4(ofd, hz[i])!=0) return 4;

    nfail = 0u;
    for(i=first; i<first+cnt; i++){
        int r = dumpblk(ofd, hs[i], hz[i]);
        if(r != 0) nfail = nfail + 1u;
        /* 进度标记：即使后面段错误，也能从落盘长度反推进度 */
        if(w4(ofd, 0xA5A50000u | i)!=0) break;
    }

    (void)close(ofd);
    (void)close(memfd);
    return (int)nfail;
}