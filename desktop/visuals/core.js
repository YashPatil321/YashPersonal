/* Wave core: host bridge, settings, audio frames, palettes. Plain script, no build step. */
'use strict';

const Wave = (window.Wave = {});

// ---------------------------------------------------------------- defaults

Wave.DEFAULTS = {
  // visualizer widget
  style: 'bars',
  theme: 'nebula',
  useCustom: false,
  customHue: 280,
  moodSync: true,
  density: 0.6,
  glow: 0.6,
  backdrop: 0,
  feather: 0.5,
  opacity: 1,
  card: 'compact', // compact | centred | cover | text | none
  albumGlow: true,
  widgetEnabled: true,
  widgetPlacement: 'wallpaper', // wallpaper | top | normal
  // audio
  sensitivity: 1,
  smoothing: 0.55,
  // clock widget
  clockEnabled: true,
  clockStyle: 'digital', // digital | stacked | minimal | analog | words
  clockFont: 'system', // system | rounded | serif | mono | condensed
  clock24: false,
  clockSeconds: true,
  clockDate: 'long', // long | short | none
  clockColor: 'theme', // theme | solid | gradient
  clockColorA: '#ffffff',
  clockColorB: '#8ab4ff',
  clockSize: 1,
  clockWeight: 600,
  clockSpacing: 0,
  clockOpacity: 1,
  clockShadow: true,
  clockGlow: false,
  clockPlacement: 'wallpaper',
  // full screen
  fsStyle: 'ring',
  fsTheme: 'album', // album | <theme id>
  // screen glow (light along the display edges)
  glowEnabled: false,
  glowMode: 'music', // music | breathe | still
  glowAlbumColors: true,
  glowColorCount: 2,
  glowPrimary: '#ff2e6b',
  glowSecondary: '#3873ff',
  glowTertiary: '#9e4dff',
  glowSplit: 0.6,
  glowThickness: 10,
  glowSize: 36,
  glowNotch: true,
  // lyrics overlay
  lyricsEnabled: true,
  lyricsStyle: 'spotlight', // spotlight | stack | thread | terminal | drift
  lyricsFont: 'system', // system | rounded | serif | mono | condensed
  lyricsSize: 1,
  lyricsText: '#ffffff',
  lyricsHighlight: '#ff6b9e',
  lyricsDimOpacity: 0.38,
  lyricsMatchAlbum: false,
  lyricsShadow: true,
  lyricsPlacement: 'bottom', // top | center | bottom
  lyricsKeepAwake: false,
  lyricsLatency: 0.15,
  // system
  fps: 60,
  pauseWhenCovered: true,
  launchAtLogin: false,
  spotifyClientId: '',
};

Wave.THEMES = {
  nebula: ['#7c3aed', '#ec4899', '#38bdf8'],
  sunset: ['#f97316', '#f43f5e', '#a855f7'],
  ocean: ['#06b6d4', '#3b82f6', '#22d3ee'],
  forest: ['#22c55e', '#a3e635', '#14b8a6'],
  ember: ['#ef4444', '#f59e0b', '#fde047'],
  mono: ['#e5e7eb', '#9ca3af', '#ffffff'],
};

// ---------------------------------------------------------------- host bridge

/** Messages to the native app (macOS WKWebView or Windows WebView2). Falls back to console in a browser. */
Wave.send = function (msg) {
  try {
    if (window.webkit && window.webkit.messageHandlers && window.webkit.messageHandlers.wave) {
      window.webkit.messageHandlers.wave.postMessage(msg);
    } else if (window.chrome && window.chrome.webview) {
      window.chrome.webview.postMessage(msg);
    } else if (Wave.onLocalMessage) {
      Wave.onLocalMessage(msg);
    }
  } catch (e) {
    console.warn('send failed', e);
  }
};

Wave.hasHost = !!((window.webkit && window.webkit.messageHandlers && window.webkit.messageHandlers.wave) ||
  (window.chrome && window.chrome.webview));

// ---------------------------------------------------------------- state

Wave.settings = Object.assign({}, Wave.DEFAULTS);
Wave.track = null; // {title, artist, album, art, colors[], isPlaying, position, duration, liked, source}
Wave.status = { spotify: 'disconnected', spotifyUser: '', audio: 'starting', platform: 'web', version: '1.0.0', lyrics: 'Waiting for a song', lyricsOffset: 0 };
const listeners = [];
Wave.subscribe = (fn) => listeners.push(fn);
const emit = (what) => listeners.forEach((fn) => { try { fn(what); } catch (e) { console.error(e); } });

