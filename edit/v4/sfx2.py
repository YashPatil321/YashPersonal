import numpy as np, wave
from scipy.signal import fftconvolve, butter, sosfilt
SR=48000; rng=np.random.default_rng(21)
def t(d): return np.arange(int(d*SR))/SR
def save(n,x):
    x=np.asarray(x); x=x if x.ndim==2 else np.stack([x,x],1)
    x=x/max(1e-9,np.abs(x).max())*0.95
    w=wave.open(n,'wb'); w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR); w.writeframes((x*32767).astype(np.int16).tobytes()); w.close()
def bp(x,lo,hi,o=2): return sosfilt(butter(o,[lo,hi],'band',fs=SR,output='sos'),x)
def lp(x,f,o=2): return sosfilt(butter(o,f,'low',fs=SR,output='sos'),x)
def hp(x,f,o=2): return sosfilt(butter(o,f,'high',fs=SR,output='sos'),x)
def verb(x,dur=1.6,mix=0.25,damp=4000):
    n=int(dur*SR); tt=np.arange(n)/SR
    irL=lp(rng.normal(0,1,n),damp)*np.exp(-tt*4.5/dur*1.5); irR=lp(rng.normal(0,1,n),damp)*np.exp(-tt*4.5/dur*1.5)
    irL[:int(0.012*SR)]=0; irR[:int(0.017*SR)]=0
    L=fftconvolve(x,irL)[:len(x)+n]; R=fftconvolve(x,irR)[:len(x)+n]
    L/=np.abs(L).max()+1e-9; R/=np.abs(R).max()+1e-9
    dry=np.pad(x,(0,n))[:len(L)]; dry=dry/(np.abs(dry).max()+1e-9); R=np.pad(R,(0,len(L)-len(R)))
    return np.stack([dry+mix*L,dry+mix*R],1)
# cinematic impact: layered sub drop + body thud + bright crack, into a big tail
tt=t(2.5)
sub=np.sin(2*np.pi*np.cumsum(32+48*np.exp(-tt*6))/SR)*np.exp(-tt*1.8)
body=lp(rng.normal(0,1,len(tt)),180)*np.exp(-tt*9)*3
crack=hp(rng.normal(0,1,len(tt)),2500)*np.exp(-tt*60)*0.5
save('impact.wav',verb(sub*1.0+body*0.6+crack*0.35,2.2,0.35,3000))
# soft whoosh (0.55s): band-limited air that sweeps up and pans across, ends on the cut
def whoosh(d,lo0,lo1,pan=True):
    tt=t(d); nz=rng.normal(0,1,len(tt)); out=np.zeros_like(nz)
    steps=24
    for i in range(steps):
        a,b_=int(i*len(tt)/steps),int((i+1)*len(tt)/steps); f=lo0+(lo1-lo0)*(i/steps)**1.6
        out[a:b_]=bp(nz,f,f*2.2)[a:b_]
    env=np.sin(np.pi*np.clip(tt/d,0,1)*0.92)**2.5
    p=np.linspace(-0.8,0.8,len(tt)) if pan else np.zeros(len(tt))
    x=out*env; return np.stack([x*np.sqrt((1-p)/2),x*np.sqrt((1+p)/2)],1)
save('whoosh.wav',whoosh(0.55,300,2400))
# riser into the shop drop (1.4s): rising tone + air, tight end
tt=t(1.4); f=180*2**(tt/1.4*2.2); tone=np.sin(2*np.pi*np.cumsum(f)/SR)*0.25+np.sin(2*np.pi*np.cumsum(f*1.5)/SR)*0.12
air=whoosh(1.4,400,5000,False)[:,0]
env=(tt/1.4)**2.5; save('riser.wav',verb((tone+air*1.5)*env,0.8,0.2))
# heavy toggle switch: sharp metal click + plastic body + low thump, small room
tt=t(0.3)
clk=hp(rng.normal(0,1,len(tt)),3000)*np.exp(-tt*1400)
ping=np.sin(2*np.pi*3100*tt)*np.exp(-tt*160)*0.25+np.sin(2*np.pi*5200*tt)*np.exp(-tt*240)*0.12
bod=bp(rng.normal(0,1,len(tt)),400,1500)*np.exp(-tt*120)*0.6
thump=np.sin(2*np.pi*np.cumsum(55+70*np.exp(-tt*50))/SR)*np.exp(-tt*25)*0.9
save('switch.wav',verb(clk*1.2+ping+bod+thump,0.5,0.12,6000))
# power-up: electrical surge rising into a hum
tt=t(1.1); f=50+70*(1-np.exp(-tt*5)); ph=2*np.pi*np.cumsum(f)/SR
hum=sum(np.sin(k*ph)/k for k in (1,2,3,4,6))*np.minimum(1,tt/0.05)*np.exp(-np.maximum(0,tt-0.5)*3.5)
zap=hp(rng.normal(0,1,len(tt)),4000)*np.exp(-tt*30)*0.15
save('powerup.wav',verb(hum*0.5+zap,0.6,0.15))
# downlifter into the desk section: falling tone, airy, long tail
tt=t(1.6); f=900*2**(-tt/1.6*3)
down=np.sin(2*np.pi*np.cumsum(f)/SR)*np.exp(-tt*1.5)*0.3+whoosh(1.6,3000,300,False)[:,0]*np.exp(-tt*1.2)
save('down.wav',verb(down,1.8,0.4,2500))
print('sfx ok')
