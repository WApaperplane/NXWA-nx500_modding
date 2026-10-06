/* epdump6.arm -- 逐 256 字节步进扫块 0，每步【读之前】先落一个标记
 * 用法: epdump6 <outfile> <blk> <step>
 * 目的：定位块 0 (0x20820000, 0x1c00) 到底从哪个偏移开始不可读。
 *   epreg 历史证据：offset 0x000-0x3ff 可读（83 个非零非FF字）
 *   epdump4/5 证据：整个 0x1c00 读不下来（连 header 后 0 字节数据都没有）
 *   ⇒ 假设：0x20820000 页内 0x400 之后开始 fault。需证实或否证。
 * ★ 纯只读。绝不写 EP 寄存器。
 */
#include <unistd.h>
#include <fcntl.h>
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
static int ofd;

static int w4(unsigned v)
{
    unsigned char b[4];
    b[0]=(unsigned char)(v&0xffu);       b[1]=(unsigned char)((v>>8)&0xffu);
    b[2]=(unsigned char)((v>>16)&0xffu); b[3]=(unsigned char)((v>>24)&0xffu);
    if(write(ofd, b, 4) != 4) return -1;
    return 0;
}

int main(int argc, char **argv)
{
    /* ★ 交错结构：raw[2i]=start, raw[2i+1]=size（v7 已修正的 bug 1） */
    static unsigned raw[20];
    unsigned i, blk, step, pg, page, offs, size, at, nsteps, s;
    int epfd, memfd, k;
    void *p;
    unsigned char *base;
    unsigned char b[4];

    if(argc < 4){ (void)write(2, "usage: epdump6 <out> <blk> <step>\n", 36); return 1; }
    blk  = (unsigned)strtoul(argv[2], 0, 0);
    step = (unsigned)strtoul(argv[3], 0, 0);
    if(blk > 9u) blk = 9u;
    if(step == 0u || step > 4096u) step = 256u;

    {
        char path[256];
        const char *pre = "/mnt/mmc/_xfer/";
        k = 0;
        while(*pre) path[k++] = *pre++;
        { const char *x = argv[1]; while(*x && k < 240) path[k++] = *x++; }
        path[k] = 0;
        ofd = open(path, O_WRONLY|O_CREAT|O_TRUNC, 0644);
        if(ofd < 0){ (void)write(2, "epdump6: cannot create\n", 25); return 2; }
    }

    memfd = open("/dev/mem", O_RDONLY);
    epfd = open("/dev/drime5_ep", O_RDONLY);
    if(epfd < 0) epfd = open("/dev/drime5_ep", O_RDWR);
    memset(raw, 0, sizeof(raw));
    if(epfd >= 0){ (void)ioctl(epfd, EP_REGINFO_CMD, raw); (void)close(epfd); }
    for(i=0;i<10;i++){
        if(raw[2*i]==0u || raw[2*i+1]==0u){
            raw[2*i]=EP_START[i]; raw[2*i+1]=BLK_SIZE[i];
        }
    }

    pg   = (unsigned)sysconf(_SC_PAGE_SIZE);
    page = raw[2*blk] & ~(pg - 1u);
    offs = raw[2*blk] - page;
    size = raw[2*blk+1];

    (void)w4(0x45503636u);          /* 'F6' magic */
    (void)w4(raw[2*blk]);
    (void)w4(size);
    (void)w4(step);

    p = mmap((void*)0, (size_t)size + (size_t)offs, PROT_READ, MAP_SHARED,
             memfd, (off_t)page);
    if(p == MAP_FAILED){ (void)w4(0xDEAD0002u); (void)close(ofd); return 5; }
    base = (unsigned char *)p;
    base = base + offs;

    nsteps = size / step;
    for(s=0u; s<nsteps; s++){
        at = s * step;
        /* 标记 BEFORE：0xB0000000|s  表示"即将读 s" */
        if(w4(0xB0000000u | s) != 0) break;
        memcpy(b, base + at, 4);
        /* 标记 AFTER：0xA0000000 | (读到的值 & 0xfff) */
        if(w4(0xA0000000u | ((unsigned)b[0] | ((unsigned)b[1]<<8)
             | ((unsigned)b[2]<<16) | ((unsigned)b[3]<<24)) ) != 0) break;
    }
    (void)w4(0x600D0000u | nsteps);
    (void)munmap(p, (size_t)size + (size_t)offs);
    (void)close(ofd);
    (void)close(memfd);
    return 0;
}