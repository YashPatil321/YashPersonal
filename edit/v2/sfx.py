import numpy as np, wave
SR=48000; rng=np.random.default_rng(3)
def save(name,x):
    x=np.clip(x,-1,1); st=np.stack([x,x],1) if x.ndim==1 else x
    w=wave.open(name,'wb'); w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR); w.writeframes((st*32767).astype(np.int16).tobytes()); w.close()
def t(d): return np.arange(int(d*SR))/SR
def lp(x,a):  # one-pole lowpass
    y=np.empty_like(x); s=0.0
    for i,v in enumerate(x): s+=a*(v-s); y[i]=s
    return y
# cinematic boom: pitched-down sub + noise transient + soft tail
tt=t(2.2); f=38+34*np.exp(-tt*5); ph=2*np.pi*np.cumsum(f)/SR
boom=np.sin(ph)*np.exp(-tt*2.2)*0.9
boom+=lp(rng.normal(0,1,len(tt)),0.08)*np.exp(-tt*18)*0.6
boom+=np.sin(2*np.pi*55*tt)*np.exp(-tt*6)*0.25
save('boom.wav',boom*0.9)
# whoosh riser (0.7s): noise through sweeping lowpass, swelling to the cut
tt=t(0.7); nz=rng.normal(0,1,len(tt)); out=np.empty_like(nz); s=0
a=0.01+0.25*(tt/0.7)**2
for i,v in enumerate(nz): s+=a[i]*(v-s); out[i]=s
env=(tt/0.7)**2.2; env[-int(0.02*SR):]*=np.linspace(1,0,int(0.02*SR))
L=out*env; R=np.roll(out,90)*env
save('whoosh.wav',np.stack([L,R],1)*1.6)
# downlifter (1.2s): reverse of a whoosh, falling, for the shift into the chill section
tt=t(1.2); nz=rng.normal(0,1,len(tt)); out=np.empty_like(nz); s=0
a=0.2*np.exp(-tt*3)+0.005
for i,v in enumerate(nz): s+=a[i]*(v-s); out[i]=s
env=np.exp(-tt*2.5)*np.minimum(1,tt/0.01)
save('down.wav',out*env*1.4)
# mechanical switch click: tight transient + metallic ping + body thunk
tt=t(0.18)
clk=rng.normal(0,1,len(tt))*np.exp(-tt*900)*0.9
clk+=np.sin(2*np.pi*2900*tt)*np.exp(-tt*120)*0.35+np.sin(2*np.pi*4700*tt)*np.exp(-tt*200)*0.15
clk+=np.sin(2*np.pi*140*tt)*np.exp(-tt*45)*0.6
save('click.wav',clk*0.9)
# power-up hum: rising electric tone with harmonics
tt=t(0.9); f=60+50*(1-np.exp(-tt*6)); ph=2*np.pi*np.cumsum(f)/SR
hum=sum(np.sin(k*ph)/k for k in (1,2,3,5))*np.minimum(1,tt/0.08)*np.exp(-np.maximum(0,tt-0.4)*4)*0.35
save('powerup.wav',hum)
# soft tick for the 1-beat micro cuts
tt=t(0.06); tick=rng.normal(0,1,len(tt))*np.exp(-tt*400)*0.5+np.sin(2*np.pi*1800*tt)*np.exp(-tt*150)*0.2
save('tick.wav',tick)
print('ok')
