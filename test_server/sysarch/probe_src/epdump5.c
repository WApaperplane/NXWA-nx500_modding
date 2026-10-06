/* epdump5.arm -- 定位"写多少会挂"的最小复现（只读 EP）
 *
 * 用法: epdump5 <outbase> <blk> <chunk_bytes>
 *   chunk = 0  → 整块一次 write
 *   chunk > 0  → 按 chunk 分次 write
 *
 * v5 已证实：块9(256B,1次write) OK；块0(7168B,7次write) 崩。
 * 本版唯一变量 = write 的次数与单次大小，用来判定是
 *   (a) 单次 write 太大   还是   (b) write 次数太多/SD 卡累计压力。
 * ★ 无论结果如何都绝不写任何 EP 寄存器。
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

static const unsigned MAGIC = 0x45503344u;
static const unsigned VER   = 5u;

static int memfd = -1;
static unsigned char buf[8192];

static int w4(int fd, unsigned v)
{
    unsigned char b[4];
    b[0]=(unsigned char)(v&0xffu);       b[1]=(unsigned char)((v>>8)&0xffu);
    b[2]=(unsigned char)((v>>16)&0xffu); b[3]=(unsigned char)((v>>24)&0xffu);
    if(write(fd, b, 4) != 4) return -1;
    return 0;
}

int main(int argc, char **argv)
{
    static struct { unsigned start[10]; unsigned size[10]; } reg;
    unsigned hs[10], hz[10];
    unsigned i, blk, size, chunk, done, n, wcount;
    int epfd, ofd, k;

    if(argc < 4){ (void)write(2, "usage: epdump5 <base> <blk> <chunk>\n", 38); return 1; }
    blk   = (unsigned)strtoul(argv[2], 0, 0);
    chunk = (unsigned)strtoul(argv[3], 0, 0);
    if(blk > 9u) blk = 9u;

    {
        char path[256];
        const char *pre = "/mnt/mmc/_xfer/";
        k = 0;
        while(*pre) path[k++] = *pre++;
        { const char *b = argv[1]; while(*b && k < 240) path[k++] = *b++; }
        path[k] = 0;
        ofd = open(path, O_WRONLY|O_CREAT|O_TRUNC, 0644);
        if(ofd < 0){ (void)write(2, "epdump5: cannot create\n", 24); return 2; }
    }

    memfd = open("/dev/mem", O_RDONLY);
    if(memfd < 0){ (void)w4(ofd, 0xDEAD0001u); (void)close(ofd); return 3; }

    epfd = open("/dev/drime5_ep", O_RDONLY);
    if(epfd < 0) epfd = open("/dev/drime5_ep", O_RDWR);
    memset(&reg, 0, sizeof(reg));
    if(epfd >= 0){
        if(ioctl(epfd, EP_REGINFO_CMD, &reg) != 0) memset(&reg, 0, sizeof(reg));
        (void)close(epfd);
    }
    for(i=0;i<10;i++){
        hs[i] = reg.start[i]; hz[i] = reg.size[i];
        if(hs[i]==0u || hz[i]==0u){ hs[i]=EP_START[i]; hz[i]=BLK_SIZE[i]; }
    }
    size = hz[blk];
    if(chunk == 0u) chunk = size;

    /* header: magic,ver,blk,size,chunk + start/size 表 */
    if(w4(ofd, MAGIC)!=0) return 4;
    if(w4(ofd, VER)!=0)   return 4;
    if(w4(ofd, blk)!=0)   return 4;
    if(w4(ofd, size)!=0)  return 4;
    if(w4(ofd, chunk)!=0) return 4;
    if(w4(ofd, hs[blk])!=0) return 4;
    for(i=0;i<10;i++) if(w4(ofd, hs[i])!=0) return 4;
    for(i=0;i<10;i++) if(w4(ofd, hz[i])!=0) return 4;

    {
        unsigned pg = (unsigned)sysconf(_SC_PAGE_SIZE);
        unsigned page = hs[blk] & ~(pg - 1u);
        unsigned offs = hs[blk] - page;
        void *p = mmap((void*)0, (size_t)size + (size_t)offs, PROT_READ,
                       MAP_SHARED, memfd, (off_t)page);
        if(p == MAP_FAILED){
            (void)w4(ofd, 0xDEAD0002u);
            (void)close(ofd); (void)close(memfd);
            return 5;
        }
        {
            unsigned char *base = (unsigned char *)p;
            base = base + offs;
            /* 进度标记：每写 4KB 落一个 0xA5A5xxxx，崩了能看出跑到哪 */
            done = 0u; wcount = 0u;
            while(done < size){
                n = size - done;
                if(n > chunk) n = chunk;
                if(n > (unsigned)sizeof(buf)) n = (unsigned)sizeof(buf);
                memcpy(buf, base + done, n);
                if(write(ofd, buf, n) != (int)n) break;
                done = done + n;
                wcount = wcount + 1u;
                if((wcount % 4u) == 0u){ (void)w4(ofd, 0xA5A50000u | wcount); }
            }
            (void)w4(ofd, 0x600D0000u | (wcount & 0xfffu));
            (void)w4(ofd, done);
            (void)munmap(p, (size_t)size + (size_t)offs);
        }
    }
    (void)close(ofd);
    (void)close(memfd);
    return 0;
}