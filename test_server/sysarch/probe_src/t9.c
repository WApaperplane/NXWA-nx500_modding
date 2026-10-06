#include <unistd.h>
#include <fcntl.h>
#include <errno.h>
#include <sys/ioctl.h>
static int n_; static char obuf_[1024];
static void flush_(void){ if(n_){ write(1,obuf_,n_); n_=0; } }
static void p_(const char*s){ while(*s){ if(n_>=(int)sizeof(obuf_))flush_(); obuf_[n_++]=*s++; } }
static void de_(int v){ char b[16]; int m=0,i; unsigned u; if(v<0){b[m++]='-';u=(unsigned)(-v);}else u=v;
  if(!u)b[m++]='0'; while(u){b[m++]= '0'+u%10;u/=10;} for(i=0;i<m;i++)write(1,b+i,1); }
/* ★ 关键差异：像 t3 那样用 int 算 IOC，不加 UL 后缀、不转unsigned long */
#define IOC(d,t,nr,sz) (((d)<<30)|((sz)<<16)|((t)<<8)|(nr))
int main(void){
    int fd,r; unsigned int v=0;
    p_("1 start\n"); flush_();
    fd = open("/dev/null", O_RDONLY);
    p_("2 opened\n"); flush_();
    p_("3 calling ioctl with IOC(2,'Z',77,4) = ");
    { unsigned long c = (unsigned long)IOC(2,'Z',77,4);
      char h[16]; int i; for(i=0;i<16;i++)h[i]='0';
      i=16; { unsigned x=(unsigned)c; while(x&&i>0){ i--; h[i]="0123456789abcdef"[x&0xf]; x>>=4; } }
      for(i=0;i<16;i++)write(1,h+i,1); }
    p_("\n"); flush_();
    r = ioctl(fd, IOC(2,'Z',77,4), &v);
    p_("4 SURVIVED r="); de_(r); p_("\n"); flush_();
    close(fd); p_("5 end\n"); flush_();
    return 0;
}
