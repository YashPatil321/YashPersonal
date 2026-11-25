/* Desktop clock: Digital, Stacked, Minimal, Analog, Words. */
'use strict';

(function () {
  const { el } = Wave;
  const CLOCK_STYLES = { digital: 'Digital', stacked: 'Stacked', minimal: 'Minimal', analog: 'Analog', words: 'Words' };
  const ONES = ['', 'one', 'two', 'three', 'four', 'five', 'six', 'seven', 'eight', 'nine', 'ten', 'eleven', 'twelve',
    'thirteen', 'fourteen', 'quarter', 'sixteen', 'seventeen', 'eighteen', 'nineteen', 'twenty'];

  function minuteWords(m) {
    if (m <= 20) return ONES[m];
    if (m === 30) return 'half';
    return 'twenty-' + ONES[m - 20];
  }

  /** "It's twenty past four", "It's quarter to nine", "It's nine o'clock". */
  function timeInWords(d) {
    let h = d.getHours(), m = d.getMinutes();
    const hourName = (x) => ONES[((x + 11) % 12) + 1];
    if (m === 0) return ["It's", hourName(h), "o'clock"];
    if (m <= 30) return ["It's", minuteWords(m), m === 15 || m === 30 ? 'past' : m === 1 ? 'minute past' : 'past', hourName(h)];
    const to = 60 - m;
    return ["It's", minuteWords(to), 'to', hourName(h + 1)];
  }

  function pad(n) { return String(n).padStart(2, '0'); }

  function parts(d, s) {
    let h = d.getHours();
    const ampm = h >= 12 ? 'PM' : 'AM';
    if (!s.clock24) h = h % 12 || 12;
    return { h: s.clock24 ? pad(h) : String(h), m: pad(d.getMinutes()), s: pad(d.getSeconds()), ampm: s.clock24 ? '' : ampm };
  }

  function dateText(d, s) {
    if (s.clockDate === 'none') return '';
    if (s.clockDate === 'short') return d.toLocaleDateString(undefined, { weekday: 'short', month: 'short', day: 'numeric' });
    return d.toLocaleDateString(undefined, { weekday: 'long', month: 'long', day: 'numeric' }).toUpperCase();
  }

  /** Builds and updates a clock inside root. Returns {update(now), destroy()}. */
  Wave.mountClock = function (root, opts = {}) {
    const box = el('div', { class: 'clock' });
    root.append(box);
    let lastKey = '';
    let analog = null;

    function colorCss(s) {
      if (s.clockColor === 'solid') return { color: s.clockColorA };
      let a = s.clockColorA, b = s.clockColorB;
      if (s.clockColor === 'theme') {
        const p = Wave.palette(); a = p[0]; b = p[2];
      }
      return { gradient: `linear-gradient(100deg, ${a}, ${b})`, a, b };
    }

    function applyText(node, s) {
      const c = colorCss(s);
      if (c.color) {
        node.style.background = 'none'; node.style.webkitTextFillColor = ''; node.style.color = c.color;
      } else {
        node.style.background = c.gradient;
        node.style.webkitBackgroundClip = 'text';
        node.style.backgroundClip = 'text';
        node.style.webkitTextFillColor = 'transparent';
      }
    }

    function build(s, d) {
      box.innerHTML = '';
      box.className = `clock clock-${s.clockStyle}`;
      box.style.fontFamily = Wave.fonts[s.clockFont] || Wave.fonts.system;
      box.style.fontWeight = s.clockWeight;
      box.style.letterSpacing = `${s.clockSpacing}em`;
      box.style.opacity = s.clockOpacity;
      box.style.setProperty('--clock-scale', s.clockSize * (opts.scale || 1));
      const shadow = [];
      if (s.clockShadow) shadow.push('drop-shadow(0 4px 18px rgba(0,0,0,0.55))');
      if (s.clockGlow) {
        const p = Wave.palette();
        shadow.push(`drop-shadow(0 0 24px ${p[1]}aa)`);
      }
      box.style.filter = shadow.join(' ');
      analog = null;

      if (s.clockStyle === 'analog') {
        const size = 220;
        const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
        svg.setAttribute('viewBox', `0 0 ${size} ${size}`);
        svg.classList.add('analog');
        const c = colorCss(s);
        const stroke = c.color || c.a;
        const gid = 'cg' + Math.random().toString(36).slice(2, 8);
        let ticks = '';
        for (let i = 0; i < 60; i++) {
          const a = (i / 60) * Math.PI * 2, r1 = i % 5 ? 98 : 90, r2 = 104;
          ticks += `<line x1="${110 + Math.sin(a) * r1}" y1="${110 - Math.cos(a) * r1}" x2="${110 + Math.sin(a) * r2}" y2="${110 - Math.cos(a) * r2}" stroke="${stroke}" stroke-opacity="${i % 5 ? 0.35 : 0.9}" stroke-width="${i % 5 ? 1.5 : 3}" stroke-linecap="round"/>`;
        }
        svg.innerHTML = `<defs><linearGradient id="${gid}" gradientUnits="userSpaceOnUse" x1="20" y1="20" x2="200" y2="200"><stop offset="0" stop-color="${c.color || c.a}"/><stop offset="1" stop-color="${c.color || c.b}"/></linearGradient></defs>
          ${ticks}
          <line class="hh" x1="110" y1="110" x2="110" y2="58" stroke="url(#${gid})" stroke-width="7" stroke-linecap="round"/>
          <line class="mh" x1="110" y1="110" x2="110" y2="30" stroke="url(#${gid})" stroke-width="4.5" stroke-linecap="round"/>
          <line class="sh" x1="110" y1="124" x2="110" y2="22" stroke="${c.color ? c.color : c.b}" stroke-width="1.8" stroke-linecap="round" ${s.clockSeconds ? '' : 'visibility="hidden"'}/>
          <circle cx="110" cy="110" r="5" fill="url(#${gid})"/>`;
        box.append(svg);
        analog = { h: svg.querySelector('.hh'), m: svg.querySelector('.mh'), s: svg.querySelector('.sh') };
        const date = el('div', { class: 'clock-date' }, dateText(d, s));
        box.append(date);
        return;
      }
      if (s.clockStyle === 'words') {
        const w = el('div', { class: 'clock-words' });
        box.append(w, el('div', { class: 'clock-date' }, dateText(d, s)));
        return;
      }
      const time = el('div', { class: 'clock-time' });
      applyText(time, s);
      box.append(time);
      if (s.clockStyle !== 'minimal') box.append(el('div', { class: 'clock-date' }, dateText(d, s)));
    }

    function update(now = new Date()) {
      const s = Wave.settings;
      const key = ['clockStyle', 'clockFont', 'clockWeight', 'clockSpacing', 'clockOpacity', 'clockSize', 'clockColor', 'clockColorA', 'clockColorB',
        'clockShadow', 'clockGlow', 'clockSeconds', 'clockDate', 'clock24'].map((k) => s[k]).join('|') + '|' + Wave.palette().join() + '|' + now.toDateString();
      if (key !== lastKey) { lastKey = key; build(s, now); }
      const p = parts(now, s);
      if (s.clockStyle === 'analog' && analog) {
        const sec = now.getSeconds() + now.getMilliseconds() / 1000;
        const min = now.getMinutes() + sec / 60, hr = (now.getHours() % 12) + min / 60;
        analog.h.setAttribute('transform', `rotate(${hr * 30} 110 110)`);
        analog.m.setAttribute('transform', `rotate(${min * 6} 110 110)`);
        analog.s.setAttribute('transform', `rotate(${Math.floor(sec) * 6} 110 110)`);
        return;
      }
      if (s.clockStyle === 'words') {
        const w = box.querySelector('.clock-words');
        const words = timeInWords(now);
        const text = words.join(' ');
        if (w.dataset.t !== text) {
          w.dataset.t = text;
          w.innerHTML = '';
          words.forEach((x, i) => {
            const span = el('span', { class: i === 0 ? 'dim' : '' }, x);
            if (i) applyText(span, s);
            w.append(span, ' ');
          });
        }
        return;
      }
      const t = box.querySelector('.clock-time');
      let html;
      if (s.clockStyle === 'stacked') html = `<span>${p.h}</span><span>${p.m}</span>${s.clockSeconds ? `<span class="sec">${p.s}</span>` : ''}`;
      else html = `${p.h}<span class="colon">:</span>${p.m}${s.clockSeconds && s.clockStyle === 'digital' ? `<span class="colon">:</span>${p.s}` : ''}${p.ampm && s.clockStyle === 'digital' ? `<span class="ampm">${p.ampm}</span>` : ''}`;
      if (t.innerHTML !== html) t.innerHTML = html;
    }

    update();
    return { update, destroy: () => box.remove(), el: box };
  };

  Wave.CLOCK_STYLES = CLOCK_STYLES;
  Wave.timeInWords = timeInWords;
})();
