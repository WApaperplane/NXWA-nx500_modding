import struct, sys
sys.path.insert(0,'.')
from capstone import *
d=open('libudd5.so','rb').read()
DS_OFF,DS_SZ=0x11e4,0x2280; ST_OFF=0x3464
def nm(x):
    e=d.index(b'\x00',ST_OFF+x); return d[ST_OFF+x:e].decode('latin1')
syms={};objs={}
for i in range(DS_SZ//16):
    o=DS_OFF+i*16
    sn,sv,ssz,si,so,sh=struct.unpack_from('<IIIBBH',d,o)
    if not sn: continue
    t=si&0xf
    if t==2: syms.setdefault(sv,(nm(sn),ssz))
    elif t==1: objs.setdefault(sv,nm(sn))
got={}
for REL,RSZ in ((0x6b88,0xdb8),(0x7940,0x9c0)):
    for i in range(RSZ//8):
        off,info=struct.unpack_from('<II',d,REL+i*8)
        got[off]=nm(struct.unpack_from('<I',d,DS_OFF+(info>>8)*16)[0])
def resolve_bl(t):
    if t in syms: return syms[t][0]
    if t in got: return got[t]
    return None
def dis(name,maxb=400):
    for v,(n,sz) in syms.items():
        if n!=name: continue
        print('='*74); print('%s @0x%08x size=%d'%(name,v,sz)); print('='*74)
        md=Cs(CS_ARCH_ARM,CS_MODE_ARM)
        for ins in md.disasm(d[v:v+min(sz,maxb)],v):
            ann=''
            if ins.mnemonic.startswith('b') and ins.mnemonic!='bic' and '#' in ins.op_str:
                try: t=int(ins.op_str.split('#')[-1],0)
                except: t=None
                if t is not None:
                    r=resolve_bl(t)
                    if r: ann='   ; %s'%r
            elif ins.mnemonic=='ldr' and '[pc' in ins.op_str:
                try:
                    t=int(ins.op_str.split('#')[-1],0)
                    lit=struct.unpack_from('<I',d,(t+ins.address)&~3)[0]
                    ann='   ; &%s=0x%x'%(objs.get(lit,'?'),lit)
                except: pass
            print('%08x  %-8s %-30s%s'%(ins.address,ins.mnemonic,ins.op_str,ann))
        print()
        return
    print('missing',name)
for n in sys.argv[1:]: dis(n)
