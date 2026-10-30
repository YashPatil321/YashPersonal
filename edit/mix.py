import json, subprocess, re
A=json.load(open('audio.json')); C='/home/user/clips/'
def lufs(src,sin,dur):
    r=subprocess.run(['ffmpeg','-hide_banner','-ss',str(sin),'-t',str(dur),'-i',C+f'IMG_{src}.MOV','-vn','-af','highpass=f=90,afftdn=nf=-25,ebur128','-f','null','-'],capture_output=True,text=True).stderr
    return float(re.findall(r'I:\s+(-?[\d.]+) LUFS',r)[-1])
inputs=['-i',C+'music.mp3']; fc=[]; k=1; sp=[]; nat=[]
for (src,sin,T,dur) in A['SPEECH']:
    g=-15.5-lufs(src,sin,dur)
    inputs+=['-ss',str(sin),'-t',str(dur),'-i',C+f'IMG_{src}.MOV']
    fc.append(f'[{k}:a]aformat=channel_layouts=stereo:sample_rates=48000,highpass=f=90,lowpass=f=12000,afftdn=nf=-25,acompressor=threshold=-24dB:ratio=3:attack=8:release=160,volume={g:.2f}dB,afade=t=in:d=0.04,afade=t=out:st={dur-0.15:.2f}:d=0.15,adelay={int(T*1000)}:all=1[s{k}]'); sp.append(f'[s{k}]'); k+=1
    print(src,'gain',round(g,1))
for (src,sin,T,dur,gain) in A['NAT']:
    inputs+=['-ss',str(sin),'-t',str(dur),'-i',C+f'IMG_{src}.MOV']
    fc.append(f'[{k}:a]aformat=channel_layouts=stereo:sample_rates=48000,volume={gain},afade=t=in:d=0.03,afade=t=out:st={max(0,dur-0.12):.2f}:d=0.12,adelay={int(T*1000)}:all=1[n{k}]'); nat.append(f'[n{k}]'); k+=1
E=A['END']
fc.append(f"{''.join(sp)}amix=inputs={len(sp)}:normalize=0,apad,atrim=0:{E},asplit[sp][key]")
fc.append(f"{''.join(nat)}amix=inputs={len(nat)}:normalize=0,apad,atrim=0:{E}[nat]")
fc.append(f"[0:a]aformat=channel_layouts=stereo:sample_rates=48000,atrim=0:{E},volume=0.62,afade=t=out:st={E-2.6}:d=2.6[mus]")
fc.append("[mus][key]sidechaincompress=threshold=0.012:ratio=12:attack=20:release=600:knee=4,asplit[duck][dstem]")
fc.append("[duck][sp][nat]amix=inputs=3:normalize=0,alimiter=limit=0.93:level=false[out]")
subprocess.run(['ffmpeg','-v','error','-y',*inputs,'-filter_complex',';'.join(fc),'-map','[out]','-c:a','pcm_s16le','mix.wav','-map','[dstem]','-c:a','pcm_s16le','duck.wav'],check=True)
r=subprocess.run(['ffmpeg','-hide_banner','-i','mix.wav','-af','ebur128','-f','null','-'],capture_output=True,text=True).stderr
print('mix', re.findall(r'I:\s+(-?[\d.]+) LUFS',r)[-1], 'LUFS')
