import sys, subprocess, numpy as np
from PIL import Image, ImageFilter, ImageDraw
S=int(sys.argv[1]); OUT=sys.argv[2]; W,H,FPS=1920*S,1080*S,60; DUR=1.15; N=round(DUR*FPS)
src=Image.open('reg.png').convert('RGB').crop((0,0,596,410))
# background: the red header, blurred and darkened, filling the frame
bg=src.crop((0,0,596,290)).resize((W,H),Image.LANCZOS).filter(ImageFilter.GaussianBlur(40*S))
bg=Image.fromarray((np.asarray(bg,np.float32)*0.45).astype(np.uint8))
ch=int(700*S); cw=int(src.width*ch/src.height)
card=src.resize((cw,ch),Image.LANCZOS).filter(ImageFilter.UnsharpMask(radius=2*S,percent=60,threshold=2))
mask=Image.new('L',(cw,ch),0); ImageDraw.Draw(mask).rounded_rectangle((0,0,cw,ch),radius=18*S,fill=255)
shadow=Image.new('L',(cw+120*S,ch+120*S),0); ImageDraw.Draw(shadow).rounded_rectangle((60*S,70*S,60*S+cw,70*S+ch),radius=18*S,fill=170)
shadow=shadow.filter(ImageFilter.GaussianBlur(28*S))
p=subprocess.Popen(['ffmpeg','-v','error','-y','-f','rawvideo','-pix_fmt','rgb24','-s',f'{W}x{H}','-r',str(FPS),'-i','-','-c:v','libx264','-preset','veryfast','-crf','12','-pix_fmt','yuv420p',OUT],stdin=subprocess.PIPE)
for i in range(N):
    t=i/FPS; z=1.0+0.045*(t/DUR)            # slow push-in
    f=bg.copy()
    sw,sh=int(shadow.width*z),int(shadow.height*z); sh_=shadow.resize((sw,sh))
    f.paste(Image.new('RGB',(sw,sh),(0,0,0)),((W-sw)//2,(H-sh)//2),sh_)
    cw2,ch2=int(cw*z),int(ch*z); c2=card.resize((cw2,ch2),Image.LANCZOS); m2=mask.resize((cw2,ch2))
    f.paste(c2,((W-cw2)//2,(H-ch2)//2),m2)
    p.stdin.write(f.tobytes())
p.stdin.close(); p.wait(); print(OUT,N)
