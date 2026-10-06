#include <unistd.h>
#include <fcntl.h>
#include <errno.h>
/* ★ 自己声明 ioctl 原型，不用 sys/ioctl.h ——那个头在 NX500 上生成错误代码 */
extern int ioctl(int fd, unsigned long request, ...);
static int n; static char ob[1024];
static void fl(void){ if(n){ write(1,ob,n); n=0; } }
static void s_(const char*p){ while(*p){ if(n>=(int)sizeof(ob))fl(); ob[n++]=*p++; } }
static void de(int v){ char b[16]; int m=0,i; unsigned u; if(v<0){ b[m++]='-'; u=(unsigned)(-v);} else u=v;
  if(!u)b[m++]='0'; while(u){b[m++]= '0'+u%10; u/=10;} for(i=0;i<m;i++)write(1,b+i,1); }
int main(void){
    int fd, r; unsigned int v=0;
    s_("1 start\n"); fl();
    fd = open("/dev/null", O_RDONLY);
    s_("2 fd="); de(fd); s_("\n"); fl();
    r = ioctl(fd, 0x00005417UL, 0);        /* _IO('T',23) 随便一个 */
    s_("3 ioctl r="); de(r); s_(" errno="); de(errno); s_("\n"); fl();
    r = ioctl(fd, 0x80546800UL, &v);        /* _IOR('h',0,4) */
    s_("4 ioctl2 r="); de(r); s_(" v="); de((int)v); s_("\n"); fl();
    close(fd);
    s_("5 done\n"); fl();
    return 0;
}
