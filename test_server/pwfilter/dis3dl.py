import struct, sys
sys.path.insert(0,'.')
from capstone import *
d=open('libudd5.so','rb').read()
DS_OFF,DS_SZ=0x11e4,0x2280
ST_OFF=0x3464
def nm(x):
    e=d.index(b'\x00',ST_OFF+x); return d[ST_OFF+x:e].decode('latin1')
syms={}
for i in range(DS_SZ//16):
    o=DS_OFF+i*16
    st_name,st_value,st_size,st_info,st_other,st_shndx=struct.unpack_from('<IIIBBH',d,o)
    if st_name and (st_info&0xf)==2: syms[st_value]=(nm(st_name),st_size)
# plt/got: find target of PLT entries by scanning .rela.plt relocs
RELA_OFF,RELA_SZ=0x7940,0x9c0
JMPREL=0x7940
# .rel.plt at 0x7940 size 0x9c0
got={}
for i in range(RELA_SZ//8):
    off,info=struct.unpack_from('<II',d,RELA_OFF+i*8)
    symidx=info>>8; typ=info&0xff
    o=DS_OFF+symidx*16
    st_name=struct.unpack_from('<I',d,o)[0]
    got[off]=nm(st_name)
def dis(name):
    for v,(n,sz) in syms.items():
        if n==name:
            print('='*70); print('%s  @0x%08x  size=%d'%(name,v,sz))
            code=d[v:v+sz]
            md=Cs(CS_ARCH_ARM,CS_MODE_THUMB)
            md.detail=False
            for ins in md.disasm(code,v):
                # annotate bl to known symbols
                ann=''
                if ins.mnemonic in ('bl','blx','b') and ins.op_str.startswith('#'):
                    try: t=int(ins.op_str[1:],16)
                    except: t=-1
                    if t in syms: ann='  ; %s'%syms[t][0]
                    elif t in got: ann='  ; [plt]%s'%got[t]
                print('  %08x  %-8s %-28s%s'%(ins.address,ins.mnemonic,ins.op_str,ann))
            return v,sz
    print('not found',name)
for n in sys.argv[1:]: dis(n)
