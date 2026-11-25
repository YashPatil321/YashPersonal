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
