import numpy as np, subprocess, math
from PIL import Image, ImageDraw, ImageFont, ImageFilter
W,H,FPS=1920,1080,60
DUR=2.74; N=round(DUR*FPS)
HIT1, HIT2 = 0.12, 1.18
rng=np.random.default_rng(7)
# brushed steel base
n=rng.normal(0,1,(H,W)).astype(np.float32)
img=Image.fromarray(((n-n.min())/(n.max()-n.min())*255).astype(np.uint8))
img=img.filter(ImageFilter.BoxBlur(0)).resize((W,H))
b=np.asarray(img.filter(ImageFilter.GaussianBlur((0.01))),np.float32)
# horizontal brushing: heavy blur along x
from scipy.ndimage import uniform_filter1d, gaussian_filter
br=uniform_filter1d(n,size=180,axis=1)
br=(br-br.mean())/br.std()
coarse=gaussian_filter(rng.normal(0,1,(H,W)).astype(np.float32),40); coarse/=coarse.std()
steel=0.16+0.035*br+0.03*coarse
# scratches
sc=np.zeros((H,W),np.float32); im=Image.fromarray(sc); d=ImageDraw.Draw(im)
for _ in range(140):
    x=rng.uniform(0,W); y=rng.uniform(0,H); L=rng.uniform(30,260); a=rng.uniform(-0.5,0.5)+ (0 if rng.random()<0.7 else math.pi/2.3)
    d.line([(x,y),(x+L*math.cos(a),y+L*math.sin(a))],fill=float(rng.uniform(0.02,0.08)),width=1)
steel+=gaussian_filter(np.asarray(im),0.6)
yy,xx=np.mgrid[0:H,0:W]; r=np.sqrt(((xx-W/2)/(W*0.62))**2+((yy-H/2)/(H*0.62))**2)
vig=np.clip(1.15-r**1.8,0.15,1)
tint=np.array([0.92,0.97,1.05],np.float32)
font=ImageFont.truetype('/home/user/clips/fonts/BebasNeue-Regular.ttf',250)
sub=ImageFont.truetype('/usr/share/fonts/truetype/inter/Inter-Medium.ttf' if False else [l for l in subprocess.run(['fc-match','-f','%{file}','Inter:medium'],capture_output=True,text=True).stdout.split('\n')][0],30)
def text_layer(txt,f,track):
    widths=[f.getbbox(c)[2]-f.getbbox(c)[0] if c!=' ' else f.size*0.25 for c in txt]
    tw=sum(widths)+track*(len(txt)-1)
    asc,desc=f.getmetrics()
    L=Image.new('L',(int(tw)+40,asc+desc+40),0); d=ImageDraw.Draw(L); x=20
    for c,w in zip(txt,widths):
        if c!=' ': d.text((x-f.getbbox(c)[0],20),c,font=f,fill=255)
        x+=w+track
    return L
T1=text_layer('YASH PATIL',font,18)
T2=text_layer('USC IOVINE AND YOUNG ACADEMY',sub,14)
def ease(t): return 1-(1-min(max(t,0),1))**3
p=subprocess.Popen(['ffmpeg','-v','error','-y','-f','rawvideo','-pix_fmt','rgb24','-s',f'{W}x{H}','-r',str(FPS),'-i','-','-c:v','libx264','-preset','veryfast','-crf','12','-pix_fmt','yuv420p','title.mp4'],stdin=subprocess.PIPE)
for i in range(N):
    t=i/FPS
    if t<HIT1:
        frame=np.zeros((H,W,3),np.float32)
    else:
        u=t-HIT1
        # specular light sweep moving across
        sx=-0.3*W+(u/2.4)*1.6*W
        band=np.exp(-(((xx-sx)-(yy-H/2)*0.35)/(W*0.11))**2)
        lum=steel*(0.55+0.45*ease(u/0.35))+0.22*band*(0.4+0.6*(br*0.15+0.85))
        # pulse on second hit
        if t>=HIT2: lum=lum*(1+0.25*math.exp(-(t-HIT2)*9))
        frame=(lum*vig)[...,None]*tint[None,None,:]
        # title text with metallic gradient + scale-in
        s=1.07-0.07*ease(u/0.55)
        tw,th=T1.size; Ts=T1.resize((int(tw*s),int(th*s)),Image.LANCZOS)
        a=np.asarray(Ts,np.float32)/255*ease(u/0.12)
        x0=W//2-Ts.size[0]//2; y0=int(H*0.47)-Ts.size[1]//2
        # shake for 4 frames after hit
        if u<4/FPS: x0+=int(rng.integers(-6,7)); y0+=int(rng.integers(-4,5))
        gy=np.linspace(1.0,0.72,Ts.size[1])[:,None]
        col=(0.93*gy+0.12*np.exp(-(((np.arange(Ts.size[0])[None,:]+x0-sx)/(W*0.06))**2)))
        sub_=frame[y0:y0+Ts.size[1],x0:x0+Ts.size[0]]
        sub_[:]=sub_*(1-a[...,None])+col[...,None]*a[...,None]
        # glow
        if u<0.6:
            g=gaussian_filter(np.pad(a,((0,0),(0,0))),12)*0.35*(1-u/0.6)
            sub_[:]=np.clip(sub_+g[...,None],0,1.3)
        # subtitle + rule on second hit
        if t>=HIT2:
            v=ease((t-HIT2)/0.4)
            lw=int(520*v); ly=int(H*0.47)+125
            frame[ly:ly+2,W//2-lw//2:W//2+lw//2]=frame[ly:ly+2,W//2-lw//2:W//2+lw//2]*0.3+0.62
            a2=np.asarray(T2,np.float32)/255*v
            x2=W//2-T2.size[0]//2; y2=ly+18+int((1-v)*14)
            s2=frame[y2:y2+T2.size[1],x2:x2+T2.size[0]]
            s2[:]=s2*(1-a2[...,None]*0.95)+0.82*a2[...,None]*0.95
        # flash on hits
        fl=0.85*math.exp(-u*22)
        if t>=HIT2: fl+=0.25*math.exp(-(t-HIT2)*25)
        frame=frame+fl
        # fade out last 0.18s
        fo=min(1,(DUR-t)/0.18); frame*=fo
    grain=rng.normal(0,0.018,(H,W,1)).astype(np.float32)
    frame=np.clip(frame+grain*(frame.mean()>0.01),0,1)
    p.stdin.write((frame*255).astype(np.uint8).tobytes())
p.stdin.close(); p.wait(); print('frames',N)
