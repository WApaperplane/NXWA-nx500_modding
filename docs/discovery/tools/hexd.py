import sys, os, struct
sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)))
from armcap import fw, off
def hexdump(vaddr, size, label=""):
    d=fw(); o=off(vaddr)
    print("="*78); print(" HEXDUMP va=0x%08x off=0x%06x size=%d %s"%(vaddr,o,size,label)); print("="*78)
    for r in range(0,size,16):
        chunk=d[o+r:o+r+16]
        if not chunk: break
        h=" ".join("%02x"%b for b in chunk)
        a="".join(chr(b) if 32<=b<127 else "." for b in chunk)
        print("0x%08x  %-47s  |%s|"%(vaddr+r,h,a))
if __name__=="__main__":
    hexdump(int(sys.argv[1],0), int(sys.argv[2],0), sys.argv[3] if len(sys.argv)>3 else "")
