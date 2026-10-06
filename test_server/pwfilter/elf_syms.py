"""解析 ARM ELF 的 .dynsym，列出导出函数符号（相机上没有 binutils）"""
import struct
import sys

path = sys.argv[1] if len(sys.argv) > 1 else r'D:\download\NX-KS2-88\test_server\pwfilter\libSLP-db-util.so'
d = open(path, 'rb').read()

assert d[:4] == b'\x7fELF', 'not ELF'
ei_class = d[4]          # 1=32bit
ei_data = d[5]           # 1=LE
e_type, e_machine = struct.unpack_from('<HH', d, 16)
e_shoff, = struct.unpack_from('<I', d, 32)
e_shentsize, e_shnum, e_shstrndx = struct.unpack_from('<HHH', d, 46)

print('ELF32 %s  machine=%d  sections=%d' % ('LE' if ei_data == 1 else 'BE', e_machine, e_shnum))

# 节头
secs = []
for i in range(e_shnum):
    off = e_shoff + i * e_shentsize
    sh_name, sh_type, sh_flags, sh_addr, sh_offset, sh_size = struct.unpack_from('<IIIIII', d, off)
    secs.append(dict(name_off=sh_name, type=sh_type, addr=sh_addr, off=sh_offset, size=sh_size))

# 节名表
shstr = secs[e_shstrndx]
shstrtab = d[shstr['off']:shstr['off'] + shstr['size']]


def sname(off):
    end = shstrtab.index(b'\x00', off)
    return shstrtab[off:end].decode('ascii', 'replace')


STT = {0: 'NOTYPE', 1: 'OBJECT', 2: 'FUNC', 3: 'SECTION', 4: 'FILE'}

for i, sec in enumerate(secs):
    if sec['type'] in (2, 11):   # SHT_SYMTAB / SHT_DYNSYM
        linked = secs[sec['name_off'] and i] if False else None
        # 符号表的 name_off 在结构里，读出 link 字段
        off_h = e_shoff + i * e_shentsize
        sh_link, = struct.unpack_from('<I', d, off_h + 24)
        entsize, = struct.unpack_from('<I', d, off_h + 36)
        strtab = secs[sh_link]
        st = d[strtab['off']:strtab['off'] + strtab['size']]
        print()
        print('=== %s (section %d, %d entries) ===' % (sname(sec['name_off']), i, sec['size'] // (entsize or 16)))
        n = sec['size'] // (entsize or 16)
        for k in range(n):
            p = sec['off'] + k * entsize
            st_name, st_value, st_size, st_info, st_other, st_shndx = struct.unpack_from('<IIIBBH', d, p)
            if st_name == 0:
                continue
            end = st.index(b'\x00', st_name)
            nm = st[st_name:end].decode('ascii', 'replace')
            ttype = STT.get(st_info & 0xF, str(st_info & 0xF))
            if st_info & 0xF == 2 or (nm and not nm.startswith('$')):
                bind = 'GLOBAL' if (st_info >> 4) == 1 else ('LOCAL' if (st_info >> 4) == 0 else 'WEAK')
                print('  %-8s %-10s 0x%08x  %s' % (ttype, bind, st_value, nm))
