#!/bin/bash
# usage: finalize.sh <builddir> <out.mp4> <scale 1|2>
set -e
cd "$1"; S=$3; W=$((1920*S)); H=$((1080*S)); BAR=$((138*S))
E=$(python3 -c "import json;print(json.load(open('timing.json'))['END'])")
read D SH < <(python3 -c "import json;b=json.load(open('/home/user/clips/beats.json'));print(b[0],b[10])")
Z="1+0.06*(gte(t,$D)*exp(-(t-$D)*7)+gte(t,$SH)*exp(-(t-$SH)*7))"
F="0.32*(gte(t,$D)*exp(-(t-$D)*24)+gte(t,$SH)*exp(-(t-$SH)*24))"
G="eq=contrast=1.04:brightness=0.012:saturation=1.05,colorbalance=rs=-0.025:bs=0.03:rh=0.03:gh=0.008:bh=-0.02,curves=master='0/0.02 0.5/0.51 1/0.99',vignette=angle=PI/7"
if [ $S = 2 ]; then Q="-preset medium -crf 18 -maxrate 40M -bufsize 80M -level 5.2"; else Q="-preset slow -crf 16 -maxrate 22M -bufsize 44M -level 4.2"; fi
ffmpeg -v error -y -f concat -safe 0 -i concat.txt -i mix.wav -filter_complex \
"[0:v]scale=w='trunc($W*($Z)/2)*2':h='trunc($H*($Z)/2)*2':eval=frame:flags=lanczos,crop=$W:$H:(iw-$W)/2:(ih-$H)/2,$G,eq=brightness='$F':eval=frame,noise=alls=3:allf=t,format=yuv420p,drawbox=x=0:y=0:w=iw:h=$BAR:color=black:t=fill,drawbox=x=0:y=ih-$BAR:w=iw:h=$BAR:color=black:t=fill,subtitles=subs.ass,fade=t=out:st=$(python3 -c "print($E-0.7)"):d=0.7,format=yuv420p[v]" \
-map "[v]" -map 1:a -c:v libx264 $Q -r 60 -profile:v high -c:a aac -b:a 320k -movflags +faststart -shortest "$2"
ffprobe -v error -show_entries format=duration,size -of compact "$2"
