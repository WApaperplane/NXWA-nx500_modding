#include <unistd.h>
#include <fcntl.h>
#include <errno.h>
#include <string.h>
#include <sys/ioctl.h>
static int n; static char ob[4096];
static void fl(void){ if(n){ write(1,ob,n); n=0; } }
static void s_(const char*p){ while(*p){ if(n>=(int)sizeof(ob))fl(); ob[n++]=*p++; } }
static void hx(unsigned v,int w){ char t[16]; int i,j=w; for(i=0;i<w;i++)t[i]='0';
    while(v&&j>0){ t[--j]="0123456789abcdef"[v&0xf]; v>>=4; } for(i=0;i<w;i++) s_(t+i); }
static void de(int v){ char t[16]; int i=0; unsigned u; if(v<0){ s_("-"); u=(unsigned)(-v);} else u=v;
    if(!u){ s_("0"); return;} while(u){ t[i++]= '0'+u%10; u/=10;} while(i>0) s_(t+--i); }
#define IOC(d,t,nr,sz) (((d)<<30)|((sz)<<16)|((t)<<8)|(nr))

/* 逐设备测：第一个 ioctl 就崩的device 会被标出来 */
static void one(const char*path){
    int fd, r; unsigned int v=0;
    fd = open(path, O_RDONLY);
    s_("dev "); s_(path); s_(" open="); de(fd);
    if(fd<0){ s_(" (no)\n"); fl(); return; }
    s_("\n  pre-ioctl alive, now calling IOR('Z',77,4)...\n"); fl();
    r = ioctl(fd, IOC(2,'Z',77,4), &v);
    s_("  SURVIVED r="); de(r); s_(" errno="); de(errno); s_("\n"); fl();
    close(fd);
}

int main(void){
    s_("T3 start\n"); fl();
    /* 对照组：普通设备 ioctl 应该正常返回 ENOTTY */
    one("/dev/null");
    one("/dev/urandom");
    one("/dev/d5_sma");
    one("/dev/d5_ipcc");
    one("/dev/d5_lock");
    one("/dev/drime5_ep");
    s_("T3 done\n"); fl();
    return 0;
}
