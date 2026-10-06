#include <unistd.h>
#include <fcntl.h>
#include <errno.h>
int main(void){
    write(1,"T0-OK\n",6);
    int fd = open("/dev/d5_sma", O_RDWR);
    write(1,"open fd=",8);
    char b[16]; int n=0; int v=fd;
    if(v<0){ b[n++]='-'; v=-v; }
    if(v==0) b[n++]='0';
    while(v){ b[n++]='0'+v%10; v/=10; }
    write(1,b,n);
    write(1,"\n",1);
    if(fd>=0) close(fd);
    write(1,"T0-DONE\n",8);
    return 0;
}
