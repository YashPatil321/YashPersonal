/* Wave visualizers. Each draws one frame into a 2D canvas.
 * draw(ctx, w, h, A, pal, t, st, o)
 *   A   audio frame (bins[64], wave[128], level, bass, mid, treble, beat), all 0..1
 *   pal 3 rgb stops, use Wave.mix(pal, x, alpha)
 *   t   seconds, st per-instance state object, o options {density, glow, dpr, hole}
 *       hole: {x, y, r} keeps the centre clear for a cover in full screen.
 */
'use strict';

(function () {
  const { mix } = Wave;
  const TAU = Math.PI * 2;

  /** Resample 64 bins to n bars, weighting low end less so bars spread evenly across the range. */
  function sample(bins, n) {
    const out = new Array(n);
    for (let i = 0; i < n; i++) {
      const x = (i / Math.max(1, n - 1)) * (bins.length - 1);
      const i0 = Math.floor(x), f = x - i0;
      const v = bins[i0] * (1 - f) + (bins[Math.min(bins.length - 1, i0 + 1)] || 0) * f;
      out[i] = Math.min(1, v * (0.85 + 0.35 * (i / n)));
    }
    return out;
  }
  const barCount = (w, o, base = 56) => Math.max(12, Math.round(base * (0.4 + o.density * 1.2) * Math.min(1.6, w / (900 * o.dpr) + 0.4)));

  function glowStroke(ctx, o, draw, width, color) {
    if (o.glow > 0.02) {
      ctx.save();
      ctx.globalCompositeOperation = 'lighter';
      ctx.globalAlpha = 0.18 * o.glow;
      ctx.lineWidth = width * 5;
      ctx.strokeStyle = color;
      draw();
      ctx.globalAlpha = 0.35 * o.glow;
      ctx.lineWidth = width * 2.4;
      draw();
      ctx.restore();
    }
    ctx.lineWidth = width;
    ctx.strokeStyle = color;
    draw();
  }

  function roundBar(ctx, x, y, w, h, r) {
    if (!(w > 0) || !(h > 0)) return;
    r = Math.max(0, Math.min(r, w / 2, h / 2));
    ctx.beginPath();
    if (ctx.roundRect) ctx.roundRect(x, y, w, h, r);
    else ctx.rect(x, y, w, h);
    ctx.fill();
  }

  const V = {};

  // ------------------------------------------------------------------ Bars
  V.bars = {
    name: 'Bars',
    draw(ctx, w, h, A, pal, t, st, o) {
      const n = barCount(w, o);
      const vals = sample(A.bins, n);
      st.peaks = st.peaks && st.peaks.length === n ? st.peaks : new Array(n).fill(0);
      const gap = Math.max(0.5, (w / n) * 0.28), bw = Math.max(1, w / n - gap);
      const base = h * 0.78, maxH = base * 0.94;
      const grad = ctx.createLinearGradient(0, 0, w, 0);
      grad.addColorStop(0, mix(pal, 0)); grad.addColorStop(0.5, mix(pal, 0.5)); grad.addColorStop(1, mix(pal, 1));
      for (let i = 0; i < n; i++) {
        const v = vals[i], bh = Math.max(2 * o.dpr, v * maxH), x = i * (bw + gap) + gap / 2;
        st.peaks[i] = Math.max(v, st.peaks[i] - 0.012);
        ctx.fillStyle = grad;
        if (o.glow > 0.02) {
          ctx.save(); ctx.globalCompositeOperation = 'lighter'; ctx.globalAlpha = 0.22 * o.glow * (0.4 + v);
          roundBar(ctx, x - bw * 0.35, base - bh - bw * 0.3, bw * 1.7, bh + bw * 0.3, bw); ctx.restore();
        }
        roundBar(ctx, x, base - bh, bw, bh, bw * 0.45);
        // reflection
        ctx.save(); ctx.globalAlpha = 0.18; roundBar(ctx, x, base + 3 * o.dpr, bw, bh * 0.28, bw * 0.45); ctx.restore();
        // falling peak cap
        ctx.fillStyle = mix(pal, i / n, 0.9);
        roundBar(ctx, x, base - st.peaks[i] * maxH - 6 * o.dpr, bw, 2.5 * o.dpr, 2);
      }
    },
  };

  // ------------------------------------------------------------------ Mirror
  V.mirror = {
    name: 'Mirror',
    draw(ctx, w, h, A, pal, t, st, o) {
      const n = barCount(w, o, 48);
      const vals = sample(A.bins, n);
      const half = Math.ceil(n / 2);
      const cy = h / 2, step = w / (half * 2), bw = step * 0.62;
      for (let k = 0; k < half; k++) {
        const v = vals[k * 2] || 0, bh = Math.max(2 * o.dpr, v * h * 0.44);
        for (const side of [-1, 1]) {
          const x = w / 2 + side * (k + 0.5) * step - bw / 2;
          const c = mix(pal, k / half, 0.95);
          ctx.fillStyle = c;
          if (o.glow > 0.02) {
            ctx.save(); ctx.globalCompositeOperation = 'lighter'; ctx.globalAlpha = 0.2 * o.glow;
            roundBar(ctx, x - bw * 0.4, cy - bh - bw * 0.4, bw * 1.8, bh * 2 + bw * 0.8, bw); ctx.restore();
          }
          roundBar(ctx, x, cy - bh, bw, bh * 2, bw / 2);
        }
      }
    },
  };

  // ------------------------------------------------------------------ Blocks (LED meter)
  V.blocks = {
    name: 'Blocks',
    draw(ctx, w, h, A, pal, t, st, o) {
      const n = Math.max(10, Math.round(barCount(w, o, 36) * 0.7));
      const vals = sample(A.bins, n);
      const rows = Math.max(8, Math.round(16 * (0.6 + o.density * 0.6)));
      const cw = w / n, ch = (h * 0.86) / rows, pad = Math.max(1.5 * o.dpr, cw * 0.14);
      for (let i = 0; i < n; i++) {
        const lit = Math.round(vals[i] * rows);
        for (let r = 0; r < rows; r++) {
          const on = r < lit;
          const y = h * 0.93 - (r + 1) * ch;
          ctx.fillStyle = on ? mix(pal, r / rows, 1) : 'rgba(255,255,255,0.045)';
          if (on && o.glow > 0.02 && r === lit - 1) {
            ctx.save(); ctx.globalCompositeOperation = 'lighter'; ctx.globalAlpha = 0.35 * o.glow;
            roundBar(ctx, i * cw, y - pad, cw, ch + pad * 2, 4 * o.dpr); ctx.restore();
          }
          roundBar(ctx, i * cw + pad, y + pad / 2, cw - pad * 2, ch - pad, 2.5 * o.dpr);
        }
      }
    },
  };

  // ------------------------------------------------------------------ Ring
  V.ring = {
    name: 'Ring',
    draw(ctx, w, h, A, pal, t, st, o) {
      const cx = o.hole ? o.hole.x : w / 2, cy = o.hole ? o.hole.y : h / 2;
      const base = o.hole ? o.hole.r * 1.08 : Math.min(w, h) * 0.24 * (1 + A.bass * 0.06);
      const n = Math.round(90 * (0.5 + o.density));
      const vals = sample(A.bins, Math.ceil(n / 2));
      st.rot = (st.rot || 0) + 0.0015 + A.mid * 0.004;
      const maxL = Math.min(w, h) * (o.hole ? 0.2 : 0.22);
      ctx.save();
      ctx.translate(cx, cy);
      ctx.rotate(st.rot);
      ctx.lineCap = 'round';
      for (let i = 0; i < n; i++) {
        const k = i < n / 2 ? i : n - 1 - i; // symmetric
        const v = vals[k] || 0;
        const a = (i / n) * TAU;
        const len = 3 * o.dpr + v * maxL;
        const c = mix(pal, k / (n / 2));
        const x0 = Math.cos(a) * base, y0 = Math.sin(a) * base;
        const x1 = Math.cos(a) * (base + len), y1 = Math.sin(a) * (base + len);
        const lw = Math.max(2 * o.dpr, ((TAU * base) / n) * 0.5);
        glowStroke(ctx, o, () => { ctx.beginPath(); ctx.moveTo(x0, y0); ctx.lineTo(x1, y1); ctx.stroke(); }, lw, c);
      }
      // inner pulse
      ctx.globalCompositeOperation = 'lighter';
      const g = ctx.createRadialGradient(0, 0, base * 0.5, 0, 0, base * 1.05);
      g.addColorStop(0, 'rgba(0,0,0,0)');
      g.addColorStop(1, mix(pal, 0.5, 0.12 + 0.35 * A.beat * o.glow));
      ctx.fillStyle = g;
      ctx.beginPath(); ctx.arc(0, 0, base * 1.05, 0, TAU); ctx.fill();
      ctx.restore();
    },
  };

  // ------------------------------------------------------------------ Waveform
  V.waveform = {
    name: 'Waveform',
    draw(ctx, w, h, A, pal, t, st, o) {
      const N = A.wave.length;
      const layers = 3;
      for (let L = layers - 1; L >= 0; L--) {
        const amp = h * (0.32 - L * 0.07) * (0.6 + A.level * 0.8);
        const shift = L * 6;
        const grad = ctx.createLinearGradient(0, 0, w, 0);
        grad.addColorStop(0, mix(pal, 0, 0.9 - L * 0.25)); grad.addColorStop(0.5, mix(pal, 0.5, 0.9 - L * 0.25)); grad.addColorStop(1, mix(pal, 1, 0.9 - L * 0.25));
        const draw = () => {
          ctx.beginPath();
          for (let i = 0; i <= N; i++) {
            const x = (i / N) * w;
            const env = Math.sin((i / N) * Math.PI); // taper the ends
            const v = A.wave[(i + shift) % N] * env;
            const y = h / 2 + v * amp + Math.sin(i * 0.12 + t * (1 + L)) * 4 * o.dpr * env;
            if (i === 0) ctx.moveTo(x, y);
            else {
              const px = ((i - 0.5) / N) * w;
              ctx.quadraticCurveTo(px, y, x, y);
            }
          }
          ctx.stroke();
        };
        ctx.lineJoin = 'round';
        glowStroke(ctx, o, draw, (3 - L) * o.dpr, grad);
      }
    },
  };

  // ------------------------------------------------------------------ Aurora
  V.aurora = {
    name: 'Aurora',
    draw(ctx, w, h, A, pal, t, st, o) {
      ctx.save();
      ctx.globalCompositeOperation = 'lighter';
      const bands = 5;
      for (let b = 0; b < bands; b++) {
        const energy = A.bins[Math.floor((b / bands) * 40)] || 0;
        const yBase = h * (0.35 + b * 0.09);
        const amp = h * (0.08 + energy * 0.22);
        const grad = ctx.createLinearGradient(0, yBase - amp * 2, 0, yBase + amp * 2.5);
        grad.addColorStop(0, mix(pal, b / bands, 0));
        grad.addColorStop(0.45, mix(pal, b / bands, (0.16 + energy * 0.35) * (0.6 + o.glow * 0.6)));
        grad.addColorStop(1, mix(pal, b / bands, 0));
        ctx.fillStyle = grad;
        ctx.beginPath();
        ctx.moveTo(0, h);
        const steps = 48;
        for (let i = 0; i <= steps; i++) {
          const x = (i / steps) * w;
          const y = yBase + Math.sin(i * 0.25 + t * (0.4 + b * 0.13) + b) * amp + Math.sin(i * 0.09 - t * 0.3 * (b + 1)) * amp * 0.6;
          ctx.lineTo(x, y);
        }
        ctx.lineTo(w, h);
        ctx.closePath();
        ctx.fill();
      }
      ctx.restore();
    },
  };

  // ------------------------------------------------------------------ Orb
  V.orb = {
    name: 'Orb',
    draw(ctx, w, h, A, pal, t, st, o) {
      const n = Math.round(420 * (0.5 + o.density));
      if (!st.pts || st.pts.length !== n) {
        st.pts = [];
        const golden = Math.PI * (3 - Math.sqrt(5));
        for (let i = 0; i < n; i++) {
          const y = 1 - (i / (n - 1)) * 2, r = Math.sqrt(1 - y * y), th = golden * i;
          st.pts.push([Math.cos(th) * r, y, Math.sin(th) * r]);
        }
      }
      st.rot = (st.rot || 0) + 0.004 + A.mid * 0.01;
      const cx = o.hole ? o.hole.x : w / 2, cy = o.hole ? o.hole.y : h / 2;
      const R = Math.min(w, h) * 0.3 * (1 + A.bass * 0.18 + A.beat * 0.08);
      const cr = Math.cos(st.rot), sr = Math.sin(st.rot), tilt = 0.35;
      ctx.save();
      ctx.globalCompositeOperation = 'lighter';
      for (let i = 0; i < n; i++) {
        const p = st.pts[i];
        let x = p[0] * cr - p[2] * sr, z = p[0] * sr + p[2] * cr, y = p[1];
        const y2 = y * Math.cos(tilt) - z * Math.sin(tilt); z = y * Math.sin(tilt) + z * Math.cos(tilt); y = y2;
        const pole = Math.abs(p[1]);
        const bin = Math.floor((1 - pole) * 30 + pole * 55);
        const push = 1 + (A.bins[bin] || 0) * 0.35 * (pole > 0.7 ? 1.5 : 1);
        const depth = (z + 1.6) / 2.6;
        const px = cx + x * R * push, py = cy + y * R * push;
        const size = (1 + depth * 2.2) * o.dpr * (1 + (pole > 0.8 ? A.treble * 1.5 : 0));
        ctx.fillStyle = mix(pal, (p[1] + 1) / 2, 0.25 + depth * 0.65);
        ctx.beginPath(); ctx.arc(px, py, size, 0, TAU); ctx.fill();
      }
      const g = ctx.createRadialGradient(cx, cy, 0, cx, cy, R * 1.25);
      g.addColorStop(0, mix(pal, 0.5, 0.25 * o.glow + A.bass * 0.2));
      g.addColorStop(1, 'rgba(0,0,0,0)');
      ctx.fillStyle = g; ctx.beginPath(); ctx.arc(cx, cy, R * 1.25, 0, TAU); ctx.fill();
      ctx.restore();
    },
  };

  // ------------------------------------------------------------------ Particles
  V.particles = {
    name: 'Particles',
    draw(ctx, w, h, A, pal, t, st, o) {
      st.p = st.p || [];
      const cx = o.hole ? o.hole.x : w / 2, cy = o.hole ? o.hole.y : h / 2;
      const spawn = Math.round((2 + A.level * 6 + (A.beat > 0.85 ? 40 : 0)) * (0.5 + o.density));
      for (let i = 0; i < spawn && st.p.length < 1400; i++) {
        const a = Math.random() * TAU, sp = (0.6 + Math.random() * 2.4 + A.bass * 3) * o.dpr;
        const r0 = o.hole ? o.hole.r : Math.min(w, h) * 0.05;
        st.p.push({ x: cx + Math.cos(a) * r0, y: cy + Math.sin(a) * r0, vx: Math.cos(a) * sp, vy: Math.sin(a) * sp, life: 1, c: Math.random() });
      }
      ctx.save();
      ctx.globalCompositeOperation = 'lighter';
      const keep = [];
      for (const p of st.p) {
        p.x += p.vx; p.y += p.vy;
        p.vx *= 0.992; p.vy *= 0.992;
        p.vx += Math.sin(p.y * 0.01 + t) * 0.02 * o.dpr;
        p.life -= 0.006 + (1 - A.level) * 0.004;
        if (p.life <= 0 || p.x < -20 || p.y < -20 || p.x > w + 20 || p.y > h + 20) continue;
        keep.push(p);
        const s = (1.2 + p.life * 2.6) * o.dpr;
        ctx.fillStyle = mix(pal, p.c, p.life * 0.9);
        ctx.beginPath(); ctx.arc(p.x, p.y, s, 0, TAU); ctx.fill();
        if (o.glow > 0.3) { ctx.fillStyle = mix(pal, p.c, p.life * 0.12 * o.glow); ctx.beginPath(); ctx.arc(p.x, p.y, s * 4, 0, TAU); ctx.fill(); }
      }
      st.p = keep;
      ctx.restore();
    },
  };

  // ------------------------------------------------------------------ Terrain (retro grid)
  V.terrain = {
    name: 'Terrain',
    draw(ctx, w, h, A, pal, t, st, o) {
      const cols = 40, rows = 22;
      st.hist = st.hist || [];
      st.acc = (st.acc || 0) + 1;
      if (st.acc >= 3) {
        st.acc = 0;
        st.hist.unshift(sample(A.bins, cols).map((v, i) => v * (0.4 + 0.6 * Math.abs(i - cols / 2) / (cols / 2))));
        if (st.hist.length > rows) st.hist.pop();
      }
      const horizon = h * 0.34;
      // sun
      const sunR = Math.min(w, h) * 0.16 * (1 + A.bass * 0.08);
      const sg = ctx.createLinearGradient(0, horizon - sunR, 0, horizon);
      sg.addColorStop(0, mix(pal, 1, 0.9)); sg.addColorStop(1, mix(pal, 0, 0.9));
      ctx.fillStyle = sg;
      ctx.save(); ctx.beginPath(); ctx.arc(w / 2, horizon, sunR, Math.PI, TAU); ctx.fill(); ctx.restore();
      ctx.lineWidth = 1.4 * o.dpr;
      ctx.save();
      ctx.globalCompositeOperation = 'lighter';
      for (let r = st.hist.length - 1; r >= 0; r--) {
        const z = (r + 1) / rows;
        const persp = 1 / (z * 2.2 + 0.25);
        const y = horizon + (h - horizon) * (1 - z) * 0.98;
        const rowW = w * persp * 0.6;
        ctx.strokeStyle = mix(pal, 1 - z, 0.25 + (1 - z) * 0.7);
        ctx.beginPath();
        st.hist[r].forEach((v, i) => {
          const x = w / 2 + (i / (cols - 1) - 0.5) * rowW * 2;
          const yy = y - v * h * 0.22 * (1 - z * 0.6);
          i ? ctx.lineTo(x, yy) : ctx.moveTo(x, yy);
        });
        ctx.stroke();
      }
      ctx.restore();
    },
  };

  // ------------------------------------------------------------------ Starfield
  V.starfield = {
    name: 'Starfield',
    draw(ctx, w, h, A, pal, t, st, o) {
      const n = Math.round(380 * (0.5 + o.density));
      st.s = st.s || [];
      while (st.s.length < n) st.s.push({ x: (Math.random() - 0.5) * 2, y: (Math.random() - 0.5) * 2, z: Math.random(), c: Math.random() });
      st.s.length = n;
      const cx = w / 2, cy = h / 2, speed = 0.004 + A.level * 0.02 + A.beat * 0.03;
      ctx.save();
      ctx.globalCompositeOperation = 'lighter';
      ctx.lineCap = 'round';
      for (const s of st.s) {
        const pz = s.z;
        s.z -= speed;
        if (s.z <= 0.02) { s.x = (Math.random() - 0.5) * 2; s.y = (Math.random() - 0.5) * 2; s.z = 1; continue; }
        const k = Math.max(w, h) * 0.5;
        const x0 = cx + (s.x / pz) * k * 0.3, y0 = cy + (s.y / pz) * k * 0.3;
        const x1 = cx + (s.x / s.z) * k * 0.3, y1 = cy + (s.y / s.z) * k * 0.3;
        ctx.strokeStyle = mix(pal, s.c, Math.min(1, (1 - s.z) * 1.4));
        ctx.lineWidth = (1 - s.z) * 2.6 * o.dpr + 0.4;
        ctx.beginPath(); ctx.moveTo(x0, y0); ctx.lineTo(x1, y1); ctx.stroke();
      }
      ctx.restore();
    },
  };

  // ------------------------------------------------------------------ Vinyl
  V.vinyl = {
    name: 'Vinyl',
    draw(ctx, w, h, A, pal, t, st, o) {
      const cx = w / 2, cy = h / 2, R = Math.min(w, h) * 0.36;
      st.rot = (st.rot || 0) + (Wave.track && Wave.track.isPlaying === false ? 0 : 0.035);
      // spectrum halo
      const n = 120, vals = sample(A.bins, n / 2);
      ctx.save();
      ctx.translate(cx, cy);
      ctx.lineCap = 'round';
      for (let i = 0; i < n; i++) {
        const k = i < n / 2 ? i : n - 1 - i, v = vals[k], a = (i / n) * TAU - Math.PI / 2;
        ctx.strokeStyle = mix(pal, k / (n / 2), 0.85);
        ctx.lineWidth = 2.2 * o.dpr;
        ctx.beginPath();
        ctx.moveTo(Math.cos(a) * R * 1.04, Math.sin(a) * R * 1.04);
        ctx.lineTo(Math.cos(a) * R * (1.06 + v * 0.3), Math.sin(a) * R * (1.06 + v * 0.3));
        ctx.stroke();
      }
      ctx.rotate(st.rot);
      ctx.fillStyle = '#0b0b0e';
      ctx.beginPath(); ctx.arc(0, 0, R, 0, TAU); ctx.fill();
      for (let g = 0.42; g < 0.98; g += 0.035) {
        ctx.strokeStyle = `rgba(255,255,255,${0.03 + 0.03 * Math.sin(g * 40)})`;
        ctx.lineWidth = 1 * o.dpr;
        ctx.beginPath(); ctx.arc(0, 0, R * g, 0, TAU); ctx.stroke();
      }
      // light sheen that stays put while the record spins
      ctx.rotate(-st.rot);
      const sheen = ctx.createLinearGradient(-R, -R, R, R);
      sheen.addColorStop(0.35, 'rgba(255,255,255,0)'); sheen.addColorStop(0.5, mix(pal, 0.5, 0.12 + A.treble * 0.1)); sheen.addColorStop(0.65, 'rgba(255,255,255,0)');
      ctx.fillStyle = sheen; ctx.beginPath(); ctx.arc(0, 0, R, 0, TAU); ctx.fill();
      ctx.rotate(st.rot);
      // label: the cover if we have it
      const img = Wave.coverImage;
      ctx.save();
      ctx.beginPath(); ctx.arc(0, 0, R * 0.36, 0, TAU); ctx.clip();
      if (img && img.complete && img.naturalWidth) ctx.drawImage(img, -R * 0.36, -R * 0.36, R * 0.72, R * 0.72);
      else { ctx.fillStyle = mix(pal, 0.3); ctx.fillRect(-R, -R, R * 2, R * 2); }
      ctx.restore();
      ctx.fillStyle = '#111'; ctx.beginPath(); ctx.arc(0, 0, R * 0.025, 0, TAU); ctx.fill();
      ctx.restore();
    },
  };

  // ------------------------------------------------------------------ Scope (XY phosphor)
  V.scope = {
    name: 'Scope',
    draw(ctx, w, h, A, pal, t, st, o) {
      const N = A.wave.length, cx = w / 2, cy = h / 2, R = Math.min(w, h) * 0.38;
      st.trail = st.trail || [];
      const pts = [];
      let peak = 0.05;
      for (let i = 0; i < N; i++) peak = Math.max(peak, Math.abs(A.wave[i]));
      // Auto-gain so quiet passages still fill the scope, louder ones bloom a little more.
      const gain = (0.55 + A.level * 0.45) / peak;
      for (let i = 0; i < N; i++) {
        const x = A.wave[i] * gain, y = A.wave[(i + Math.floor(N / 4)) % N] * gain;
        const a = t * 0.3;
        pts.push([cx + (x * Math.cos(a) - y * Math.sin(a)) * R, cy + (x * Math.sin(a) + y * Math.cos(a)) * R]);
      }
      st.trail.unshift(pts);
      if (st.trail.length > 6) st.trail.pop();
      ctx.save();
      ctx.globalCompositeOperation = 'lighter';
      ctx.lineJoin = 'round';
      st.trail.forEach((p, k) => {
        ctx.strokeStyle = mix(pal, k / 6, (1 - k / 6) * 0.8);
        ctx.lineWidth = (2.2 - k * 0.25) * o.dpr;
        ctx.beginPath();
        p.forEach(([x, y], i) => (i ? ctx.lineTo(x, y) : ctx.moveTo(x, y)));
        ctx.closePath();
        ctx.stroke();
      });
      ctx.restore();
    },
  };

  Wave.VISUALIZERS = V;
  Wave.STYLE_IDS = Object.keys(V);
})();
