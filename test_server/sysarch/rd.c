/*读 p7 预置的 4 个 LUT 缓冲（只读，验证格式）*/
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <fcntl.h>
#include <sys/mman.h>
#include <errno.h>
int main(int argc, char **argv){
    static const unsigned bufs[]={0x810fd100,0x81101e00,0x81106b00,0x81115200};
    int fd=open("/dev/d5_sma",O_RDONLY);
    int i,k;
    if(fd<0){printf("open: %s\n",strerror(errno));return 1;}
    for(i=0;i<4;i++){
        unsigned long a=bufs[i]&~4095UL, off=bufs[i]&4095UL;
        volatile unsigned char *p=mmap(NULL,4096,PROT_READ,MAP_SHARED,fd,(off_t)a);
        printf("\n=== LUT[%d] @0x%08x (off 0x%lx) ===\n",i,bufs[i],off);
        if(p==MAP_FAILED){printf("  mmap fail: %s\n",strerror(errno));continue;}
        printf("  前64 字节: ");
        for(k=0;k<64;k++) printf("%02x",p[off+k]);
        printf("\n  前32 word: ");
        for(k=0;k<32;k++) printf("%08x ",((volatile unsigned*)p)[off/4+k]);
        printf("\n");
        /* 统计非零 */
        {int nz=0; for(k=0;k<4096;k++) if(p[k]) nz++; printf("  本页非零字节=%d/4096\n",nz);}
        munmap((void*)p,4096);
    }
    close(fd); return 0;
}
