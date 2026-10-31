import sys, subprocess, numpy as np
from PIL import Image, ImageFilter, ImageDraw, ImageFont
S=int(sys.argv[1]); OUT=sys.argv[2]; W,H,FPS=1920*S,1080*S,60; DUR=3.2; N=round(DUR*FPS)
shot=Image.open('mk_hero.png').convert('RGB')
bg=shot.resize((W//8,H//8),Image.LANCZOS).filter(ImageFilter.GaussianBlur(6)).resize((W,H),Image.LANCZOS)
bg=Image.fromarray((np.asarray(bg,np.float32)*0.42).astype(np.uint8))
ww=1300*S; bar=40*S; sh_h=int(ww*9/16); wh=sh_h+bar
win=Image.new('RGB',(ww,wh),(236,236,238)); d=ImageDraw.Draw(win)
for i,c in enumerate([(255,95,87),(255,189,46),(40,201,64)]):
    cx=22*S+i*20*S; d.ellipse((cx-6*S,bar//2-6*S,cx+6*S,bar//2+6*S),fill=c)
d.rounded_rectangle((ww//2-230*S,8*S,ww//2+230*S,bar-8*S),radius=12*S,fill=(255,255,255))
f=ImageFont.truetype(subprocess.run(['fc-match','-f','%{file}','Inter:medium'],capture_output=True,text=True).stdout,15*S)
d.text((ww//2,bar//2),'mantelkeep.com',font=f,fill=(90,90,95),anchor='mm')
win.paste(shot.resize((ww,sh_h),Image.LANCZOS),(0,bar))
mask=Image.new('L',(ww,wh),0); ImageDraw.Draw(mask).rounded_rectangle((0,0,ww,wh),radius=14*S,fill=255)
shadow=Image.new('L',(ww+140*S,wh+140*S),0); ImageDraw.Draw(shadow).rounded_rectangle((70*S,84*S,70*S+ww,84*S+wh),radius=14*S,fill=180)
shadow=shadow.filter(ImageFilter.GaussianBlur(30*S))
p=subprocess.Popen(['ffmpeg','-v','error','-y','-f','rawvideo','-pix_fmt','rgb24','-s',f'{W}x{H}','-r',str(FPS),'-i','-','-c:v','libx264','-preset','veryfast','-crf','12','-pix_fmt','yuv420p',OUT],stdin=subprocess.PIPE)
for i in range(N):
    t=i/FPS; z=1.0+0.04*(t/DUR); fr=bg.copy()
    sw,shh=int(shadow.width*z),int(shadow.height*z)
    fr.paste(Image.new('RGB',(sw,shh),(0,0,0)),((W-sw)//2,(H-shh)//2),shadow.resize((sw,shh)))
    w2,h2=int(ww*z),int(wh*z)
    fr.paste(win.resize((w2,h2),Image.LANCZOS),((W-w2)//2,(H-h2)//2),mask.resize((w2,h2)))
    p.stdin.write(fr.tobytes())
p.stdin.close(); p.wait(); print(OUT,N)
