import json, subprocess, re
C='/home/user/clips/'; b=json.load(open(C+'beats.json')); T=json.load(open('timing.json')); TALK=T['TALK']; END=T['END']
T1=TALK+7.65; T2=T1+4.62; T3=T2+5.05
SPEECH=[('4867',0.55,TALK,7.65),('4885',0.0,T1,4.62),('4886',0.0,T2,5.05),('4894',0.15,T3,END-T3)]
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
VP=json.load(open('vo_place.json'))['placed']
for name,T0,dur in VP: sp.append(add(f'{name}.wav',0,dur,T0,'anull','s'))
# natural sound only from clips with no voices in them
NAT=[('4732',8.02,b[0]-0.163,0.45,0.9),('4738',0.55,b[2],b[4]-b[2],0.4),('4753',5.30,b[4],b[7]-b[4]+0.15,0.9),
     ('4778',0.2,b[10],b[13]-b[10],0.55),('4786',1.40,b[13],b[15]-b[13],0.4),('4786',4.60,b[15],3.4,0.6),
     ('4795',1.27,b[21]-0.15,b[22]-b[21]+0.15,0.6),('4792',0.3,b[22],b[24]-0.25-b[22],0.3),('4899',0.61,b[24]-0.25,0.55,0.75),('4902',0.28,b[25]-0.2,0.716,0.6)]
nat=[add(C+f'IMG_{s}.MOV',a,d,T0,f'volume={g},{fade(d,0.02,0.35 if (s=="4786" and a>4) else 0.06)}','n') for s,a,T0,d,g in NAT]
SFX=[('snap',b[2]+0.47-0.09,0.55),('impact',b[10],0.6),
     ('switch',b[17],0.8),('switch',b[18],0.8),('switch',b[19],0.9),('powerup',b[20],0.5),('switch',b[21],0.7),('thump',b[24],0.5),('thump',b[25],0.45)]
fx=[add(f'{s}.wav',0,4,T0,f'volume={g}','f') for s,T0,g in SFX]
L=lambda xs: ''.join(xs)
fc.append(f'{L(sp)}amix=inputs={len(sp)}:normalize=0,asplit[sp][key]')
# chill desk: ease the music down a little, then duck hard under the voice
d0,d1=b[26],b[44]
fc.append(f"{mus}volume='1-0.3*clip((t-{d0})/0.8,0,1)*(1-clip((t-{d1})/0.8,0,1))':eval=frame[mv]")
fc.append('[mv][key]sidechaincompress=threshold=0.008:ratio=16:attack=15:release=650:knee=5[duck]')
fc.append(f'[duck][sp]{L(nat)}{L(fx)}amix=inputs={2+len(nat)+len(fx)}:normalize=0,alimiter=limit=0.93:level=false,afade=t=out:st={END-1.2:.3f}:d=1.2[out]')
subprocess.run(['ffmpeg','-v','error','-y',*inputs,'-filter_complex',';'.join(fc),'-map','[out]','-t',f'{END:.3f}','-c:a','pcm_s16le','mix.wav'],check=True)
for a,c in ((0,10.4),(10.45,16.1),(16.2,25.4),(25.5,35.8),(35.9,END)):
    r=subprocess.run(['ffmpeg','-hide_banner','-ss',str(a),'-to',str(c),'-i','mix.wav','-af','ebur128','-f','null','-'],capture_output=True,text=True).stderr
    print(f'{a}-{c:.1f}', re.findall(r'I:\s+(-?[\d.]+) LUFS',r)[-1])
