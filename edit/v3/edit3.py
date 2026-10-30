import subprocess, json, os
os.chdir('/home/user/clips/build3'); C='/home/user/clips/'
FPS=60; b=json.load(open(C+'beats.json'))
def fr(t): return round(t*FPS)
TALK=b[40]; END=TALK+11.80+4.12+(8.94-0.35)-0.02
V=[('TITLE',0,0,2.74),('4732',0.90,2.74,6.36),('4738',0.0,6.36,7.94),('4732',5.68,7.94,b[0]),
   ('4764',0.00,b[0],b[2]),('4751',1.60,b[2],b[4]),('4766',2.00,b[4],b[6]),('4765',20.20,b[6],b[9]),
   ('4779',0.90,b[9],b[11]),('4778',0.90,b[11],b[13]),('4786',1.40,b[13],b[15]),('4787',0.40,b[15],b[16]),
   ('SWITCH',0,b[16],b[20]),('4788',9.20,b[20],b[21]),('4795',0.00,b[21],b[22]),('4801',0.90,b[22],b[24]),
   ('4803',0.60,b[24],b[25]),('4792',0.60,b[25],b[26]),('4899',0.60,b[26],b[27]),('4902',0.20,b[27],b[28]),
   ('4904',1.25,b[28],b[29]),('4908',0.10,b[29],b[30]),
   ('DESK',0,b[30],b[40]),
   ('4854',0.00,TALK,TALK+11.80),('4855',0.00,TALK+11.80,TALK+15.92),('4863',0.35,TALK+15.92,END)]
def run(cmd):
    r=subprocess.run(cmd,capture_output=True,text=True)
    if r.returncode: print(' '.join(cmd)); print(r.stderr[-2500:]); raise SystemExit(1)
ENC=['-c:v','libx264','-preset','veryfast','-crf','12','-pix_fmt','yuv420p','-an']
SC='scale=1920:1080:flags=lanczos'
segs=[]
for i,(src,sin,ts,te) in enumerate(V):
    N=fr(te)-fr(ts); out=f'seg{i:02d}.mp4'; segs.append(out)
    if os.path.exists(out) and not os.environ.get('FORCE'): continue
    if src=='TITLE':
        run(['ffmpeg','-v','error','-y','-i','title.mp4','-frames:v',str(N),*ENC,out])
    elif src=='SWITCH':
        # slow the three presses so each lands on a beat (b17, b18, b19); motion-interpolated to stay smooth
        knots=[(5.45,b[16]),(5.70,b[17]),(6.03,b[18]),(6.36,b[19]),(6.70,b[20])]
        parts=[]
        for j in range(4):
            (s0,t0),(s1,t1)=knots[j],knots[j+1]; k=(t1-t0)/(s1-s0); pn=fr(t1)-fr(t0); po=f'sw{j}.mp4'; parts.append(po)
            run(['ffmpeg','-v','error','-y','-ss',f'{s0-0.1:.3f}','-t',f'{s1-s0+0.3:.3f}','-i',C+'IMG_4788.MOV','-vf',
                 f'{SC},trim=start=0.1,setpts=(PTS-STARTPTS)*{k:.4f},minterpolate=fps={FPS}:mi_mode=mci:mc_mode=aobmc:me_mode=bidir:vsbmc=1,setsar=1','-frames:v',str(pn),*ENC,po])
        open('sw.txt','w').write(''.join(f"file '{p}'\n" for p in parts))
        run(['ffmpeg','-v','error','-y','-f','concat','-safe','0','-i','sw.txt','-c','copy',out])
    elif src=='DESK':
        c1,c2=b[33],b[37]; X=0.45
        la=(c1-ts)+X/2; lb=(c2-c1)+X; lc=(te-c2)+X/2
        pre=f'{SC},fps={FPS},settb=AVTB,setsar=1,format=yuv420p'
        fc=(f'[0:v]{pre}[a];[1:v]{pre}[b];[2:v]{pre}[c];[a][b]xfade=transition=fade:duration={X}:offset={la-X:.3f}[ab];'
            f'[ab][c]xfade=transition=fade:duration={X}:offset={la+lb-2*X:.3f}[v]')
        run(['ffmpeg','-v','error','-y','-ss','3.0','-t',f'{la:.3f}','-i',C+'IMG_4691.MOV','-ss','1.0','-t',f'{lb:.3f}','-i',C+'IMG_4679.MOV',
             '-ss','0.6','-t',f'{lc+0.1:.3f}','-i',C+'IMG_4684.MOV','-filter_complex',fc,'-map','[v]','-frames:v',str(N),*ENC,out])
    else:
        run(['ffmpeg','-v','error','-y','-ss',str(sin),'-i',C+f'IMG_{src}.MOV','-vf',f'{SC},fps={FPS},setsar=1','-frames:v',str(N),*ENC,out])
    print('seg',i,src,round(ts,3),round(te,3),N,flush=True)
open('concat.txt','w').write(''.join(f"file '{s}'\n" for s in segs))
print('total',sum(fr(te)-fr(ts) for _,_,ts,te in V),'expect',fr(END),'END',round(END,3),'TALK',round(TALK,3))
json.dump({'TALK':TALK,'END':END},open('timing.json','w'))
