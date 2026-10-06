import struct, sys
sys.path.insert(0,'.')
from capstone import *
d=open('libudd5.so','rb').read()
DS_OFF,DS_SZ=0x11e4,0x2280
ST_OFF=0x3464
def nm(x):
    e=d.index(b'\x00',ST_OFF+x); return d[ST_OFF+x:e].decode('latin1')
syms={};obj={}
for i in range(DS_SZ//16):
    o=DS_OFF+i*16
    st_name,st_value,st_size,st_info,st_other,st_shndx=struct.unpack_from('<IIIBBH',d,o)
    if not st_name: continue
    t=st_info&0xf
    if t==2: syms.setdefault(st_value,(nm(st_name),st_size))
    elif t==1: obj.setdefault(st_value,nm(st_name))
RELA_OFF,RELA_SZ=0x7940,0x9c0
got={}
for i in range(RELA_SZ//8):
    off,info=struct.unpack_from('<II',d,RELA_OFF+i*8)
    got[off]=nm(struct.unpack_from('<I',d,DS_OFF+(info>>8)*16)[0])
def run(start,size,label):
    print('='*72); print('%s  @0x%08x size=%d'%(label,start,size))
    for mode,mn in ((CS_MODE_THUMB,'T'),(CS_MODE_ARM,'A')):
        md=Cs(CS_ARCH_ARM,mode); md.skipdata=True
        code=d[start:start+size]
        cnt=sum(1 for _ in md.disasm(code,start))
        print('  mode=%s decoded=%d/%d'%(mn,cnt,size))
    md=Cs(CS_ARCH_ARM,CS_MODE_THUMB); md.skipdata=True
    for ins in md.disasm(d[start:start+size],start):
        ann=''
        if ins.mnemonic in('bl','blx','b.w','b') and ins.op_str.startswith('#'):
            try: t=int(ins.op_str[1:].replace('0x',''),16)
            except: t=-1
            if t in syms: ann='   ; %s'%syms[t][0]
            elif t in got: ann='   ; [plt]%s'%got[t]
        elif ins.mnemonic in('ldr','add') and 'pc' in ins.op_str:
            pcv=ins.address+8&~3
            try:
                lit=struct.unpack_from('<I',d,ins.address+4+struct.unpack_from('<I',d,ins.address+4&~3 if False else ins.address+4)[0]*0)[0]
            except: lit=None
        print('  %08x  %-9s %-30s%s'%(ins.address,ins.mnemonic,ins.op_str,ann))
def get(name):
    for v,(n,sz) in syms.items():
        if n==name: return v,sz
    return None,None
for n in sys.argv[1:]:
    v,sz=get(n)
    if v is None: print('missing',n); continue
    run(v,sz,n)
