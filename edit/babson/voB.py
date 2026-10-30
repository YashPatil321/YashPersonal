import json, subprocess
V='/home/user/clips/babson/'; d=json.load(open(V+'vo.json'))
VOX='highpass=f=85,afftdn=nr=10:nf=-42:tn=1,equalizer=f=220:t=q:w=1.0:g=-3,equalizer=f=4200:t=q:w=0.9:g=3.5,equalizer=f=9500:t=q:w=0.8:g=1.5,deesser=i=0.35,acompressor=threshold=-21dB:ratio=2.6:attack=6:release=140:makeup=2'
# (name, recording, pieces [(src_in, src_out)], tempo, timeline start)
PLAN=[('vo1a','60',[(0.08,5.74)],1.0,3.70),('vo1b','60',[(7.30,10.88)],1.0,10.75),
      ('vo2','61',[(0.40,5.08),(5.30,6.72),(6.98,11.92)],1.04,15.65),('vo3','62',[(0.24,9.26)],1.04,26.50)]
words=[]; placed=[]
for name,rec,pieces,tempo,T0 in PLAN:
    fc=''.join(f'[0:a]atrim={a}:{b},asetpts=PTS-STARTPTS,afade=t=in:d=0.02,afade=t=out:st={b-a-0.03:.3f}:d=0.03[p{i}];' for i,(a,b) in enumerate(pieces))
    fc+=''.join(f'[p{i}]' for i in range(len(pieces)))+f'concat=n={len(pieces)}:v=0:a=1,aformat=channel_layouts=stereo,{VOX},atempo={tempo}[x]'
    subprocess.run(['ffmpeg','-v','error','-y','-i',V+f'rec{rec}.m4a','-filter_complex',fc,'-map','[x]','-ar','48000','-c:a','pcm_s24le',f'{name}_raw.wav'],check=True)
    r=subprocess.run(['ffmpeg','-hide_banner','-i',f'{name}_raw.wav','-af','loudnorm=I=-16:TP=-1.5:LRA=7:print_format=json','-f','null','-'],capture_output=True,text=True).stderr
    j=json.loads(r[r.rfind('{'):r.rfind('}')+1])
    ln=f"loudnorm=I=-16:TP=-1.5:LRA=7:measured_I={j['input_i']}:measured_TP={j['input_tp']}:measured_LRA={j['input_lra']}:measured_thresh={j['input_thresh']}:offset={j['target_offset']}:linear=true"
    subprocess.run(['ffmpeg','-v','error','-y','-i',f'{name}_raw.wav','-af',ln,'-ar','48000','-c:a','pcm_s24le',f'{name}.wav'],check=True)
    dur=float(subprocess.run(['ffprobe','-v','error','-show_entries','format=duration','-of','csv=p=0',f'{name}.wav'],capture_output=True,text=True).stdout)
    placed.append((name,T0,dur))
    # map word times from the recording onto the timeline
    off=0.0
    for a,b in pieces:
        for s in d[rec]:
            for ws,we,w in s['w']:
                if ws>=a-0.02 and we<=b+0.05: words.append((T0+(off+ws-a)/tempo,T0+(off+we-a)/tempo,w.strip()))
        off+=b-a
    print(name,'at',T0,'dur',round(dur,2),'ends',round(T0+dur,2))
json.dump({'placed':placed,'words':words},open('vo_place.json','w'))