/** Host pushes settings (full object or partial). */
Wave.config = function (patch) {
  if (typeof patch === 'string') patch = JSON.parse(patch);
  Object.assign(Wave.settings, patch || {});
  emit('settings');
};

/** Dashboard changes one setting: update locally and tell the host to persist and broadcast it. */
Wave.set = function (key, value) {
  Wave.settings[key] = value;
  emit('settings');
  Wave.send({ cmd: 'set', key, value });
};

Wave.setTrack = function (t) {
  if (typeof t === 'string') t = JSON.parse(t);
  const changed = !Wave.track || !t || Wave.track.title !== t.title || Wave.track.artist !== t.artist;
  Wave.track = t;
  if (t) Wave.trackClock = { position: t.position || 0, at: performance.now() };
  emit(changed ? 'track' : 'progress');
};

Wave.setStatus = function (s) {
  if (typeof s === 'string') s = JSON.parse(s);
  Object.assign(Wave.status, s || {});
  emit('status');
};

Wave.position = function () {
  const t = Wave.track;
  if (!t || !Wave.trackClock) return 0;
  const p = Wave.trackClock.position + (t.isPlaying ? (performance.now() - Wave.trackClock.at) / 1000 : 0);
  return Math.min(p, t.duration || p);
};

// ---------------------------------------------------------------- audio

const BINS = 64;
const WAVE_N = 128;

function emptyFrame() {
  return { bins: new Float32Array(BINS), wave: new Float32Array(WAVE_N), level: 0, bass: 0, mid: 0, treble: 0, beat: 0 };
}

Wave.BINS = BINS;
Wave.audio = emptyFrame(); // smoothed frame read by visualizers
let raw = emptyFrame();
let lastHostAudio = -1e9;
let lastBeatAt = -1e9;

/**
 * Host pushes an analysis frame. bins: 64 log-spaced magnitudes 0..1, wave: up to 128 samples -1..1,
 * plus level/bass/mid/treble 0..1 and beat (true or 0..1 when a beat was detected in this frame).
 */
Wave.pushAudio = function (f) {
  if (typeof f === 'string') f = JSON.parse(f);
  lastHostAudio = performance.now();
  ingest(f);
};

function ingest(f) {
  if (f.bins) for (let i = 0; i < BINS; i++) raw.bins[i] = f.bins[i] || 0;
  if (f.wave) for (let i = 0; i < WAVE_N; i++) raw.wave[i] = f.wave[Math.floor((i * f.wave.length) / WAVE_N)] || 0;
  raw.level = f.level || 0;
  raw.bass = f.bass || 0;
  raw.mid = f.mid || 0;
  raw.treble = f.treble || 0;
  if (f.beat === true || f.beat > 0.9) lastBeatAt = performance.now();
}

Wave.demoAudio = false; // previews and the browser page use generated audio

/** Synthetic music: a kick at 122 bpm, a bass line, swirling mids and hats. */
function demoFrame(t) {
  const bpm = 122, beatLen = 60 / bpm;
  const ph = (t % beatLen) / beatLen;
  const kick = Math.exp(-ph * 9);
  const bar = Math.floor(t / beatLen) % 8;
  const hat = Math.exp(-((t + beatLen / 2) % (beatLen / 2)) / (beatLen / 2) * 12);
  const f = { bins: [], wave: [], beat: ph < 0.04 };
  for (let i = 0; i < BINS; i++) {
    const x = i / BINS;
    let v = 0;
    v += kick * Math.exp(-x * 14) * 1.1;
    v += (0.35 + 0.25 * Math.sin(t * 0.9 + bar)) * Math.exp(-Math.pow((x - 0.18) * 6, 2));
    v += (0.3 + 0.2 * Math.sin(t * 1.7 + i * 0.3)) * Math.exp(-Math.pow((x - 0.45 - 0.1 * Math.sin(t * 0.4)) * 4, 2));
    v += hat * 0.35 * Math.max(0, x - 0.6) * 2;
    v += 0.06 * Math.random();
    f.bins.push(Math.min(1, v * (0.85 + 0.15 * Math.sin(t * 0.3))));
  }
  for (let i = 0; i < WAVE_N; i++) {
    const s = i / WAVE_N;
    f.wave.push(0.55 * kick * Math.sin(s * Math.PI * 4 + t * 3) + 0.25 * Math.sin(s * Math.PI * 18 + t * 9) * (0.5 + 0.5 * Math.sin(t)) + 0.08 * (Math.random() - 0.5));
  }
  f.bass = Math.min(1, kick * 0.9 + 0.2);
  f.mid = 0.4 + 0.25 * Math.sin(t * 1.3);
  f.treble = 0.25 + hat * 0.5;
  f.level = 0.3 + kick * 0.5;
  return f;
}

