/* The dashboard: every setting, with live previews running on real (or demo) audio. */
'use strict';

(function () {
  const { el } = Wave;

  function row(label, control, hint) {
    return el('label', { class: 'row' }, el('span', { class: 'row-label' }, label, hint ? el('small', {}, hint) : null), control);
  }

  function toggle(key) {
    const input = el('input', { type: 'checkbox', class: 'switch' });
    input.checked = !!Wave.settings[key];
    input.addEventListener('change', () => Wave.set(key, input.checked));
    Wave.subscribe(() => { input.checked = !!Wave.settings[key]; });
    return input;
  }

  function slider(key, min, max, step, fmt) {
    const out = el('output');
    const input = el('input', { type: 'range', min, max, step });
    const sync = () => { input.value = Wave.settings[key]; out.textContent = fmt(Number(Wave.settings[key])); };
    input.addEventListener('input', () => { Wave.set(key, Number(input.value)); out.textContent = fmt(Number(input.value)); });
    Wave.subscribe(sync);
    sync();
    return el('div', { class: 'slider' }, input, out);
  }

  function segmented(key, options) {
    const box = el('div', { class: 'seg' });
    const sync = () => box.querySelectorAll('button').forEach((b) => b.classList.toggle('on', b.dataset.v === String(Wave.settings[key])));
    for (const [v, label] of Object.entries(options)) {
      box.append(el('button', { 'data-v': v, onclick: (e) => { e.preventDefault(); Wave.set(key, typeof Wave.DEFAULTS[key] === 'number' ? Number(v) : v); } }, label));
    }
    Wave.subscribe(sync);
    sync();
    return box;
  }

  function color(key) {
    const input = el('input', { type: 'color', value: Wave.settings[key] });
    input.addEventListener('input', () => Wave.set(key, input.value));
    Wave.subscribe(() => { input.value = Wave.settings[key]; });
    return input;
  }

  function section(title, ...rows) {
    return el('section', { class: 'card' }, el('h3', {}, title), ...rows);
  }

  // Live previews registered here are rendered by main.js every frame.
  Wave.previews = [];

  function visualizerTab() {
    const tiles = el('div', { class: 'tiles' });
    for (const id of Wave.STYLE_IDS) {
      const holder = el('div', { class: 'tile-viz' });
      const tile = el('button', { class: 'tile', 'data-id': id, onclick: () => Wave.set('style', id) }, holder, el('span', {}, Wave.VISUALIZERS[id].name));
      tiles.append(tile);
      Wave.previews.push(Wave.mountVisualizer(holder, { style: id, density: 0.45, paletteKey: 'tile' }));
    }
    const syncTiles = () => tiles.querySelectorAll('.tile').forEach((t) => t.classList.toggle('on', t.dataset.id === Wave.settings.style));
    Wave.subscribe(syncTiles);
    syncTiles();

    const swatches = el('div', { class: 'swatches' });
    for (const [id, cols] of Object.entries(Wave.THEMES)) {
      swatches.append(el('button', {
        class: 'swatch', 'data-id': id, title: id,
        style: `background: linear-gradient(120deg, ${cols.join(',')})`,
        onclick: () => { Wave.set('theme', id); Wave.set('useCustom', false); },
      }));
    }
    const hue = el('input', { type: 'range', min: 0, max: 359, step: 1, class: 'hue' });
    hue.addEventListener('input', () => { Wave.set('customHue', Number(hue.value)); Wave.set('useCustom', true); });
    const customPreview = el('div', { class: 'custom-preview' });
    const syncSw = () => {
      const s = Wave.settings;
      swatches.querySelectorAll('.swatch').forEach((b) => b.classList.toggle('on', !s.useCustom && b.dataset.id === s.theme));
      hue.value = s.customHue;
      customPreview.style.background = `linear-gradient(90deg, ${Wave.sweep(s.customHue).join(',')})`;
      customPreview.classList.toggle('on', s.useCustom);
    };
    Wave.subscribe(syncSw);
    syncSw();

    return el('div', { class: 'tab' },
      section('Style', tiles),
      section('Colour',
        row('Theme', swatches),
        row('Your colour', el('div', { class: 'hue-box' }, hue, customPreview), 'One hue, swept into a three-stop gradient'),
        row('Mood sync', toggle('moodSync'), 'Take colours from the album cover when a song plays')),
      section('Look',
        row('Density', slider('density', 0, 1, 0.01, (v) => `${Math.round(v * 100)}%`)),
        row('Glow', slider('glow', 0, 1, 0.01, (v) => `${Math.round(v * 100)}%`)),
        row('Edge feather', slider('feather', 0, 1, 0.01, (v) => `${Math.round(v * 100)}%`), 'Dissolve the edges into the wallpaper'),
        row('Backdrop', slider('backdrop', 0, 1, 0.01, (v) => `${Math.round(v * 100)}%`), 'Put a surface behind the visualizer'),
        row('Opacity', slider('opacity', 0.2, 1, 0.01, (v) => `${Math.round(v * 100)}%`))),
      section('Widget',
        row('Show on desktop', toggle('widgetEnabled')),
        row('Where it lives', segmented('widgetPlacement', { wallpaper: 'On the wallpaper', top: 'Always on top', normal: 'Normal window' })),
        row('Move and resize', el('button', { class: 'btn', onclick: () => Wave.send({ cmd: 'editLayout' }) }, 'Arrange widgets'), 'Brings the widgets forward so you can drag them. Click Done when finished.')));
  }

  function nowPlayingTab() {
    return el('div', { class: 'tab' },
      section('Card',
        row('Layout', segmented('card', { compact: 'Compact', centred: 'Centred', cover: 'Cover', text: 'Text only', none: 'Off' })),
        row('Album art glow', toggle('albumGlow'), 'Blend the cover into the background as a soft colour field')),
      section('Full screen',
        row('Open full screen', el('button', { class: 'btn', onclick: () => Wave.send({ cmd: 'openFullscreen' }) }, 'Open'), 'Shortcut: Ctrl + Alt + F (⌃⌥F on a Mac)'),
        row('Visualizer', segmented('fsStyle', Object.fromEntries(Wave.STYLE_IDS.map((id) => [id, Wave.VISUALIZERS[id].name])))),
        row('Colours', segmented('fsTheme', Object.assign({ album: 'Album' }, Object.fromEntries(Object.keys(Wave.THEMES).map((k) => [k, k[0].toUpperCase() + k.slice(1)])))))));
  }

  function clockTab() {
    const preview = el('div', { class: 'clock-preview' });
    const clock = Wave.mountClock(preview, { scale: 0.62 });
    Wave.previews.push({ render: () => clock.update(new Date()) });
    return el('div', { class: 'tab' },
      preview,
      section('Clock',
        row('Show on desktop', toggle('clockEnabled')),
        row('Face', segmented('clockStyle', Wave.CLOCK_STYLES)),
        row('Font', segmented('clockFont', { system: 'System', rounded: 'Rounded', serif: 'Serif', mono: 'Mono', condensed: 'Condensed' })),
        row('Where it lives', segmented('clockPlacement', { wallpaper: 'On the wallpaper', top: 'Floating on top' }))),
      section('Text',
        row('Size', slider('clockSize', 0.5, 2.5, 0.01, (v) => `${Math.round(v * 100)}%`)),
        row('Weight', slider('clockWeight', 200, 900, 100, (v) => String(v))),
        row('Letter spacing', slider('clockSpacing', -0.08, 0.3, 0.01, (v) => `${v.toFixed(2)} em`)),
        row('Opacity', slider('clockOpacity', 0.2, 1, 0.01, (v) => `${Math.round(v * 100)}%`)),
        row('24-hour time', toggle('clock24')),
        row('Seconds', toggle('clockSeconds')),
        row('Date', segmented('clockDate', { long: 'Long', short: 'Short', none: 'Off' }))),
      section('Colour',
        row('Fill', segmented('clockColor', { theme: 'Match visualizer', solid: 'Solid', gradient: 'Gradient' })),
        row('Colours', el('div', { class: 'pair' }, color('clockColorA'), color('clockColorB'))),
        row('Shadow', toggle('clockShadow')),
        row('Glow', toggle('clockGlow'))));
  }

  // ---------------------------------------------------------------- screen glow

  function glowTab() {
    const screen = el('div', { class: 'glow-screen' }, el('div', { class: 'glow-ring' }), el('div', { class: 'glow-core' }));
    let rot = 0;
    Wave.previews.push({
      canvas: screen,
      render(now) {
        const s = Wave.settings, A = Wave.audio;
        let cols;
        if (s.glowAlbumColors && Wave.track && Wave.track.colors && Wave.track.colors.length) cols = Wave.track.colors.slice(0, s.glowColorCount);
        else cols = [s.glowPrimary, s.glowSecondary, s.glowTertiary].slice(0, s.glowColorCount);
        let bright, speed;
        if (s.glowMode === 'music' && A.level > 0.01) { bright = 0.35 + 0.45 * A.bass + 0.25 * A.beat; speed = 0.04 + 0.25 * A.mid; }
        else if (s.glowMode === 'still') { bright = 0.8; speed = 0; }
        else { bright = 0.55 + 0.25 * Math.sin((2 * Math.PI * now) / 4000); speed = 0.03; }
        rot = (rot + speed * 6) % 360;
        const split = Math.round(s.glowSplit * 100);
        const grad = cols.length >= 3
          ? `conic-gradient(from ${rot}deg, ${cols[0]}, ${cols[1]}, ${cols[2]}, ${cols[0]})`
          : `conic-gradient(from ${rot}deg, ${cols[0]} 0%, ${cols[0]} ${split - 8}%, ${cols[1]} ${split + 8}%, ${cols[1]} 92%, ${cols[0]})`;
        const k = 0.42; // preview scale
        screen.style.setProperty('--g', grad);
        screen.style.setProperty('--t', `${Math.max(1.5, s.glowThickness * k)}px`);
        screen.style.setProperty('--blur', `${s.glowSize * k}px`);
        screen.style.setProperty('--b', Math.min(1, bright).toFixed(3));
        screen.style.opacity = s.glowEnabled ? 1 : 0.35;
      },
    });
    return el('div', { class: 'tab' },
      section('Preview', screen),
      section('Screen glow',
        row('Light up my screen edges', toggle('glowEnabled'), 'A soft light along the edges of every display, over everything, never taking a click'),
        row('Animation', segmented('glowMode', { music: 'Music sync', breathe: 'Breathe', still: 'Static' })),
        row('Thickness', slider('glowThickness', 2, 60, 1, (v) => `${v} px`)),
        row('Glow', slider('glowSize', 0, 80, 1, (v) => `${v} px`)),
        row('Notch compatibility', toggle('glowNotch'), 'Mac only: run the light around the camera notch')),
      section('Colour',
        row('Match album art', toggle('glowAlbumColors')),
        row('Gradient', segmented('glowColorCount', { 2: '2 colours', 3: '3 colours' })),
        row('Colours', el('div', { class: 'pair' }, color('glowPrimary'), color('glowSecondary'), color('glowTertiary'))),
        row('Primary / secondary', slider('glowSplit', 0.15, 0.85, 0.01, (v) => `${Math.round(v * 100)} / ${100 - Math.round(v * 100)}`))));
  }

  // ---------------------------------------------------------------- lyrics

  const DEMO_LINES = ['Every word lights up', 'the moment it is sung', 'follow along with me', 'one word at a time'];
  const LINE_LEN = 2.4;

  /** A small DOM version of the five lyric styles, played on a loop for the preview. */
  function lyricPreview() {
    const box = el('div', { class: 'ly-preview' });
    let last = '';
    return {
      el: box,
      canvas: box,
      render(now) {
        const s = Wave.settings;
        const t = (now / 1000) % (DEMO_LINES.length * LINE_LEN);
        const li = Math.floor(t / LINE_LEN), lt = t - li * LINE_LEN;
        const words = DEMO_LINES[li].split(' ');
        const wi = Math.min(words.length - 1, Math.floor((lt / 2.0) * words.length));
        const prog = Math.min(1, ((lt / 2.0) * words.length) - wi);
        const hi = s.lyricsMatchAlbum && Wave.track && Wave.track.colors ? Wave.track.colors[0] : s.lyricsHighlight;
        box.style.setProperty('--ly-text', s.lyricsText);
        box.style.setProperty('--ly-hi', hi);
        box.style.setProperty('--ly-dim', s.lyricsDimOpacity);
        box.style.setProperty('--ly-size', s.lyricsSize);
        box.style.fontFamily = Wave.fonts[s.lyricsFont] || Wave.fonts.system;
        box.style.justifyContent = { top: 'flex-start', center: 'center', bottom: 'flex-end' }[s.lyricsPlacement] || 'flex-end';
        box.classList.toggle('shadow', !!s.lyricsShadow);
        const key = [s.lyricsStyle, li, wi].join('|');
        const style = s.lyricsStyle;
        if (key !== last) {
          last = key;
          box.className = 'ly-preview ly-' + style + (s.lyricsShadow ? ' shadow' : '');
          box.innerHTML = '';
          const stage = el('div', { class: 'ly-stage' });
          if (style === 'spotlight') {
            const line = el('div', { class: 'ly-line' });
            words.forEach((w, i) => line.append(el('span', { class: i < wi ? 'sung' : i === wi ? 'cur' : 'up' }, w), ' '));
            stage.append(line, el('div', { class: 'ly-next' }, DEMO_LINES[(li + 1) % DEMO_LINES.length]));
          } else if (style === 'stack') {
            const flat = [];
            DEMO_LINES.forEach((l, i) => l.split(' ').forEach((w, j) => flat.push([i, j, w])));
            const idx = flat.findIndex(([i, j]) => i === li && j === wi);
            [idx - 2, idx - 1, idx].forEach((k, n) => { if (k >= 0) stage.append(el('div', { class: 'ly-stack s' + n }, flat[k][2])); });
          } else if (style === 'thread') {
            for (let k = Math.max(0, li - 2); k <= li; k++) {
              const text = k === li ? words.slice(0, wi + 1).join(' ') : DEMO_LINES[k];
              stage.append(el('div', { class: 'ly-bubble ' + (k % 2 ? 'right' : 'left') + (k === li ? ' new' : '') }, text));
            }
          } else if (style === 'terminal') {
            const term = el('div', { class: 'ly-term' });
            for (let k = Math.max(0, li - 2); k < li; k++) term.append(el('div', { class: 'old' }, '> ' + DEMO_LINES[k]));
            term.append(el('div', {}, el('b', {}, '> '), words.slice(0, wi + 1).join(' '), el('i', { class: 'cursor' }, '█')));
            stage.append(term);
          } else {
            const line = el('div', { class: 'ly-line drift' });
            words.forEach((w, i) => line.append(el('span', { class: i <= wi ? 'in' : 'wait', style: `--age:${i <= wi ? wi - i : 0}` }, w), ' '));
            stage.append(line);
          }
          box.append(stage);
        }
        const cur = box.querySelector('.cur');
        if (cur) cur.style.setProperty('--p', `${Math.round(prog * 100)}%`);
      },
    };
  }

  function lyricsTab() {
    const preview = lyricPreview();
    Wave.previews.push(preview);
    const status = el('div', { class: 'sp-status' });
    const offset = el('output', { class: 'small' });
    const sync = () => {
      status.textContent = Wave.status.lyrics || '';
      const o = Number(Wave.status.lyricsOffset || 0);
      offset.textContent = `${o >= 0 ? '+' : ''}${o.toFixed(2)} s`;
    };
    Wave.subscribe(sync);
    sync();
    return el('div', { class: 'tab' },
      preview.el,
      section('Lyrics',
        row('Show lyrics on screen', toggle('lyricsEnabled'), 'Words light up as they are sung, over everything, never taking a click'),
        row('Now', status),
        row('Style', segmented('lyricsStyle', { spotlight: 'Spotlight', stack: 'Stack', thread: 'Thread', terminal: 'Terminal', drift: 'Drift' })),
        row('Position', segmented('lyricsPlacement', { top: 'Top', center: 'Centre', bottom: 'Bottom' }))),
      section('Look',
        row('Font', segmented('lyricsFont', { system: 'System', rounded: 'Rounded', serif: 'Serif', mono: 'Mono', condensed: 'Condensed' })),
        row('Size', slider('lyricsSize', 0.6, 2, 0.01, (v) => `${Math.round(v * 100)}%`)),
        row('Sung / current word', el('div', { class: 'pair' }, color('lyricsText'), color('lyricsHighlight'))),
        row('Upcoming words', slider('lyricsDimOpacity', 0.1, 0.9, 0.01, (v) => `${Math.round(v * 100)}%`)),
        row('Match the album cover', toggle('lyricsMatchAlbum')),
        row('Shadow', toggle('lyricsShadow'))),
      section('Timing',
        row('This song', el('div', { class: 'btn-row tight' },
          el('button', { class: 'btn', onclick: () => Wave.send({ cmd: 'lyricsNudge', delta: 0.25 }) }, 'Earlier'),
          offset,
          el('button', { class: 'btn', onclick: () => Wave.send({ cmd: 'lyricsNudge', delta: -0.25 }) }, 'Later')), 'Resets when the next song starts'),
        row('Latency', slider('lyricsLatency', -0.5, 0.8, 0.01, (v) => `${v >= 0 ? '+' : ''}${v.toFixed(2)} s`), 'Applies to every song'),
        row('Keep the screen awake while music plays', toggle('lyricsKeepAwake'))));
  }

  function spotifyTab() {
    const status = el('div', { class: 'sp-status' });
    const connect = el('button', { class: 'btn primary', onclick: () => Wave.send({ cmd: 'spotifyConnect' }) }, 'Connect Spotify');
    const disconnect = el('button', { class: 'btn', onclick: () => Wave.send({ cmd: 'spotifyDisconnect' }) }, 'Disconnect');
    const clientId = el('input', { type: 'text', class: 'text', placeholder: 'Uses the built-in app ID', spellcheck: 'false' });
    clientId.addEventListener('change', () => Wave.set('spotifyClientId', clientId.value.trim()));
    const sync = () => {
      const s = Wave.status;
      const on = s.spotify === 'connected';
      status.textContent = on ? `Connected${s.spotifyUser ? ' as ' + s.spotifyUser : ''}` : s.spotify === 'connecting' ? 'Waiting for you to approve in the browser…' : s.spotify === 'error' ? `Couldn’t connect: ${s.spotifyError || 'try again'}` : 'Not connected';
      status.className = 'sp-status ' + (on ? 'ok' : '');
      connect.style.display = on ? 'none' : '';
      disconnect.style.display = on ? '' : 'none';
      if (document.activeElement !== clientId) clientId.value = Wave.settings.spotifyClientId || '';
    };
    Wave.subscribe(sync);
    sync();
    return el('div', { class: 'tab' },
      section('Spotify',
        el('p', { class: 'lead' }, 'Wave already follows any player through the system’s media controls. Connecting Spotify adds the extras: like the song with one click (L in full screen), sharp cover art, exact song position for lyrics, and playback control even when Spotify is on another device.'),
        el('div', { class: 'sp-row' }, el('div', { class: 'sp-logo' }), status, connect, disconnect)),
      section('Advanced',
        row('Spotify app Client ID', clientId, 'Optional. Your own app from developer.spotify.com, with redirect URI http://127.0.0.1:8765/callback'),
        el('p', { class: 'small' }, 'Sign-in uses PKCE, so no secret is stored. Your refresh token stays on this computer.')));
  }

  function audioTab() {
    const meter = el('div', { class: 'meter' }, el('i'));
    const label = el('div', { class: 'small' });
    Wave.previews.push({
      render() {
        meter.firstChild.style.width = `${Math.round(Wave.audio.level * 100)}%`;
        label.textContent = Wave.status.audio || '';
      },
    });
    return el('div', { class: 'tab' },
      section('Source',
        row('System audio', el('div', { class: 'meter-box' }, meter, label), 'Wave listens to your speakers, never your microphone. Nothing is recorded or sent anywhere.'),
        row('Sensitivity', slider('sensitivity', 0.3, 2.5, 0.01, (v) => `${Math.round(v * 100)}%`)),
        row('Smoothing', slider('smoothing', 0, 1, 0.01, (v) => `${Math.round(v * 100)}%`))));
  }

  function systemTab() {
    const version = el('span', { class: 'small' });
    Wave.subscribe(() => { version.textContent = `Wave ${Wave.status.version} · ${Wave.status.platform}`; });
    version.textContent = `Wave ${Wave.status.version} · ${Wave.status.platform}`;
    return el('div', { class: 'tab' },
      section('System',
        row('Launch at login', toggle('launchAtLogin')),
        row('Frame rate', segmented('fps', { 30: '30', 60: '60', 120: '120' })),
        row('Pause when covered', toggle('pauseWhenCovered'), 'Stop drawing while a window covers the widget'),
        row('Shortcuts', el('div', { class: 'small' }, 'Ctrl + Alt + F full screen · Ctrl + Alt + M show or hide widgets'))),
      section('About', version, el('div', { class: 'btn-row' },
        el('button', { class: 'btn', onclick: () => Wave.send({ cmd: 'resetSettings' }) }, 'Reset all settings'),
        el('button', { class: 'btn danger', onclick: () => Wave.send({ cmd: 'quit' }) }, 'Quit Wave'))));
  }

  Wave.mountDashboard = function (root) {
    const tabs = { visualizer: ['Visualizer', visualizerTab], nowplaying: ['Now playing', nowPlayingTab], clock: ['Clock', clockTab],
      lyrics: ['Lyrics', lyricsTab], glow: ['Screen glow', glowTab],
      spotify: ['Spotify', spotifyTab], audio: ['Audio', audioTab], system: ['System', systemTab] };
    const built = {};
    const nav = el('nav', { class: 'nav' }, el('div', { class: 'brand' }, el('span', { class: 'logo' }), 'Wave'));
    const content = el('main', { class: 'content' });
    const previewStage = el('div', { class: 'hero-preview' });
    const hero = el('div', { class: 'hero' }, previewStage, el('div', { class: 'hero-meta' }));
    const widget = Wave.mountWidget(previewStage);
    Wave.previews.push(widget);

    const pages = el('div', { class: 'pages' });
    content.append(hero, pages);
    for (const [id, [label]] of Object.entries(tabs)) {
      nav.append(el('button', { class: 'nav-item', 'data-tab': id, onclick: () => show(id) }, label));
    }
    nav.append(el('div', { class: 'nav-spacer' }), el('button', { class: 'nav-item fs', onclick: () => Wave.send({ cmd: 'openFullscreen' }) }, 'Full screen ↗'));

    function show(id) {
      for (const k in built) built[k].style.display = k === id ? '' : 'none';
      if (!built[id]) { built[id] = tabs[id][1](); pages.append(built[id]); }
      built[id].style.display = '';
      nav.querySelectorAll('.nav-item').forEach((b) => b.classList.toggle('on', b.dataset.tab === id));
      hero.style.display = id === 'visualizer' || id === 'nowplaying' || id === 'audio' ? '' : 'none';
    }
    root.append(el('div', { class: 'dashboard' }, nav, content));
    show('visualizer');
  };
})();
