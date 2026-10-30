import subprocess, json, os
os.chdir('/home/user/clips/build')
C='/home/user/clips/'
FPS=60
def fr(t): return round(t*FPS)
# ---- VIDEO EDL: (src, src_in, T_start, T_end, opts)
V=[
 ('TITLE',0,0.00,2.74,{}),
 ('4732',0.90,2.74,6.36,{}),
 ('4738',0.00,6.36,7.94,{}),
 ('4732',5.68,7.94,10.45,{}),
 ('4764',0.80,10.45,12.93,{}),
 ('4751',1.60,12.93,14.23,{}),
 ('4744',0.40,14.23,15.51,{'portrait':True}),
 ('4766',2.00,15.51,16.83,{}),
 ('4765',2.90,16.83,18.13,{}),
 ('4778',0.30,18.13,20.06,{}),
 ('4795',0.00,20.06,21.08,{}),
 ('4803',0.50,21.08,22.36,{}),
 ('4792',0.60,22.36,23.68,{}),
 ('4788',5.00,23.68,24.66,{}),
 ('4908',0.00,24.66,25.96,{}),
 ('4902',0.20,25.96,27.26,{}),
 ('4679',0.50,27.26,29.23,{}),
 ('4684',1.00,29.23,30.51,{}),
 ('4679',9.00,30.51,31.83,{}),
 ('4787',5.60,31.83,33.46,{}),
 ('4691',4.00,33.46,35.09,{}),
 ('4679',16.50,35.09,37.41,{}),
 ('4854',0.00,37.41,42.00,{}),
 ('4691',8.00,42.00,43.90,{}),
 ('4854',4.59,43.90,45.30,{}),
 ('4684',3.00,45.30,46.50,{}),
 ('4801',4.00,46.50,47.90,{}),
 ('4854',10.49,47.90,49.36,{}),
 ('4855',0.00,49.36,50.40,{}),
 ('4786',1.50,50.40,51.80,{}),
 ('4855',2.44,51.80,53.60,{}),
 ('4863',0.25,53.60,62.20,{}),
 ('END',0,62.20,65.20,{}),
]
# ---- AUDIO: nat sound (src, src_in, T, dur, gain)
NAT=[('4732',0.90,2.74,3.62,0.5),('4738',0,6.36,1.58,0.35),('4732',5.68,7.94,2.85,0.9),
     ('4764',0.8,10.45,2.48,0.25),('4751',1.6,12.93,1.3,0.3),('4744',0.4,14.23,1.28,0.3),
     ('4766',2.0,15.51,1.32,0.6),('4765',2.9,16.83,1.3,0.5),('4778',0.3,18.13,1.93,0.22),
     ('4803',0.5,21.08,1.28,0.15),('4792',0.6,22.36,1.32,0.25),('4908',0,24.66,1.3,0.2),('4902',0.2,25.96,1.3,0.22),
     ('4679',0.5,27.26,1.97,0.12),('4679',9.0,30.51,1.32,0.12),('4691',4.0,33.46,1.63,0.12)]
SPEECH=[('4823',0.0,18.60,8.60),('4827',0.0,27.50,4.40),('4827',4.60,32.08,5.35),
        ('4854',0.0,37.41,11.95),('4855',0.0,49.36,4.24),('4863',0.25,53.60,8.60)]
END_T=65.20
def run(cmd):
    r=subprocess.run(cmd,capture_output=True,text=True)
    if r.returncode: print(' '.join(cmd)); print(r.stderr[-2000:]); raise SystemExit(1)
segs=[]
for i,(src,sin,ts,te,o) in enumerate(V):
    n=fr(te)-fr(ts); out=f'seg{i:02d}.mp4'; segs.append(out)
    if os.path.exists(out) and not os.environ.get('FORCE'): continue
    if src=='TITLE':
        run(['ffmpeg','-v','error','-y','-i','title.mp4','-frames:v',str(n),'-c:v','libx264','-preset','veryfast','-crf','14','-pix_fmt','yuv420p','-an',out]); continue
    if src=='END':
        F='/home/user/clips/fonts/BebasNeue-Regular.ttf'
        vf=(f"drawtext=fontfile={F}:text='YASH PATIL':fontsize=120:fontcolor=white:x=(w-tw)/2:y=(h-th)/2-30:alpha='if(lt(t,0.4),0,min(1,(t-0.4)/0.6))*if(gt(t,2.4),max(0,(3-t)/0.6),1)',"
            f"drawtext=fontfile={F}:text='USC  IOVINE  AND  YOUNG  ACADEMY':fontsize=38:fontcolor=0xBBBBBB:x=(w-tw)/2:y=(h)/2+50:alpha='if(lt(t,0.8),0,min(1,(t-0.8)/0.6))*if(gt(t,2.4),max(0,(3-t)/0.6),1)'")
        run(['ffmpeg','-v','error','-y','-f','lavfi','-i',f'color=black:s=1920x1080:r={FPS}','-vf',vf,'-frames:v',str(n),'-c:v','libx264','-preset','veryfast','-crf','14','-pix_fmt','yuv420p',out]); continue
    if o.get('portrait'):
        geo='crop=2160:1215:0:780,scale=1920:1080:flags=lanczos'
    else:
        geo='scale=1920:1080:flags=lanczos'
    vf=f'{geo},fps={FPS},setsar=1'
    run(['ffmpeg','-v','error','-y','-ss',str(sin),'-i',C+f'IMG_{src}.MOV','-vf',vf,'-frames:v',str(n),'-an','-c:v','libx264','-preset','veryfast','-crf','14','-pix_fmt','yuv420p','-color_primaries','bt709','-color_trc','bt709','-colorspace','bt709',out])
    print('seg',i,src,n,flush=True)
open('concat.txt','w').write(''.join(f"file '{s}'\n" for s in segs))
json.dump({'NAT':NAT,'SPEECH':SPEECH,'END':END_T},open('audio.json','w'))
print('total frames',sum(fr(te)-fr(ts) for _,_,ts,te,_ in V), 'expect', fr(END_T))
