/* Views: a visualizer surface, the desktop widget, and the full-screen player. */
'use strict';

(function () {
  const { el } = Wave;

  // -------------------------------------------------------------- cover image shared by views

  Wave.coverImage = null;
  let coverUrl = '';
  Wave.subscribe((what) => {
    if (what !== 'track') return;
    const url = Wave.track && Wave.track.art;
    if (!url || url === coverUrl) { if (!url) { coverUrl = ''; Wave.coverImage = null; } return; }
    coverUrl = url;
    const img = new Image();
    img.crossOrigin = 'anonymous';
    img.onload = () => {
      Wave.coverImage = img;
      if (Wave.track && (!Wave.track.colors || !Wave.track.colors.length)) {
        const c = Wave.extractColors(img);
        if (c) { Wave.track.colors = c; }
      }
      document.querySelectorAll('[data-cover]').forEach((n) => { n.style.backgroundImage = `url("${url}")`; });
    };
    img.src = url;
  });

  /**
   * A canvas running one visualizer. opts: {style, theme (palette override), hole, density, glow}.
   * Read settings live unless the option is given.
   */
  // Styles that orbit a centre: in the widget the album cover sits inside them.
  const COVER_STYLES = ['ring', 'orb', 'particles'];

  /** The cover as a slowly turning disc, like a record under the ring. */
  function drawCoverDisc(ctx, hole, t, dpr) {
    const img = Wave.coverImage;
    ctx.save();
    ctx.translate(hole.x, hole.y);
    ctx.beginPath(); ctx.arc(0, 0, hole.r, 0, Math.PI * 2); ctx.clip();
    if (img && img.complete && img.naturalWidth) {
      const playing = !Wave.track || Wave.track.isPlaying !== false;
      ctx.rotate(playing ? t * 0.25 : 0);
      ctx.drawImage(img, -hole.r, -hole.r, hole.r * 2, hole.r * 2);
    } else {
      const g = ctx.createRadialGradient(0, 0, 0, 0, 0, hole.r);
      g.addColorStop(0, 'rgba(255,255,255,0.10)'); g.addColorStop(1, 'rgba(255,255,255,0.02)');
      ctx.fillStyle = g; ctx.fillRect(-hole.r, -hole.r, hole.r * 2, hole.r * 2);
    }
    ctx.restore();
    // spindle hole and a soft rim
    ctx.save();
    ctx.fillStyle = 'rgba(0,0,0,0.55)';
    ctx.beginPath(); ctx.arc(hole.x, hole.y, Math.max(2 * dpr, hole.r * 0.06), 0, Math.PI * 2); ctx.fill();
    ctx.strokeStyle = 'rgba(255,255,255,0.18)'; ctx.lineWidth = 1.5 * dpr;
    ctx.beginPath(); ctx.arc(hole.x, hole.y, hole.r, 0, Math.PI * 2); ctx.stroke();
    ctx.restore();
  }

  Wave.mountVisualizer = function (root, opts = {}) {
    const { canvas, ctx, fit } = Wave.makeCanvas(root);
    canvas.className = 'viz';
    const state = {};
    let styleId = null;
    const t0 = performance.now();
    return {
      canvas,
      opts,
      render(now) {
        const s = Wave.settings;
        const { w, h, dpr } = fit();
        const id = opts.style || s.style;
        if (id !== styleId) { styleId = id; for (const k in state) delete state[k]; }
        const viz = Wave.VISUALIZERS[id] || Wave.VISUALIZERS.bars;
        const pal = Wave.livePalette(opts.paletteKey || 'main' + (opts.theme || ''), Wave.palette(opts.theme));
        ctx.clearRect(0, 0, w, h);
        let hole = typeof opts.hole === 'function' ? opts.hole(w, h, dpr) : null;
        if (!hole && opts.coverCentre && COVER_STYLES.includes(id)) {
          hole = { x: w / 2, y: h / 2, r: Math.min(w, h) * 0.2 * (1 + Wave.audio.beat * 0.04) };
          drawCoverDisc(ctx, hole, (now - t0) / 1000, dpr);
        }
        viz.draw(ctx, w, h, Wave.audio, pal, (now - t0) / 1000, state, {
          density: opts.density ?? s.density,
          glow: opts.glow ?? s.glow,
          dpr,
          hole,
        });
      },
    };
  };

  // -------------------------------------------------------------- now playing card

  function nowPlayingCard(layout) {
    const art = el('div', { class: 'np-art', 'data-cover': '' });
    const title = el('div', { class: 'np-title' });
    const artist = el('div', { class: 'np-artist' });
    const bar = el('div', { class: 'np-bar' }, el('i'));
    const btn = (cmd, icon, label) => el('button', {
      class: 'np-btn ' + cmd, title: label,
      onmousedown: (e) => e.stopPropagation(),
      onclick: (e) => { e.stopPropagation(); Wave.send({ cmd }); },
    }, svgIcon(icon));
    const play = btn('playpause', 'play', 'Play / pause');
    const like = btn('like', 'heart', 'Save to Liked Songs');
    const controls = el('div', { class: 'np-controls' }, btn('previous', 'prev', 'Previous'), play, btn('next', 'next', 'Next'), like);
    const card = el('div', { class: `np np-${layout}` }, art, el('div', { class: 'np-text' }, title, artist, bar), controls);
    let playing = null;
    return {
      el: card,
      update() {
        const t = Wave.track;
        card.classList.toggle('empty', !t);
        if (!t) return;
        if (title.textContent !== t.title) title.textContent = t.title || '';
        if (artist.textContent !== t.artist) artist.textContent = t.artist || '';
        if (Wave.coverImage) art.style.backgroundImage = `url("${Wave.coverImage.src}")`;
        if (playing !== !!t.isPlaying) { playing = !!t.isPlaying; play.replaceChildren(svgIcon(playing ? 'pause' : 'play')); }
        like.style.display = Wave.status.spotify === 'connected' ? '' : 'none';
        like.classList.toggle('on', !!t.liked);
        const p = t.duration ? Math.min(1, Wave.position() / t.duration) : 0;
        bar.firstChild.style.width = `${(p * 100).toFixed(2)}%`;
      },
    };
  }

  // -------------------------------------------------------------- desktop widget

  Wave.mountWidget = function (root) {
    const glow = el('div', { class: 'album-glow', 'data-cover': '' });
    const backdrop = el('div', { class: 'backdrop' });
    const stage = el('div', { class: 'stage' });
    const wrap = el('div', { class: 'widget' }, backdrop, glow, stage);
    root.append(wrap);
    const viz = Wave.mountVisualizer(stage, { coverCentre: true });
    let card = null, cardLayout = '';
    const grip = el('div', { class: 'resize-grip', title: 'Drag to resize' });
    wrap.append(grip);
    Wave.enableWindowDrag(wrap, grip);

    function layout() {
      const s = Wave.settings;
      wrap.style.opacity = s.opacity;
      backdrop.style.opacity = s.backdrop;
      const f = Math.round(s.feather * 22);
      wrap.style.setProperty('--feather', `${f}%`);
      glow.style.display = s.albumGlow && Wave.track ? '' : 'none';
      if (s.card !== cardLayout) {
        cardLayout = s.card;
        if (card) card.el.remove();
        card = s.card === 'none' ? null : nowPlayingCard(s.card);
        if (card) wrap.append(card.el);
        wrap.dataset.card = s.card;
      }
    }
    Wave.subscribe(layout);
    layout();

    return {
      render(now) {
        viz.render(now);
        if (card) card.update();
        const t = Wave.track;
        glow.style.display = Wave.settings.albumGlow && t ? '' : 'none';
      },
    };
  };

  /**
   * Grab anywhere to move the window, the corner grip to resize it. The host does the actual move
   * (it starts a native drag), so it feels like dragging any window. Off when "Lock position" is on.
   */
  Wave.enableWindowDrag = function (surface, grip) {
    surface.addEventListener('mousedown', (e) => {
      if (e.button !== 0 || Wave.settings.widgetLocked || e.target.closest('button')) return;
      e.preventDefault();
      Wave.send({ cmd: e.target === grip ? 'resizeStart' : 'dragStart' });
    });
    const sync = () => document.documentElement.classList.toggle('locked', !!Wave.settings.widgetLocked);
    Wave.subscribe(sync);
    sync();
  };

  // -------------------------------------------------------------- full screen player

  Wave.mountFullscreen = function (root) {
    const bg = el('div', { class: 'fs-bg', 'data-cover': '' });
    const shade = el('div', { class: 'fs-shade' });
    const ripples = Wave.makeCanvas(root);
    ripples.canvas.className = 'fs-ripples';
    const vizHolder = el('div', { class: 'fs-viz' });
    const cover = el('div', { class: 'fs-cover', 'data-cover': '' });
    const title = el('div', { class: 'fs-title' });
    const artist = el('div', { class: 'fs-artist' });
    const time = el('div', { class: 'fs-time' });
    const heart = el('button', { class: 'fs-btn heart', title: 'Like (L)', onclick: () => Wave.send({ cmd: 'like' }) }, svgIcon('heart'));
    const controls = el('div', { class: 'fs-controls' },
      el('button', { class: 'fs-btn', title: 'Previous', onclick: () => Wave.send({ cmd: 'previous' }) }, svgIcon('prev')),
      el('button', { class: 'fs-btn big', title: 'Play / pause', onclick: () => Wave.send({ cmd: 'playpause' }) }, svgIcon('play')),
      el('button', { class: 'fs-btn', title: 'Next', onclick: () => Wave.send({ cmd: 'next' }) }, svgIcon('next')),
      heart);
    const hint = el('div', { class: 'fs-hint' }, 'Space play · ← → skip · V visualizer · C colours · L like · Esc close');
    root.append(bg, shade, vizHolder, cover, el('div', { class: 'fs-meta' }, title, artist, time), controls, hint);
    root.classList.add('fullscreen');

    let fsStyle = Wave.settings.fsStyle;
    let fsTheme = Wave.settings.fsTheme;
    let viz = null;
    const orbitStyles = ['ring', 'orb', 'particles', 'vinyl'];
    function mountViz() {
      vizHolder.innerHTML = '';
      const around = orbitStyles.includes(fsStyle) && fsStyle !== 'vinyl';
      vizHolder.className = 'fs-viz ' + (around ? 'around' : fsStyle === 'vinyl' ? 'full' : 'under');
      cover.style.display = fsStyle === 'vinyl' ? 'none' : '';
      viz = Wave.mountVisualizer(vizHolder, {
        style: fsStyle,
        theme: fsTheme,
        paletteKey: 'fs',
        hole: around ? (w, h) => ({ x: w / 2, y: h / 2, r: Math.min(w, h) * 0.17 }) : null,
      });
    }
    mountViz();

    // Idle cursor hides the controls.
    let lastMove = performance.now();
    root.addEventListener('mousemove', () => { lastMove = performance.now(); });

    window.addEventListener('keydown', (e) => {
      if (e.key === ' ') { Wave.send({ cmd: 'playpause' }); e.preventDefault(); }
      else if (e.key === 'ArrowRight') Wave.send({ cmd: 'next' });
      else if (e.key === 'ArrowLeft') Wave.send({ cmd: 'previous' });
      else if (e.key === 'Escape') Wave.send({ cmd: 'closeFullscreen' });
      else if (e.key.toLowerCase() === 'l') Wave.send({ cmd: 'like' });
      else if (e.key.toLowerCase() === 'v') {
        const ids = Wave.STYLE_IDS;
        fsStyle = ids[(ids.indexOf(fsStyle) + 1) % ids.length];
        Wave.set('fsStyle', fsStyle);
        mountViz();
        toast(Wave.VISUALIZERS[fsStyle].name);
      } else if (e.key.toLowerCase() === 'c') {
        const order = ['album', ...Object.keys(Wave.THEMES)];
        fsTheme = order[(order.indexOf(fsTheme) + 1) % order.length];
        Wave.set('fsTheme', fsTheme);
        viz.opts.theme = fsTheme;
        toast(fsTheme === 'album' ? 'Album colours' : fsTheme[0].toUpperCase() + fsTheme.slice(1));
      }
    });

    let toastEl = null;
    function toast(text) {
      if (toastEl) toastEl.remove();
      toastEl = el('div', { class: 'fs-toast' }, text);
      root.append(toastEl);
      setTimeout(() => toastEl && toastEl.classList.add('out'), 900);
    }

    const rings = [];
    let lastBeat = 0;
    return {
      render(now) {
        const t = Wave.track;
        title.textContent = t ? t.title : 'Nothing playing';
        artist.textContent = t ? t.artist : 'Play something in Spotify or any music app';
        time.textContent = t && t.duration ? `${Wave.fmtTime(Wave.position())} / ${Wave.fmtTime(t.duration)}` : '';
        heart.classList.toggle('on', !!(t && t.liked));
        heart.style.display = Wave.status.spotify === 'connected' ? '' : 'none';
        controls.querySelector('.big').replaceChildren(svgIcon(t && t.isPlaying ? 'pause' : 'play'));
        const idle = now - lastMove > 2500;
        root.classList.toggle('idle', idle);

        const A = Wave.audio;
        cover.style.transform = `translate(-50%, -50%) scale(${1 + A.bass * 0.04 + A.beat * 0.03})`;
        bg.style.opacity = 0.75 + A.bass * 0.2;
        viz.render(now);

        // Bass ripples from the cover.
        const { canvas, ctx, fit } = ripples;
        const { w, h, dpr } = fit();
        ctx.clearRect(0, 0, w, h);
        if (A.beat > 0.95 && now - lastBeat > 220 && fsStyle !== 'vinyl') { rings.push({ r: Math.min(w, h) * 0.17, a: 0.55 }); lastBeat = now; }
        const pal = Wave.livePalette('fs' + fsTheme, Wave.palette(fsTheme));
        for (let i = rings.length - 1; i >= 0; i--) {
          const r = rings[i];
          r.r += 3.2 * dpr; r.a *= 0.965;
          if (r.a < 0.02) { rings.splice(i, 1); continue; }
          ctx.strokeStyle = Wave.mix(pal, 0.5, r.a);
          ctx.lineWidth = 2 * dpr;
          ctx.beginPath(); ctx.arc(w / 2, h / 2, r.r, 0, Math.PI * 2); ctx.stroke();
        }
      },
    };
  };

  function svgIcon(name) {
    const paths = {
      play: '<path d="M8 5.5v13a1 1 0 0 0 1.5.86l10.5-6.5a1 1 0 0 0 0-1.72L9.5 4.64A1 1 0 0 0 8 5.5z"/>',
      pause: '<rect x="6.5" y="5" width="4" height="14" rx="1.2"/><rect x="13.5" y="5" width="4" height="14" rx="1.2"/>',
      next: '<path d="M5 6.2v11.6a1 1 0 0 0 1.55.83L15 13v4.5a1 1 0 0 0 2 0v-11a1 1 0 0 0-2 0V11L6.55 5.37A1 1 0 0 0 5 6.2z"/>',
      prev: '<path d="M19 6.2v11.6a1 1 0 0 1-1.55.83L9 13v4.5a1 1 0 0 1-2 0v-11a1 1 0 0 1 2 0V11l8.45-5.63A1 1 0 0 1 19 6.2z"/>',
      heart: '<path d="M12 20.5s-7.5-4.6-7.5-10.3A4.2 4.2 0 0 1 12 7.6a4.2 4.2 0 0 1 7.5 2.6c0 5.7-7.5 10.3-7.5 10.3z"/>',
    };
    const s = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    s.setAttribute('viewBox', '0 0 24 24');
    s.innerHTML = paths[name];
    return s;
  }
  Wave.svgIcon = svgIcon;
})();
