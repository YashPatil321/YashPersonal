import subprocess, json, os
os.chdir('/home/user/clips/build2'); C='/home/user/clips/'
FPS=60; B=0.32508; D=10.45
def n(k): return round(D+k*B,3)
def fr(t): return round(t*FPS)
SHARP='unsharp=5:5:0.55:5:5:0'
TALK=33.14
V=[('TITLE',0,0,2.74),('4732',0.90,2.74,6.36),('4738',0.0,6.36,7.94),('4732',5.68,7.94,n(0)),
   ('4764',0.10,n(0),n(3)),('4751',1.60,n(3),n(7)),('4766',2.00,n(7),n(11)),('4765',13.85,n(11),n(16)),
   ('4778',0.20,n(16),n(22)),('4779',1.30,n(22),n(24)),('4786',4.60,n(24),n(28)),('4787',0.30,n(28),n(30)),
   ('4788',5.70-B,n(30),n(34)),('4788',9.20,n(34),n(36)),('4795',0.10,n(36),n(38)),('4801',1.00,n(38),n(40)),
   ('4803',0.80,n(40),n(42)),('4792',0.60,n(42),n(44)),('4899',0.75,n(44),n(45)),('4902',0.30,n(45),n(46)),
   ('4904',1.20,n(46),n(47)),('4908',0.20,n(47),n(48)),
   ('DESK',0,n(48),TALK),
   ('4854',0.00,TALK,TALK+11.85),('4855',0.00,TALK+11.85,TALK+16.00),('4863',0.30,TALK+16.00,57.18),
   ('END',0,57.18,59.40)]
def run(cmd):
    r=subprocess.run(cmd,capture_output=True,text=True)
    if r.returncode: print(' '.join(cmd)); print(r.stderr[-2500:]); raise SystemExit(1)
ENC=['-c:v','libx264','-preset','veryfast','-crf','12','-pix_fmt','yuv420p','-an']
segs=[]
for i,(src,sin,ts,te) in enumerate(V):
    N=fr(te)-fr(ts); out=f'seg{i:02d}.mp4'; segs.append(out)
    if os.path.exists(out) and not os.environ.get('FORCE'): continue
    if src=='TITLE':
        run(['ffmpeg','-v','error','-y','-i','title.mp4','-frames:v',str(N),*ENC,out])
    elif src=='END':
        F=C+'fonts/BebasNeue-Regular.ttf'
        a1="if(lt(t,0.05),0,min(1,(t-0.05)/0.25))*if(gt(t,1.5),max(0,(2.2-t)/0.7),1)"
        a2="if(lt(t,0.35),0,min(1,(t-0.35)/0.4))*if(gt(t,1.5),max(0,(2.2-t)/0.7),1)"
        vf=(f"drawtext=fontfile={F}:text='YASH PATIL':fontsize=150:fontcolor=white:x=(w-tw)/2:y=(h-th)/2-30:alpha='{a1}',"
            f"drawtext=fontfile={F}:text='FIGHT ON':fontsize=44:fontcolor=0xC9A227:x=(w-tw)/2:y=h/2+65:alpha='{a2}'")
        run(['ffmpeg','-v','error','-y','-f','lavfi','-i',f'color=black:s=1920x1080:r={FPS}','-vf',vf,'-frames:v',str(N),*ENC,out])
    elif src=='DESK':
        # chill: three clips, each used once, soft 0.4s dissolves on the quiet-bed hits
        c1,c2=28.67,31.27; X=0.4
        la=(c1-ts)+X/2; lb=(c2-c1)+X; lc=(te-c2)+X/2
        pre=f'scale=1920:1080:flags=lanczos,{SHARP},fps={FPS},settb=AVTB,setsar=1,format=yuv420p'
        fc=(f'[0:v]{pre}[a];[1:v]{pre}[b];[2:v]{pre}[c];'
            f'[a][b]xfade=transition=fade:duration={X}:offset={la-X:.3f}[ab];'
            f'[ab][c]xfade=transition=fade:duration={X}:offset={la+lb-X-X:.3f}[v]')
        run(['ffmpeg','-v','error','-y','-ss','3.0','-t',f'{la:.3f}','-i',C+'IMG_4691.MOV','-ss','1.0','-t',f'{lb:.3f}','-i',C+'IMG_4679.MOV',
             '-ss','0.8','-t',f'{lc+0.1:.3f}','-i',C+'IMG_4684.MOV','-filter_complex',fc,'-map','[v]','-frames:v',str(N),*ENC,out])
    else:
        vf=f'scale=1920:1080:flags=lanczos,{SHARP},fps={FPS},setsar=1'
        run(['ffmpeg','-v','error','-y','-ss',str(sin),'-i',C+f'IMG_{src}.MOV','-vf',vf,'-frames:v',str(N),*ENC,out])
    print('seg',i,src,N,flush=True)
open('concat.txt','w').write(''.join(f"file '{s}'\n" for s in segs))
print('total',sum(fr(te)-fr(ts) for _,_,ts,te in V),'expect',fr(59.40))
json.dump({'B':B,'D':D,'TALK':TALK,'n':{k:n(k) for k in range(0,49)}},open('timing.json','w'))