/** Called once per animation frame: smooth raw into Wave.audio. */
Wave.tickAudio = function (now) {
  const live = now - lastHostAudio < 600;
  if (!live && Wave.demoAudio) ingest(demoFrame(now / 1000));
  else if (!live) { raw = emptyFrame(); }
  const s = Wave.settings, a = Wave.audio;
  const sens = s.sensitivity || 1;
  const rel = 0.05 + (1 - (s.smoothing ?? 0.55)) * 0.35;
  const k = (cur, target) => cur + (target - cur) * (target > cur ? 0.6 : rel);
  for (let i = 0; i < BINS; i++) a.bins[i] = k(a.bins[i], Math.min(1, raw.bins[i] * sens));
  for (let i = 0; i < WAVE_N; i++) a.wave[i] = a.wave[i] + (raw.wave[i] * sens - a.wave[i]) * 0.5;
  a.level = k(a.level, Math.min(1, raw.level * sens));
  a.bass = k(a.bass, Math.min(1, raw.bass * sens));
  a.mid = k(a.mid, Math.min(1, raw.mid * sens));
  a.treble = k(a.treble, Math.min(1, raw.treble * sens));
  a.beat = Math.pow(0.88, ((now - lastBeatAt) / 1000) * 60);
  a.live = live || Wave.demoAudio;
};

// ---------------------------------------------------------------- colour

function hexToRgb(hex) {
  const h = hex.replace('#', '');
  const n = parseInt(h.length === 3 ? h.split('').map((c) => c + c).join('') : h, 16);
  return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
}
function rgbToHex([r, g, b]) {
  return '#' + [r, g, b].map((v) => Math.round(Math.max(0, Math.min(255, v))).toString(16).padStart(2, '0')).join('');
}
function hslToRgb(h, s, l) {
  h = ((h % 360) + 360) % 360 / 360;
  const q = l < 0.5 ? l * (1 + s) : l + s - l * s, p = 2 * l - q;
  const f = (t) => {
    t = (t + 1) % 1;
    if (t < 1 / 6) return p + (q - p) * 6 * t;
    if (t < 1 / 2) return q;
    if (t < 2 / 3) return p + (q - p) * (2 / 3 - t) * 6;
    return p;
  };
  return [f(h + 1 / 3) * 255, f(h) * 255, f(h - 1 / 3) * 255];
}
Wave.hexToRgb = hexToRgb;
Wave.rgbToHex = rgbToHex;
Wave.hslToRgb = hslToRgb;

/** One hue swept both ways into a designed three-stop palette. */
Wave.sweep = (hue) => [hslToRgb(hue - 38, 0.85, 0.6), hslToRgb(hue, 0.9, 0.62), hslToRgb(hue + 42, 0.85, 0.66)].map(rgbToHex);

/** The palette the visualizer should use right now: album colours, a custom hue, or a theme. */
Wave.palette = function (themeOverride) {
  const s = Wave.settings;
  const theme = themeOverride || s.theme;
  if ((themeOverride === 'album' || (!themeOverride && s.moodSync)) && Wave.track && Wave.track.colors && Wave.track.colors.length) {
    const c = Wave.track.colors.slice(0, 3);
    while (c.length < 3) c.push(c[c.length - 1]);
    return c;
  }
  if (!themeOverride && s.useCustom) return Wave.sweep(s.customHue);
  return Wave.THEMES[theme] || Wave.THEMES.nebula;
};

/** Smoothly animated palette: each component eases toward the target. */
const shownPalettes = {};
Wave.livePalette = function (key, target) {
  const cur = shownPalettes[key];
  const tgt = target.map(hexToRgb);
  if (!cur) { shownPalettes[key] = tgt.map((c) => c.slice()); return shownPalettes[key]; }
  for (let i = 0; i < 3; i++) for (let j = 0; j < 3; j++) cur[i][j] += (tgt[i][j] - cur[i][j]) * 0.06;
  return cur;
};

