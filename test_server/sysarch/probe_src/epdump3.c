/* epdump3.arm -- ★纯二进制★ dump 全部 EP 子块（只读）
 *
 * 用法: epdump3 <outfile-base>
 *   例: epdump3 base   ->  /mnt/mmc/_xfer/ep_base.bin  (44288 字节裸数据)
 *
 * ★★★ 为什么是二进制而不是文本（v3 的核心修正）★★★
 *   v2 把 11072 个寄存器逐个格式化成 "  blk 0x1234 0x12345678\n"（约 324KB），
 *   在单核相机上：sd 卡的 write() 逐行调用 + 320KB 数据量 = 卡死。
 *   实测：v2 首次运行直接把相机打到无响应，只能拔电池重启。
 *   ⇒ v3 只做一件事：memcpy 到 write()。44288 字节一次落盘，
 *     相机侧 CPU 占用接近 0，格式化/解析全部放到 PC 端。
 *
 * ★★ 文件格式（小端，与 dump 顺序一致）★★
 *   u32 magic   = 0x45503344  ('D3PE')
 *   u32 nblk    = 10
 *   u32 total   = 44288
 *   u32 version = 3
 *   然后 10 组：u32 start[10], u32 size[10]
 *   接着按 BLK[] 顺序紧密拼接各块原始字节
 */
#include <unistd.h>
#include <fcntl.h>
#include <errno.h>
#include <string.h>
#include <sys/mman.h>
#include <stdlib.h>

extern int ioctl(int fd, unsigned long request, ...);

/* 预计算 ioctl 号（禁 shift，见 MEMORY 交叉编译铁律 2） */
static const unsigned long EP_REGINFO_CMD = 0x80506864UL;

/* 实测值（epinfo3 nr=100 size=80, r=0）—— 兜底表，不是猜测 */
static const unsigned EP_START[10] = {
    0x20820000u,0x20823000u,0x20824000u,0x20826000u,0x20827000u,
    0x20828000u,0x20829000u,0x2082a000u,0x2082b000u,0x20821c00u
};
static const char *BLK[10] = {
    "top","ldc","mc","rsz","lvr","bblt","fd","jpeg","3dlut","nog"
};
static const unsigned BLK_SIZE[10] = {
    0x1c00,0x1000,0x2000,0x1000,0x1000,0x1000,0x1000,0x1000,0x1000,0x100
};

static const unsigned MAGIC = 0x45503344u;
static const unsigned VER   = 3u;

static int memfd = -1;

/* 把一个块只读映射并原样写出，返回 0 成功 */
static int dumpblk(int ofd, unsigned addr, unsigned size)
{
    unsigned pg = (unsigned)sysconf(_SC_PAGE_SIZE);
    off_t pa; unsigned offs;
    void *p;

    pa   = (off_t)(addr & ~(pg - 1u));       /* 页对齐，否则 mmap EINVAL */
    offs = addr - (unsigned)pa;

    p = mmap((void*)0, (size_t)(size + offs), PROT_READ, MAP_SHARED, memfd, pa);
    if(p == MAP_FAILED){
        /* 单块失败不终止：写 0 填充占位，PC 端能看出哪块没读到 */
        static const unsigned char ZERO[256] = {0};
        unsigned left = size;
        while(left){
            unsigned n = left > sizeof(ZERO) ? (unsigned)sizeof(ZERO) : left;
            if(write(ofd, ZERO, n) < 0) return -1;
            left -= n;
        }
        return -1;
    }
    {
        const unsigned char *q = (const unsigned char *)p + offs;
        const unsigned char *end = q + size;
        while(q < end){
            unsigned left = (unsigned)(end - q);
            /* 单次 write 不超过 4096：控制 SD 卡写入节奏，降低 monopolize 风险 */
            unsigned n = left > 4096u ? 4096u : left;
            if(write(ofd, q, n) != (int)n){ munmap(p, (size_t)(size + offs)); return -2; }
            q += n;
        }
    }
    munmap(p, (size_t)(size + offs));
    return 0;
}

int main(int argc, char **argv)
{
    unsigned hs[10], hz[10];
    unsigned i, nfail = 0;
    int epfd;
    char path[256];
    int ofd, k;

    if(argc < 2){ write(2, "usage: epdump3 <base>\n", 22); return 1; }

    /* 输出路径 */
    k = 0;
    { const char *pre = "/mnt/mmc/_xfer/ep_"; while(*pre) path[k++] = *pre++; }
    { const char *b = argv[1]; while(*b && k < 240) path[k++] = *b++; }
    { const char *suf = ".bin"; while(*suf) path[k++] = *suf++; }
    path[k] = 0;

    ofd = open(path, O_WRONLY|O_CREAT|O_TRUNC, 0644);
    if(ofd < 0){ write(2, "epdump3: cannot create output\n", 31); return 2; }

    memfd = open("/dev/mem", O_RDONLY);
    if(memfd < 0){ write(2, "epdump3: /dev/mem open failed\n", 30); return 3; }

    /* EP_REGINFO 属于 /dev/drime5_ep，不是 /dev/mem（v2 踩过：RC=3） */
    epfd = open("/dev/drime5_ep", O_RDONLY);
    if(epfd < 0) epfd = open("/dev/drime5_ep", O_RDWR);
    if(epfd < 0){
        for(i=0;i<10;i++){ hs[i]=EP_START[i]; hz[i]=BLK_SIZE[i]; }
    } else {
        memset(hs, 0, sizeof(hs));
        if(ioctl(epfd, EP_REGINFO_CMD, hs) != 0){
            for(i=0;i<10;i++){ hs[i]=EP_START[i]; hz[i]=BLK_SIZE[i]; }
        }
        close(epfd);
    }
    for(i=0;i<10;i++){
        if(hs[i]==0 || hz[i]==0){ hs[i]=EP_START[i]; hz[i]=BLK_SIZE[i]; }
    }

    /* header */
    { unsigned hdr[4 + 20];
      hdr[0]=MAGIC; hdr[1]=10u; hdr[2]=0u; hdr[3]=VER;
      hdr[2]=44288u;
      for(i=0;i<10;i++){ hdr[4+i]=hs[i]; hdr[14+i]=hz[i]; }
      if(write(ofd, hdr, sizeof(hdr)) != (int)sizeof(hdr)){ close(ofd); return 4; }
    }

    /* 逐块原样 dump */
    for(i=0;i<10;i++){
        if(dumpblk(ofd, hs[i], hz[i]) != 0) nfail++;
    }

    close(ofd);
    close(memfd);
    return nfail ? 10 : 0;
}