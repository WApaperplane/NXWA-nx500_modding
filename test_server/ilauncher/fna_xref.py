# -*- coding: utf-8 -*-
"""Locate all references to specific FnA.dll strings, plus full string dump."""
import pefile, re
P = 'E:/iLauncher/firmwareUpgrader/FnA.dll'
pe = pefile.PE(P); IB = pe.OPTIONAL_HEADER.ImageBase
secs = [(s.Name.rstrip(b'\x00').decode(), s.VirtualAddress, s.Misc_VirtualSize,
         s.PointerToRawData, s.SizeOfRawData) for s in pe.sections]
d = open(P,'rb').read()

def rva2off(rva):
    for n,va,vs,pr,rs in secs:
        if va <= rva < va+max(vs,rs): return pr+(rva-va)
def off2rva(off):
    for n,va,vs,pr,rs in secs:
        if pr <= off < pr+rs: return va+(off-pr)

# map all strings to VA
smap = {}
for m in re.finditer(rb'[\x20-\x7e]{4,300}', d):
    va = off2rva(m.start())
    if va: smap[m.group().decode('latin1')] = va

KEY = ['device_xml_path','firmware_copy_dir','Device xml full path','DownloadURL',
       'Download Complete','Unzip success','Firmware Copy dir','SD Card Has Space',
       "SD Card doesn't has Space",'Firmware Copy successful','not successful',
       'Creating thread to copy','downloadToFile','Unzipper::extract','firmware',
       '.zip','.bin','.srf','FirmwareInfo','fw_new_url','CreateDirectoryW',
       'GetDiskFreeSpaceExW','CopyFileExW']

print('=== string VAs ===')
for k in KEY:
    hits = [s for s in smap if k.lower() in s.lower()]
    for h in hits[:4]:
        print('  %08x  "%s"' % (smap[h], h[:100]))

# --- find code refs: push imm32 / mov imm32 to these VAs ---
print('\n=== xrefs (code that pushes/moves these VAs) ===')
target_vas = {}
for k in KEY:
    for s in smap:
        if k.lower() in s.lower():
            target_vas[smap[s]] = s
tv = set(target_vas)

sec_text = [s for s in secs if s[0]=='.text'][0]
_,tva,tvs,tpr,trs = sec_text
code = d[tpr:tpr+trs]
found = 0
for off in range(0, len(code)-4):
    v = int.from_bytes(code[off:off+4],'little')
    if v in tv:
        va = tva + off
        print('  ref@%08x -> %08x "%s"' % (va, v, target_vas[v][:70]))
        found += 1
print('total refs', found)