/** Colour at t in 0..1 along a 3-stop rgb palette, as an rgba() string. */
Wave.mix = function (pal, t, alpha = 1) {
  t = Math.max(0, Math.min(1, t));
  const seg = t < 0.5 ? 0 : 1, lt = t < 0.5 ? t * 2 : (t - 0.5) * 2;
  const a = pal[seg], b = pal[seg + 1];
  return `rgba(${(a[0] + (b[0] - a[0]) * lt) | 0},${(a[1] + (b[1] - a[1]) * lt) | 0},${(a[2] + (b[2] - a[2]) * lt) | 0},${alpha})`;
};

/** Pull up to three vibrant colours from an image the page can read (fallback when the host sends none). */
Wave.extractColors = function (img) {
  try {
    const c = document.createElement('canvas');
    c.width = c.height = 24;
    const x = c.getContext('2d');
    x.drawImage(img, 0, 0, 24, 24);
    const d = x.getImageData(0, 0, 24, 24).data;
    const bins = new Array(18).fill(0).map(() => ({ w: 0, r: 0, g: 0, b: 0 }));
    for (let i = 0; i < d.length; i += 4) {
      const r = d[i], g = d[i + 1], b = d[i + 2];
      const mx = Math.max(r, g, b), mn = Math.min(r, g, b);
      const sat = mx ? (mx - mn) / mx : 0, val = mx / 255;
      let h = 0;
      if (mx !== mn) {
        if (mx === r) h = ((g - b) / (mx - mn)) % 6; else if (mx === g) h = (b - r) / (mx - mn) + 2; else h = (r - g) / (mx - mn) + 4;
        h = ((h * 60) + 360) % 360;
      }
      const bin = bins[Math.min(17, Math.floor(h / 20))];
      const w = sat * sat * val + 1e-4;
      bin.w += w; bin.r += r * w; bin.g += g * w; bin.b += b * w;
    }
    const order = bins.map((b, i) => [b, i]).sort((a, b) => b[0].w - a[0].w);
    const picked = [];
    for (const [b, i] of order) {
      if (picked.length >= 3 || b.w < 0.01) break;
      if (picked.some((p) => Math.min(Math.abs(p.i - i), 18 - Math.abs(p.i - i)) < 2)) continue;
      picked.push({ i, rgb: [b.r / b.w, b.g / b.w, b.b / b.w] });
    }
    if (!picked.length) return ['#e8ecf4', '#b8c4dc', '#f4f4f8']; // grey cover: pale tinted whites
    return picked.map((p) => {
      // Lift so it glows on black.
      const [r, g, b] = p.rgb, m = Math.max(r, g, b, 1), k = Math.max(1, 210 / m);
      return rgbToHex([r * k, g * k, b * k]);
    });
  } catch (e) {
    return null;
  }
};

// ---------------------------------------------------------------- misc

Wave.fonts = {
  system: '-apple-system, "Segoe UI Variable Display", "Segoe UI", "SF Pro Display", system-ui, sans-serif',
  rounded: 'ui-rounded, "SF Pro Rounded", "Segoe UI Variable Display", "Arial Rounded MT Bold", system-ui, sans-serif',
  serif: '"New York", ui-serif, Georgia, "Times New Roman", serif',
  mono: 'ui-monospace, "SF Mono", "Cascadia Mono", Consolas, monospace',
  condensed: '"Bahnschrift Condensed", "Bahnschrift", "Helvetica Neue", "Arial Narrow", sans-serif',
};

Wave.el = function (tag, attrs, ...children) {
  const e = document.createElement(tag);
  for (const k in attrs || {}) {
    if (k === 'class') e.className = attrs[k];
    else if (k === 'style') e.style.cssText = attrs[k];
    else if (k.startsWith('on')) e.addEventListener(k.slice(2), attrs[k]);
    else if (attrs[k] !== undefined && attrs[k] !== null && attrs[k] !== false) e.setAttribute(k, attrs[k]);
  }
  for (const c of children.flat()) if (c !== null && c !== undefined && c !== false) e.append(c.nodeType ? c : document.createTextNode(String(c)));
  return e;
};

Wave.fmtTime = (s) => {
  s = Math.max(0, Math.floor(s || 0));
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`;
};

/** A canvas that tracks its element size at device pixel ratio. */
Wave.makeCanvas = function (parent) {
  const c = document.createElement('canvas');
  parent.append(c);
  const ctx = c.getContext('2d');
  const fit = () => {
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    const r = c.getBoundingClientRect();
    const w = Math.max(1, Math.round(r.width * dpr)), h = Math.max(1, Math.round(r.height * dpr));
    if (c.width !== w || c.height !== h) { c.width = w; c.height = h; }
    return { w, h, dpr };
  };
  return { canvas: c, ctx, fit };
};
