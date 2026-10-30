import json, subprocess, re
T=json.load(open('timing.json')); n=lambda k: T['n'][str(k)]; TALK=T['TALK']; C='/home/user/clips/'; END=59.40
MUS=C+'music.mp3'
def lufs(src,sin,dur):
    r=subprocess.run(['ffmpeg','-hide_banner','-ss',str(sin),'-t',str(dur),'-i',C+f'IMG_{src}.MOV','-vn','-af','highpass=f=90,afftdn=nf=-25,ebur128','-f','null','-'],capture_output=True,text=True).stderr
    return float(re.findall(r'I:\s+(-?[\d.]+) LUFS',r)[-1])
inputs=[]; fc=[]; k=0
def add(path,sin,dur,T0,chain,label):
    global k
    inputs.extend(['-ss',f'{sin:.3f}','-t',f'{dur:.3f}','-i',path])
    fc.append(f'[{k}:a]aformat=channel_layouts=stereo:sample_rates=48000,{chain},adelay={int(round(T0*1000))}:all=1,apad,atrim=0:{END}[{label}{k}]')
    k+=1; return f'[{label}{k-1}]'
fade=lambda d,i=0.015,o=0.015: f'afade=t=in:d={i},afade=t=out:st={max(0,d-o):.3f}:d={o}'
# music: loud opening, then quiet bed looped on its 2.6s pattern, drop returns after "Fight on"
m1=[add(MUS,0,26.40,0,f'volume=0.62,afade=t=out:st=26.0:d=0.4','m')]
bed=[add(MUS,0,7.90,25.93,f'volume=1.15,{fade(7.90,0.01)}','b')]
for T0 in (33.83,39.03,44.23): bed.append(add(MUS,2.70,5.20,T0,f'volume=1.15,{fade(5.20)}','b'))
bed.append(add(MUS,2.70,7.72,49.43,f'volume=1.15,{fade(7.72)}','b'))
drop=[add(MUS,10.42,2.6,57.15,f'volume=0.62,afade=t=in:d=0.01,afade=t=out:st=1.0:d=1.6','m')]
# speech (on camera only)
sp=[]
for src,sin,T0,dur in (('4854',0.0,TALK,11.85),('4855',0.0,TALK+11.85,4.15),('4863',0.30,TALK+16.0,8.0)):
    g=-15.5-lufs(src,sin,dur)
    sp.append(add(C+f'IMG_{src}.MOV',sin,dur,T0,f'highpass=f=90,lowpass=f=12000,afftdn=nf=-25,acompressor=threshold=-24dB:ratio=3:attack=8:release=160,volume={g:.2f}dB,{fade(dur,0.03,0.12)}','s'))
# natural sound
NAT=[('4732',0.90,2.74,3.62,0.5),('4738',0,6.36,1.58,0.35),('4732',5.68,7.94,2.85,0.9),
     ('4764',0.10,n(0),0.975,0.25),('4751',1.6,n(3),1.3,0.3),('4766',2.0,n(7),1.3,0.6),('4765',13.85,n(11),1.625,0.6),
     ('4778',0.2,n(16),1.95,0.8),('4779',1.3,n(22),0.65,0.45),('4786',4.60,n(24),3.3,1.1),
     ('4801',1.0,n(38),0.65,0.2),('4803',0.8,n(40),0.65,0.2),('4792',0.6,n(42),0.65,0.35),('4899',0.75,n(44),0.33,0.4),
     ('4902',0.3,n(45),0.33,0.3),('4908',0.2,n(47),0.33,0.25),
     ('4691',3.0,n(48),2.6,0.22),('4679',1.0,28.47,2.8,0.25)]
nat=[add(C+f'IMG_{s}.MOV',a,d,T0,f'volume={g},{fade(d,0.02,0.25 if s=="4786" else 0.06)}','n') for s,a,T0,d,g in NAT]
# sound design
SFX=[('boom',0.12,0.7),('whoosh',n(0)-0.7,0.35),('whoosh',n(16)-0.7,0.55),('boom',n(16),0.85),
     ('click',n(31),0.85),('click',n(32),0.85),('click',n(33),0.95),('powerup',n(34),0.6),('click',n(36),0.7),
     ('tick',n(44),0.35),('tick',n(45),0.35),('tick',n(46),0.35),('tick',n(47),0.35),
     ('down',n(48),0.6),('boom',57.18,0.8)]
fx=[add(f'{s}.wav',0,4,T0,f'volume={g}','f') for s,T0,g in SFX]
L=lambda xs: ''.join(xs)
fc.append(f'{L(sp)}amix=inputs={len(sp)}:normalize=0,asplit[sp][key]')
fc.append(f'{L(bed)}amix=inputs={len(bed)}:normalize=0[bedr]')
fc.append('[bedr][key]sidechaincompress=threshold=0.012:ratio=12:attack=20:release=600:knee=4[bed]')
fc.append(f'{L(m1+drop)}[bed][sp]{L(nat)}{L(fx)}amix=inputs={len(m1+drop)+2+len(nat)+len(fx)}:normalize=0,alimiter=limit=0.93:level=false[out]')
subprocess.run(['ffmpeg','-v','error','-y',*inputs,'-filter_complex',';'.join(fc),'-map','[out]','-t',str(END),'-c:a','pcm_s16le','mix.wav'],check=True)
for a,b in ((0,10.4),(10.45,15.6),(15.7,26),(26.1,33.1),(33.2,57.1),(57.2,59.4)):
    r=subprocess.run(['ffmpeg','-hide_banner','-ss',str(a),'-to',str(b),'-i','mix.wav','-af','ebur128','-f','null','-'],capture_output=True,text=True).stderr
    print(f'{a}-{b}', re.findall(r'I:\s+(-?[\d.]+) LUFS',r)[-1])
