/* Entry: picks a view from ?mode= and runs the frame loop.
 * Modes: widget (desktop visualizer), clock (desktop clock), fullscreen, dashboard (settings).
 */
'use strict';

(function () {
  const params = new URLSearchParams(location.search);
  const mode = params.get('mode') || 'dashboard';
  const root = document.getElementById('app');
  document.documentElement.dataset.mode = mode;

  // Running in a plain browser (the web preview): demo audio, a demo song, settings in localStorage.
  if (!Wave.hasHost || params.has('demo')) {
    Wave.demoAudio = true;
    try {
      const saved = JSON.parse(localStorage.getItem('wave.settings') || '{}');
      Object.assign(Wave.settings, saved);
    } catch (e) { /* storage may be blocked */ }
    Wave.onLocalMessage = (msg) => {
      if (msg.cmd === 'set') {
        try { localStorage.setItem('wave.settings', JSON.stringify(Wave.settings)); } catch (e) { /* ignore */ }
      } else if (msg.cmd === 'openFullscreen') {
        window.open('?mode=fullscreen', '_blank');
      } else if (msg.cmd === 'playpause' && Wave.track) {
        Wave.setTrack(Object.assign({}, Wave.track, { position: Wave.position(), isPlaying: !Wave.track.isPlaying }));
      } else if (msg.cmd === 'like' && Wave.track) {
        Wave.setTrack(Object.assign({}, Wave.track, { position: Wave.position(), liked: !Wave.track.liked }));
      }
    };
    Wave.setStatus({ platform: 'browser preview', audio: 'Demo audio (no app connected)', spotify: 'disconnected' });
    if (!params.has('notrack')) {
      Wave.setTrack({ title: 'Midnight Static', artist: 'Demo Signal', album: 'Wave', art: demoCover(), isPlaying: true, position: 42, duration: 214, liked: false });
    }
  }

  /** A generated cover so the demo has artwork without any external file. */
  function demoCover() {
    const c = document.createElement('canvas');
    c.width = c.height = 400;
    const x = c.getContext('2d');
    const g = x.createLinearGradient(0, 0, 400, 400);
    g.addColorStop(0, '#1d0b3a'); g.addColorStop(0.55, '#c2185b'); g.addColorStop(1, '#ff9e3d');
    x.fillStyle = g; x.fillRect(0, 0, 400, 400);
    for (let i = 0; i < 14; i++) {
      x.strokeStyle = `rgba(255,255,255,${0.05 + i * 0.012})`;
      x.lineWidth = 2;
      x.beginPath(); x.arc(200, 260, 30 + i * 16, Math.PI, Math.PI * 2); x.stroke();
    }
    x.fillStyle = '#fff4e0'; x.beginPath(); x.arc(200, 260, 46, 0, Math.PI * 2); x.fill();
    return c.toDataURL('image/png');
  }

  let view;
  if (mode === 'widget') view = Wave.mountWidget(root);
  else if (mode === 'clock') { const c = Wave.mountClock(root); view = { render: () => c.update(new Date()) }; }
  else if (mode === 'fullscreen') view = Wave.mountFullscreen(root);
  else if (mode === 'gallery') {
    // Every style at once (used for screenshots and the web page).
    root.classList.add('gallery');
    const views = Wave.STYLE_IDS.map((id) => {
      const cell = Wave.el('div', { class: 'gallery-cell' }, Wave.el('span', {}, Wave.VISUALIZERS[id].name));
      root.append(cell);
      return Wave.mountVisualizer(cell, { style: id });
    });
    view = { render: (now) => views.forEach((v) => v.render(now)) };
  } else Wave.mountDashboard(root);

  // Host can pause drawing (window covered, widget hidden).
  Wave.paused = false;
  Wave.setPaused = (p) => { Wave.paused = !!p; };

  let last = 0;
  function frame(now) {
    requestAnimationFrame(frame);
    const fps = Wave.settings.fps || 60;
    // Fall back to 20 fps when nothing is playing.
    const target = Wave.audio.live && Wave.audio.level > 0.01 ? fps : Math.min(fps, 20);
    if (now - last < 1000 / target - 2) return;
    last = now;
    if (Wave.paused) return;
    Wave.tickAudio(now);
    if (view) view.render(now);
    if (Wave.previews) {
      for (const p of Wave.previews) {
        if (p.canvas && !p.canvas.offsetParent) continue; // hidden tab
        p.render(now);
      }
    }
  }
  requestAnimationFrame(frame);

  Wave.send({ cmd: 'ready', mode });
})();
