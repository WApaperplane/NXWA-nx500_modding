import ftplib, os, sys
HOST='192.168.0.105'
OUT='raw3'
f=ftplib.FTP(HOST, timeout=25); f.login(); f.cwd('/_xfer')
names=['c1_asv','c2_isdvfs','c3_dvfsvals','c4_m4','c5_drmbufs','c6_ep','c7_gpio','c8_clk_summary','c9_thermal','c10_power']
got=[]
for fn in names:
    try:
        with open(os.path.join(OUT,fn),'wb') as fh: f.retrbinary('RETR '+fn, fh.write)
        got.append(fn)
    except Exception as e: print('MISS',fn,e)
try: f.retrbinary('RETR _p3.done', open(os.path.join(OUT,'_p3.done'),'wb').write)
except Exception: print('!! still running')
f.quit(); print('pulled %d/%d'%(len(got),len(names)))
