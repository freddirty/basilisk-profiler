# SPDX-License-Identifier: GPL-2.0-or-later
import sys,struct,re
def varint(b,i):
    r=s=0
    while True:
        c=b[i];i+=1;r|=(c&0x7f)<<s;s+=7
        if c<0x80:return r,i
def snappy(b):
    n,i=varint(b,0);o=bytearray()
    while i<len(b):
        t=b[i];i+=1;k=t&3
        if k==0:
            l=t>>2
            if l>=60:
                nb=l-59;l=int.from_bytes(b[i:i+nb],'little');i+=nb
            l+=1;o+=b[i:i+l];i+=l;continue
        if k==1:l=((t>>2)&7)+4;off=((t>>5)<<8)|b[i];i+=1
        elif k==2:l=(t>>2)+1;off=int.from_bytes(b[i:i+2],'little');i+=2
        else:l=(t>>2)+1;off=int.from_bytes(b[i:i+4],'little');i+=4
        for _ in range(l):o.append(o[-off])
    return bytes(o)
d=open(sys.argv[1],'rb').read()
ft=d[-48:];i=0
_,i=varint(ft,0);_,i=varint(ft,i);io,i=varint(ft,i);isz,_=varint(ft,i)
def block(off,sz):
    raw=d[off:off+sz];t=d[off+sz]
    return snappy(raw) if t==1 else raw
def entries(blk):
    nr=struct.unpack('<I',blk[-4:])[0];end=len(blk)-4-4*nr;i=0;key=b''
    while i<end:
        sh,i=varint(blk,i);ns,i=varint(blk,i);vl,i=varint(blk,i)
        key=key[:sh]+blk[i:i+ns];i+=ns;v=blk[i:i+vl];i+=vl;yield key,v
out=bytearray()
for k,v in entries(block(io,isz)):
    o,j=varint(v,0);s,_=varint(v,j)
    for kk,vv in entries(block(o,s)):
        out+=b'\n#KEY '+kk+b'\n'+vv
open(sys.argv[2],'wb').write(out)
print(len(out))
