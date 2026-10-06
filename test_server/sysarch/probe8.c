/*probe8 = probe7 + include EP 头文件（验证是否头文件引入的问题）*/
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <fcntl.h>
#include <sys/ioctl.h>
#include <sys/mman.h>
#include <errno.h>
#include <media/drime5/ep/d5_ep_ioctl.h>
int main(int argc, char **argv){
    unsigned long target = strtoul(argv[1], NULL, 0);
    int fd; unsigned char *p; unsigned char tmp[256]; int i;
    printf("sizeof(struct ep_reg_info)=%d\n",(int)sizeof(struct ep_reg_info));
    fd = open("/dev/d5_sma", O_RDWR);
    printf("A: open=%d\n", fd); fflush(stdout);
    p = mmap(NULL, 4096, PROT_READ, MAP_SHARED, fd, (off_t)target);
    printf("B: mmap RO=%p\n", (void*)p); fflush(stdout);
    if (p==MAP_FAILED){printf("   fail %s\n",strerror(errno));return 1;}
    printf("C: read %02x %02x %02x %02x\n", p[0],p[1],p[2],p[3]); fflush(stdout);
    munmap(p, 4096);
    p = mmap(NULL, 4096, PROT_READ|PROT_WRITE, MAP_SHARED, fd, (off_t)target);
    printf("E: mmap RW=%p\n", (void*)p); fflush(stdout);
    if (p==MAP_FAILED){printf("   fail %s\n",strerror(errno));return 1;}
    memset(tmp,0,256);
    for(i=0;i<256;i++) tmp[i]=(unsigned char)(i<32?i:0);
    printf("F: memcpy...\n"); fflush(stdout);
    memcpy(p, tmp, 256);
    printf("G: ok, p[0..3]=%02x %02x %02x %02x\n", p[0],p[1],p[2],p[3]);
    munmap(p, 4096);
    printf("DONE\n");
    return 0;
}
