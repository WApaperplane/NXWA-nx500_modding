/*逐行定位 SIGSEGV 点：完全复刻 mmtest 但加上 eplut7 的步骤 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <fcntl.h>
#include <sys/mman.h>
#include <errno.h>
int main(int argc, char **argv){
    unsigned long target = strtoul(argv[1], NULL, 0);
    int fd; volatile unsigned *p; unsigned char tmp[256]; int i;
    fd = open("/dev/d5_sma", O_RDWR);
    printf("A: open=%d\n", fd); fflush(stdout);
    p = mmap(NULL, 4096, PROT_READ, MAP_SHARED, fd, (off_t)target);
    printf("B: mmap RO=%p\n", (void*)p); fflush(stdout);
    if (p==MAP_FAILED){printf("   fail %s\n",strerror(errno));return 1;}
    printf("C: read %08x %08x %08x %08x\n", p[0],p[1],p[2],p[3]); fflush(stdout);
    munmap((void*)p, 4096);
    printf("D: munmap ok\n"); fflush(stdout);
    p = mmap(NULL, 4096, PROT_READ|PROT_WRITE, MAP_SHARED, fd, (off_t)target);
    printf("E: mmap RW=%p\n", (void*)p); fflush(stdout);
    if (p==MAP_FAILED){printf("   fail %s\n",strerror(errno));return 1;}
    memset(tmp,0,256);
    for(i=0;i<256;i++) tmp[i]=(unsigned char)i;
    printf("F: memcpy 256...\n"); fflush(stdout);
    memcpy((void*)p, tmp, 256);
    printf("G: memcpy ok, p[0]=%08x\n", p[0]); fflush(stdout);
    printf("H: munmap\n"); fflush(stdout);
    munmap((void*)p, 4096);
    printf("DONE\n");
    return 0;
}
