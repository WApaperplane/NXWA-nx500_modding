#include <stdio.h>
#include <sys/ioctl.h>
struct ep_phys { unsigned int start, size; };
struct ep_reg_info_80 { struct ep_phys top,ldc,mc,rsz,lvr,bblt,fd,jpeg,lut3d,nog; };
int main(void){
    printf("sizeof(ep_phys)      = %u\n", (unsigned)sizeof(struct ep_phys));
    printf("sizeof(ep_reg_info)  = %u\n", (unsigned)sizeof(struct ep_reg_info_80));
    printf("EP  _IOR('h',100,info80) = 0x%08lx\n", (unsigned long)_IOR('h',100,struct ep_reg_info_80));
    printf("EP  _IOR('h',100,info40) = 0x%08lx\n", (unsigned long)_IOR('h',100,char[40]));
    printf("EP  _IOR('h',100,info72) = 0x%08lx\n", (unsigned long)_IOR('h',100,char[72]));
    printf("SMA _IOR('S',1,uint)     = 0x%08lx\n", (unsigned long)_IOR('S',1,unsigned int));
    printf("SMA _IOR('S',4,uint)     = 0x%08lx\n", (unsigned long)_IOR('S',4,unsigned int));
    printf("SMA _IOR('S',8,uint)     = 0x%08lx\n", (unsigned long)_IOR('S',8,unsigned int));
    printf("SMA _IOR('S',2,uint)     = 0x%08lx\n", (unsigned long)_IOR('S',2,unsigned int));
    printf("IPCC_IOR('I',3,c[64])   = 0x%08lx\n", (unsigned long)_IOR('I',3,char[64]));
    printf("IPCC_IOR('I',4,c[64])   = 0x%08lx\n", (unsigned long)_IOR('I',4,char[64]));
    return 0;
}
