#include <unistd.h>
#include <fcntl.h>
#include <errno.h>
#include <sys/ioctl.h>          /* ★ 唯一差异：加回这个 include */
extern int ioctl(int fd, unsigned long request, ...);  /* 再自己声明一次 */
static int n_; static char obuf_[1024];
static void flush_(void){ if(n_){ write(1,obuf_,n_); n_=0; } }
static void p_(const char*s){ while(*s){ if(n_>=(int)sizeof(obuf_))flush_(); obuf_[n_++]=*s++; } }
int main(void){
    int fd,r; unsigned int v=0;
    p_("1 start\n"); flush_();
    fd = open("/dev/null", O_RDONLY);
    p_("2 opened\n"); flush_();
    r = ioctl(fd, 0x80546800UL, &v);
    p_("3 ioctl done\n"); flush_();
    (void)r;
    close(fd);
    p_("4 end\n"); flush_();
    return 0;
}
