#include <unistd.h>
#include <fcntl.h>
#include <errno.h>
#include <string.h>
#include <sys/ioctl.h>

static int n;
static char ob[2048];
static void flush(void){ if(n){ write(1,ob,n); n=0; } }
static void s_(const char*p){ while(*p){ if(n>=(int)sizeof(ob))flush(); ob[n++]=*p++; } }
static void hx(unsigned v,int w){ char t[16]; int i,j=w; for(i=0;i<w;i++)t[i]='0';
    while(v&&j>0){ t[--j]="0123456789abcdef"[v&0xf]; v>>=4; } for(i=0;i<w;i++) s_(t+i); }
static void de(int v){ char t[16]; int i=0; unsigned u; if(v<0){ s_("-"); u=(unsigned)(-v);} else u=v;
    if(!u){ s_("0"); return;} while(u){ t[i++]= '0'+u%10; u/=10;} while(i>0) s_(t+--i); }

#define IOC(d,t,nr,sz) (((d)<<30)|((sz)<<16)|((t)<<8)|(nr))
#define IOR(t,nr,sz)  IOC(2,t,nr,sizeof(sz))
#define IOWR(t,nr,sz) IOC(3,t,nr,sizeof(sz))

int main(void){
    int fd;
    unsigned int v;
    int r;

    s_("T1 start\n"); flush();
    fd = open("/dev/d5_sma", O_RDWR);
    if(fd<0){ s_("open fail\n"); flush(); return 1; }
    s_("fd="); de(fd); s_("\n"); flush();

    /* step1: 纯 _IOR('s',1,uint) */
    v = 0;
    r = ioctl(fd, IOR('s',1,unsigned int), &v);
    s_("step1 IOR('s',1)=0x"); hx(IOR('s',1,unsigned int),8);
    s_(" r="); de(r); s_(" v=0x"); hx(v,8); s_("\n"); flush();

    /* step2: 同上，再来一次（检验是否第一次调用就崩） */
    v = 0;
    r = ioctl(fd, IOR('s',1,unsigned int), &v);
    s_("step2 r="); de(r); s_(" v=0x"); hx(v,8); s_("\n"); flush();

    /* step3: _IOR('s',4,uint) */
    v = 0;
    r = ioctl(fd, IOR('s',4,unsigned int), &v);
    s_("step3 IOR('s',4) r="); de(r); s_(" v=0x"); hx(v,8); s_("\n"); flush();

    /* step4: _IOR('s',8,uint) */
    v = 0;
    r = ioctl(fd, IOR('s',8,unsigned int), &v);
    s_("step4 IOR('s',8) r="); de(r); s_(" v=0x"); hx(v,8); s_("\n"); flush();

    /* step5: 无参数的 _IO 打错，确认 ioctl 本身能不能返回 */
    r = ioctl(fd, IOC(0,'s',99,0), 0);
    s_("step5 IO('s',99) r="); de(r); s_(" errno="); de(errno); s_("\n"); flush();

    close(fd);
    s_("T1 done\n"); flush();
    return 0;
}
