import subprocess, json, os
os.chdir('/home/user/clips/build5'); C='/home/user/clips/'
FPS=60; b=json.load(open(C+'beats.json'))
def fr(t): return round(t*FPS)
TALK=b[43]; END=TALK+11.80+4.12+8.30
V=[('TITLE',0,0,2.74),('4732',0.48,2.74,b[0]),
   ('4764',0.00,b[0],b[2]),('4738',0.55,b[2],b[4]),('4753',5.30,b[4],b[7]),('4765',20.20,b[7],b[10]),
   ('4778',0.20,b[10],b[13]),('4786',1.40,b[13],b[16]),
   ('SWITCH',0,b[16],b[20]),('4788',9.20,b[20],b[21]),('4795',0.20,b[21],b[22]),
   ('4792',0.30,b[22],b[24]),('4899',0.60,b[24],b[25]),('4902',0.20,b[25],b[26]),
   ('DESK',0,b[26],b[43]),
   ('4854',0.00,TALK,TALK+11.80),('4855',0.00,TALK+11.80,TALK+15.92),('4863',0.35,TALK+15.92,END)]
def run(cmd):
    r=subprocess.run(cmd,capture_output=True,text=True)
    if r.returncode: print(' '.join(cmd)); print(r.stderr[-2500:]); raise SystemExit(1)
ENC=['-c:v','libx264','-preset','veryfast','-crf','12','-pix_fmt','yuv420p','-an']
SC='scale=1920:1080:flags=lanczos'
MI=f'minterpolate=fps={FPS}:mi_mode=mci:mc_mode=aobmc:me_mode=bidir:vsbmc=1'
segs=[]
for i,(src,sin,ts,te) in enumerate(V):
    N=fr(te)-fr(ts); out=f'seg{i:02d}.mp4'; segs.append(out)
    if os.path.exists(out) and not os.environ.get('FORCE'): continue
    if src=='SWITCH':
        # each of the three presses lands on a beat (b17, b18, b19)
        knots=[(5.55,b[16]),(5.95,b[17]),(6.27,b[18]),(6.55,b[19]),(6.95,b[20])]; parts=[]
        for j in range(4):
            (s0,t0),(s1,t1)=knots[j],knots[j+1]; k=(t1-t0)/(s1-s0); pn=fr(t1)-fr(t0); po=f'sw{j}.mp4'; parts.append(po)
            run(['ffmpeg','-v','error','-y','-ss',f'{s0-0.1:.3f}','-t',f'{s1-s0+0.3:.3f}','-i',C+'IMG_4788.MOV','-vf',
                 f'{SC},trim=start=0.1,setpts=(PTS-STARTPTS)*{k:.4f},{MI},setsar=1','-frames:v',str(pn),*ENC,po])
        open('sw.txt','w').write(''.join(f"file '{p}'\n" for p in parts))
        run(['ffmpeg','-v','error','-y','-f','concat','-safe','0','-i','sw.txt','-c','copy',out])
    elif src=='DESK':
        # drawing -> coding -> code close-up -> drawing IYA on the board, soft dissolves on the beats
        X=0.4; cuts=[b[29],b[33],b[37]]
        clips=[('4691',3.0),('4679',1.0),('4684',0.6),('4701',None)]
        bounds=[ts]+cuts+[te]; lens=[]
        for j in range(4):
            L=bounds[j+1]-bounds[j]+(X/2 if j>0 else 0)+(X/2 if j<3 else 0); lens.append(L)
        inp=[]
        for (c,s0),L in zip(clips,lens):
            if s0 is None: s0=8.88-L
            inp+=['-ss',f'{s0:.3f}','-t',f'{L+0.1:.3f}','-i',C+f'IMG_{c}.MOV']
        pre=f'{SC},fps={FPS},settb=AVTB,setsar=1,format=yuv420p'
        fc=''.join(f'[{j}:v]{pre},trim=duration={lens[j]:.3f}[v{j}];' for j in range(4))
        off=lens[0]-X; fc+=f'[v0][v1]xfade=transition=fade:duration={X}:offset={off:.3f}[x1];'
        off+=lens[1]-X; fc+=f'[x1][v2]xfade=transition=fade:duration={X}:offset={off:.3f}[x2];'
        off+=lens[2]-X; fc+=f'[x2][v3]xfade=transition=fade:duration={X}:offset={off:.3f}[v]'
        run(['ffmpeg','-v','error','-y',*inp,'-filter_complex',fc,'-map','[v]','-frames:v',str(N),*ENC,out])
    else:
        run(['ffmpeg','-v','error','-y','-ss',str(sin),'-i',C+f'IMG_{src}.MOV','-vf',f'{SC},fps={FPS},setsar=1','-frames:v',str(N),*ENC,out])
    print('seg',i,src,round(ts,3),round(te,3),N,flush=True)
open('concat.txt','w').write(''.join(f"file '{s}'\n" for s in segs))
print('total',sum(fr(te)-fr(ts) for _,_,ts,te in V),'expect',fr(END),'END',round(END,3),'TALK',round(TALK,3))
json.dump({'TALK':TALK,'END':END},open('timing.json','w'))
