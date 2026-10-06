#include <unistd.h>
#include <fcntl.h>
#include <errno.h>
static int n; static char ob[1024];
static void fl(void){ if(n){ write(1,ob,n); n=0; } }
static void s_(const char*p){ while(*p){ if(n>=(int)sizeof(ob))fl(); ob[n++]=*p++; } }
int main(void){
    int fd;
    s_("A start\n"); fl();
    fd = open("/dev/null", O_RDONLY);
    s_("B opened\n"); fl();
    s_("C errno-before="); 
    { char b[16]; int m=0; int v=errno; if(v<0){b[m++]='-';v=-v;} if(!v)b[m++]='0';
      while(v){b[m++]='0'+v%10;v/=10;} write(1,b,m); }
    write(1,"\n",1); fl();
    s_("D no ioctl here, just exit\n"); fl();
    close(fd);
    s_("E done\n"); fl();
    return 0;
}
