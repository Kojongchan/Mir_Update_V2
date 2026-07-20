"""FBX(→glb)의 정점+UV로 직접 오쏘를 래스터라이즈. glTF 렌더러 무관.
V-as-is 와 V-flip 두 버전을 출력해 어느 UV 규약이 맞는지 본다."""
import struct, json, sys, io
import numpy as np
from PIL import Image

GLB=sys.argv[1] if len(sys.argv)>1 else "poc/out/ground.glb"
DATA=sys.argv[2] if len(sys.argv)>2 else "data"

with open(GLB,"rb") as f: data=f.read()
clen,=struct.unpack_from("<I",data,12); joff=20
j=json.loads(data[joff:joff+clen]); binstart=joff+clen+8
BIN=data[binstart:]
bvs=j["bufferViews"]; acc=j["accessors"]

def read_acc(i):
    a=acc[i]; bv=bvs[a["bufferView"]]
    off=bv.get("byteOffset",0)+a.get("byteOffset",0)
    n=a["count"]; ncomp={"SCALAR":1,"VEC2":2,"VEC3":3}[a["type"]]
    ct=a["componentType"]
    if ct==5126: dt=np.float32; sz=4
    elif ct==5125: dt=np.uint32; sz=4
    elif ct==5123: dt=np.uint16; sz=2
    else: raise
    stride=bv.get("byteStride") or sz*ncomp
    if stride==sz*ncomp:
        arr=np.frombuffer(BIN,dt,n*ncomp,off).reshape(n,ncomp)
    else:
        arr=np.zeros((n,ncomp),dt)
        for k in range(n):
            arr[k]=np.frombuffer(BIN,dt,ncomp,off+k*stride)
    return arr

# 이미지 이름 매핑
img_names=[im["name"].split("\\")[-1] for im in j["images"]]
import glob,os
def load_tile(imgidx):
    name=img_names[imgidx].split(".")[0]  # 4_2_2
    f=glob.glob(os.path.join(DATA,name+".*.jpg"))[0]
    return np.asarray(Image.open(f).convert("RGB"))

# 메시별 데이터 수집
prims=[]
for mesh in j["meshes"]:
    for p in mesh["primitives"]:
        if "TEXCOORD_0" not in p["attributes"]: continue
        pos=read_acc(p["attributes"]["POSITION"]).astype(np.float64)
        uv=read_acc(p["attributes"]["TEXCOORD_0"]).astype(np.float64)
        idx=read_acc(p["indices"]).astype(np.int64).ravel()
        mat=p["material"]
        texsrc=j["textures"][j["materials"][mat]["pbrMetallicRoughness"]["baseColorTexture"]["index"]]["source"]
        prims.append((pos,uv,idx,texsrc))

# 전체 xy bbox (top-down: x=easting(local x), y=northing(local y))
allx=np.concatenate([p[0][:,0] for p in prims])
ally=np.concatenate([p[0][:,1] for p in prims])
xmin,xmax=allx.min(),allx.max(); ymin,ymax=ally.min(),ally.max()
W=1400; H=int(W*(ymax-ymin)/(xmax-xmin))
print("bbox x",xmin,xmax,"y",ymin,ymax,"out",W,H)

def rasterize(vflip):
    canvas=np.zeros((H,W,3),np.uint8)
    tiles={}
    for pos,uv,idx,texsrc in prims:
        if texsrc not in tiles: tiles[texsrc]=load_tile(texsrc)
        tile=tiles[texsrc]; th,tw=tile.shape[:2]
        # 픽셀 좌표 (north-up: y 큰 값이 위 → row 작음)
        px=(pos[:,0]-xmin)/(xmax-xmin)*(W-1)
        py=(1-(pos[:,1]-ymin)/(ymax-ymin))*(H-1)
        tris=idx.reshape(-1,3)
        for t in tris:
            x0,x1,x2=px[t]; y0,y1,y2=py[t]
            minx=int(max(0,np.floor(min(x0,x1,x2)))); maxx=int(min(W-1,np.ceil(max(x0,x1,x2))))
            miny=int(max(0,np.floor(min(y0,y1,y2)))); maxy=int(min(H-1,np.ceil(max(y0,y1,y2))))
            if maxx<minx or maxy<miny: continue
            xs=np.arange(minx,maxx+1); ys=np.arange(miny,maxy+1)
            gx,gy=np.meshgrid(xs,ys)
            d=(y1-y2)*(x0-x2)+(x1-x2)*(y2-y0)
            if abs(d)<1e-9: continue
            a=((y1-y2)*(gx-x2)+(x2-x1)*(gy-y2))/d
            b=((y2-y0)*(gx-x2)+(x0-x2)*(gy-y2))/d
            c=1-a-b
            m=(a>=0)&(b>=0)&(c>=0)
            if not m.any(): continue
            u=a*uv[t[0],0]+b*uv[t[1],0]+c*uv[t[2],0]
            v=a*uv[t[0],1]+b*uv[t[1],1]+c*uv[t[2],1]
            if vflip: v=1-v
            tpx=np.clip((u*(tw-1)).astype(int),0,tw-1)
            tpy=np.clip((v*(th-1)).astype(int),0,th-1)
            canvas[gy[m],gx[m]]=tile[tpy[m],tpx[m]]
    return canvas

for vflip in (False,True):
    out=rasterize(vflip)
    Image.fromarray(out).save(f"poc/results/raster_v{'flip' if vflip else 'asis'}.png")
    print("saved vflip=",vflip)
