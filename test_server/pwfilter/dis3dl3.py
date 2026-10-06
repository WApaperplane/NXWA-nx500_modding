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
    st_name,st_value,st_size,st_info,st_other,st_shndx=struct.unpack_from('<IIIBBH',d,o)
    if not st_name: continue
    t=st_info&0xf
    if t==2: syms.setdefault(st_value,(nm(st_name),st_size))
    elif t==1: objs.setdefault(st_value,nm(st_name))
RELA_OFF,RELA_SZ=0x7940,0x9c0
got={}
for i in range(RELA_SZ//8):
    off,info=struct.unpack_from('<II',d,RELA_OFF+i*8)
    got[off]=nm(struct.unpack_from('<I',d,DS_OFF+(info>>8)*16)[0])
def imm(ins):
    try: return int(ins.op_str.split('#')[-1],0)
    except: return None
def dis(name):
    for v,(n,sz) in syms.items():
        if n!=name: continue
        print('='*74); print('%s @0x%08x size=%d'%(name,v,sz)); print('='*74)
        md=Cs(CS_ARCH_ARM,CS_MODE_ARM)
        for ins in md.disasm(d[v:v+sz],v):
            ann=''
            if ins.mnemonic.startswith('b') and ins.mnemonic!='bic' and '#' in ins.op_str:
                t=imm(ins)
                if t in syms: ann='   ; %s'%syms[t][0]
                elif t in got: ann='   ; [plt]%s'%got[t]
            elif ins.mnemonic=='ldr' and '[pc' in ins.op_str:
                t=imm(ins)
                if t is not None:
                    try:
                        lit=struct.unpack_from('<I',d,(t+ins.address)&~3)[0]
                        if lit in objs: ann='   ; &%s'%objs[lit]
                        else: ann='   ; =0x%x'%lit
                    except: pass
            print('%08x  %-8s %-30s%s'%(ins.address,ins.mnemonic,ins.op_str,ann))
        return
    print('missing',name)
for n in sys.argv[1:]: dis(n)
