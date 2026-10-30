import json, subprocess, re
C='/home/user/clips/'; b=json.load(open(C+'beats.json')); T=json.load(open('timing.json')); TALK=T['TALK']; END=T['END']
SPEECH=[('4854',0.0,TALK,11.80),('4855',0.0,TALK+11.80,4.12),('4863',0.35,TALK+15.92,END-(TALK+15.92))]
VOX='highpass=f=85,afftdn=nr=10:nf=-42:tn=1,equalizer=f=220:t=q:w=1.0:g=-3,equalizer=f=4200:t=q:w=0.9:g=3.5,equalizer=f=9500:t=q:w=0.8:g=1.5,deesser=i=0.35,acompressor=threshold=-21dB:ratio=2.6:attack=6:release=140:makeup=2'
def measure(src,sin,dur):
    r=subprocess.run(['ffmpeg','-hide_banner','-ss',str(sin),'-t',str(dur),'-i',C+f'IMG_{src}.MOV','-vn','-af',VOX+',loudnorm=I=-16:TP=-1.5:LRA=7:print_format=json','-f','null','-'],capture_output=True,text=True).stderr
    j=json.loads(r[r.rfind('{'):r.rfind('}')+1]); return j
inputs=[]; fc=[]; k=0
def add(path,sin,dur,T0,chain,label):
    global k
    inputs.extend(['-ss',f'{sin:.3f}','-t',f'{dur:.3f}','-i',path])
    fc.append(f'[{k}:a]aformat=channel_layouts=stereo:sample_rates=48000,{chain},aresample=48000,adelay={int(round(T0*1000))}:all=1,apad,atrim=0:{END}[{label}{k}]')
    k+=1; return f'[{label}{k-1}]'
fade=lambda d,i=0.015,o=0.015: f'afade=t=in:d={i},afade=t=out:st={max(0,d-o):.3f}:d={o}'
# one continuous pass of the song, start to finish
mus=add(C+'music.mp3',0,END,0,'volume=0.62','m')
sp=[]
for src,sin,T0,dur in SPEECH:
    j=measure(src,sin,dur)
    ln=f"loudnorm=I=-16:TP=-1.5:LRA=7:measured_I={j['input_i']}:measured_TP={j['input_tp']}:measured_LRA={j['input_lra']}:measured_thresh={j['input_thresh']}:offset={j['target_offset']}:linear=true"
    subprocess.run(['ffmpeg','-v','error','-y','-ss',str(sin),'-t',str(dur),'-i',C+f'IMG_{src}.MOV','-vn','-af',f'aformat=channel_layouts=stereo,{VOX},{ln},{fade(dur,0.03,0.1)}','-ar','48000','-c:a','pcm_s24le',f'vox_{src}.wav'],check=True)
    sp.append(add(f'vox_{src}.wav',0,dur,T0,'anull','s'))
# natural sound only from clips with no voices in them
NAT=[('4732',0.48,2.74,7.85,0.55),('4738',0.55,b[2],b[4]-b[2],0.35),('4753',5.30,b[4],b[7]-b[4]+0.15,0.9),
     ('4766',2.05,b[7]+0.05,1.5,0.35),
     ('4778',0.2,b[10],b[13]-b[10],0.85),('4786',1.30,b[13],b[16]-b[13],0.4),('4786',4.60,b[16],3.6,1.05),
     ('4801',0.5,b[24],b[26]-b[24],0.22),('4803',0.6,b[26],b[27]-b[26],0.2),('4792',0.3,b[27],b[29]-b[27],0.35),
     ('4899',0.6,b[29],b[30]-b[29],0.4),('4902',0.2,b[30],b[31]-b[30],0.3),('4908',0.2,b[33],b[34]-b[33],0.25)]
nat=[add(C+f'IMG_{s}.MOV',a,d,T0,f'volume={g},{fade(d,0.02,0.35 if (s=="4786" and a>4) else 0.06)}','n') for s,a,T0,d,g in NAT]
SFX=[('impact',0.12,0.55),('riser',b[10]-1.4,0.35),('impact',b[10],0.7),
     ('switch',b[18],0.8),('switch',b[19],0.8),('switch',b[20],0.9),('powerup',b[21],0.5),('switch',b[22]+0.05,0.55),
     ('whoosh',b[34]-0.5,0.25),('down',b[34],0.4)]
fx=[add(f'{s}.wav',0,4,T0,f'volume={g}','f') for s,T0,g in SFX]
L=lambda xs: ''.join(xs)
fc.append(f'{L(sp)}amix=inputs={len(sp)}:normalize=0,asplit[sp][key]')
# chill desk: ease the music down a little, then duck hard under the voice
d0,d1=b[34],b[42]
fc.append(f"{mus}volume='1-0.3*clip((t-{d0})/0.8,0,1)*(1-clip((t-{d1})/0.8,0,1))':eval=frame[mv]")
fc.append('[mv][key]sidechaincompress=threshold=0.008:ratio=16:attack=15:release=650:knee=5[duck]')
fc.append(f'[duck][sp]{L(nat)}{L(fx)}amix=inputs={2+len(nat)+len(fx)}:normalize=0,alimiter=limit=0.93:level=false,afade=t=out:st={END-1.2:.3f}:d=1.2[out]')
subprocess.run(['ffmpeg','-v','error','-y',*inputs,'-filter_complex',';'.join(fc),'-map','[out]','-t',f'{END:.3f}','-c:a','pcm_s16le','mix.wav'],check=True)
for a,c in ((0,10.4),(10.45,16.1),(16.2,30.1),(30.2,34.7),(34.8,END)):
    r=subprocess.run(['ffmpeg','-hide_banner','-ss',str(a),'-to',str(c),'-i','mix.wav','-af','ebur128','-f','null','-'],capture_output=True,text=True).stderr
    print(f'{a}-{c:.1f}', re.findall(r'I:\s+(-?[\d.]+) LUFS',r)[-1])
