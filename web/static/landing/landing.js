/* YardWatch landing page: live map demo, inventory wall, vehicle marquee,
   and the email handoff to the signup page. Everything shown here is
   sample data, labeled as such on the page. */
(function () {
  // Pin positions are in the map's own pixel space (400 x 414): real city
  // coordinates run through the same projection that drew idaho-south.svg.
  // The Treasure Valley pins are nudged apart a few pixels so they stay
  // distinct; five of the six yards sit within about 30 miles of each other.
  var POINTS = [
    { name: 'BOISE', x: 127, y: 139 },
    { name: 'GARDEN CITY', x: 112, y: 132 },
    { name: 'NAMPA', x: 81.5, y: 150 },
    { name: 'CALDWELL', x: 66.8, y: 129.9 },
    { name: 'CALDWELL', x: 77, y: 119 },
    { name: 'TWIN FALLS', x: 329.9, y: 312.5 }
  ];

  var STATIC_LABELS = [
    { text: 'TREASURE VALLEY', x: 56, y: 92 },
    { text: 'TWIN FALLS', x: 288, y: 330 }
  ];

  var ITEMS = [
    { title: '2016 Chevrolet Silverado 1500', meta: 'Row P' },
    { title: '2010 Toyota Camry', meta: 'Row B' },
    { title: '2011 Ford Explorer', meta: 'Row D' },
    { title: '2008 Subaru Outback', meta: 'Row 37' },
    { title: '2004 Honda Civic', meta: 'Row 22' },
    { title: '2014 Ram 1500', meta: 'Row K' },
    { title: '2012 Jeep Wrangler', meta: 'Row F' },
    { title: '2007 Toyota Tacoma', meta: 'Row H' }
  ];

  var CONFIG = {
    mapW: 400, mapH: 414,
    popupW: 252,
    minDelay: 3, maxDelay: 6,
    feedMax: 5,
    topEdge: 100, bottomEdge: 340, rightHalf: 220
  };

  var CAR = '<svg width="34" height="20" viewBox="0 0 339 202" fill="#FF6B1A" aria-hidden="true"><use href="#yw-car"></use></svg>';

  function esc(s) { return String(s).replace(/[&<>"]/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]; }); }
  function pct(v, total) { return (v / total * 100).toFixed(2) + '%'; }
  function pick(n, avoid) {
    var i = Math.floor(Math.random() * n);
    if (avoid != null && i === avoid) i = (i + 1 + Math.floor(Math.random() * (n - 1))) % n;
    return i;
  }

  /* ---------- live map demo ---------- */
  var pinsEl = document.getElementById('yw-pins');
  var feedEl = document.getElementById('yw-feed');
  var countEl = document.getElementById('yw-count');

  if (pinsEl) {
    var state = { alert: null, feed: [], n: 0 };
    var t1, t2;

    var render = function () {
      var a = state.alert, html = '';

      STATIC_LABELS.forEach(function (l) {
        html += '<div class="mono" style="position:absolute;left:' + pct(l.x, CONFIG.mapW) + ';top:' + pct(l.y, CONFIG.mapH) + ';font-size:10px;font-weight:700;color:#6E6B66;white-space:nowrap">' + l.text + '</div>';
      });

      POINTS.forEach(function (p, i) {
        var active = !!a && a.pi === i;
        html += '<div style="position:absolute;left:' + pct(p.x, CONFIG.mapW) + ';top:' + pct(p.y, CONFIG.mapH) + ';width:0;height:0">' +
          (active ? '<div class="ring"></div><div class="ring ring2"></div><div class="ring ring3"></div>' : '') +
          '<div style="position:absolute;left:-5px;top:-5px;width:10px;height:10px;border-radius:50%;background:' + (active ? '#FF6B1A' : '#ECE8E1') + ';box-shadow:0 0 0 3px rgba(13,14,14,0.9)"></div>' +
          '</div>';
      });

      if (a) {
        var p = POINTS[a.pi], it = ITEMS[a.ii];
        var vert = p.y < CONFIG.topEdge ? '-12%' : (p.y > CONFIG.bottomEdge ? '-88%' : '-50%');
        // On narrow screens the map is smaller than the popup is wide, so
        // shrink the popup and flip it to whichever side has room.
        var mapPx = pinsEl.offsetWidth || CONFIG.mapW;
        var popW = Math.min(CONFIG.popupW, Math.round(mapPx * 0.66));
        var pinPx = p.x / CONFIG.mapW * mapPx;
        var flip = pinPx + 22 + popW > mapPx || p.x > CONFIG.rightHalf;
        var left = flip ? pinPx - 22 - popW : pinPx + 22;
        var clamped = Math.max(4, Math.min(left, mapPx - popW - 4));
        var shift;
        if (clamped !== left) {
          // No room beside the pin: keep the popup inside the map and move it above or below the pin.
          var above = p.y > CONFIG.topEdge + 40;
          shift = 'translate(' + Math.round(clamped - pinPx) + 'px, ' + (above ? 'calc(-100% - 20px)' : '20px') + ')';
        } else {
          shift = 'translate(' + Math.round(left - pinPx) + 'px, ' + vert + ')';
        }
        html += '<div style="position:absolute;z-index:5;left:' + pct(p.x, CONFIG.mapW) + ';top:' + pct(p.y, CONFIG.mapH) + ';width:0;height:0">' +
          '<div style="position:absolute;top:0;left:0;transform:' + shift + ';width:' + popW + 'px">' +
          '<div class="pop" role="status" aria-live="polite" style="background:rgba(17,19,20,0.96);border:1px solid #FF6B1A;border-radius:6px;overflow:hidden;box-shadow:0 24px 60px rgba(0,0,0,0.6),0 0 0 4px rgba(255,107,26,0.12)">' +
          '<div class="mono" style="display:flex;align-items:center;justify-content:space-between;padding:8px 12px;background:#FF6B1A;color:#0D0E0E;font-size:11px;font-weight:700">' +
          '<span style="display:flex;align-items:center;gap:8px"><span class="blink" style="width:7px;height:7px;border-radius:50%;background:#0D0E0E;display:inline-block"></span>NEW VEHICLE FOUND</span><span>' + a.tm + '</span></div>' +
          '<div style="padding:14px 12px;display:flex;flex-direction:column;gap:6px">' +
          '<div style="font-weight:600;font-size:15px;line-height:1.3;color:#ECE8E1">' + esc(it.title) + '</div>' +
          '<div class="mono" style="font-size:11px;color:#9A9A94">' + esc(it.meta + ' · ' + p.name) + '</div>' +
          '</div></div></div></div>';
      }
      pinsEl.innerHTML = html;

      if (feedEl) {
        var f = '';
        state.feed.forEach(function (e, i) {
          var it = ITEMS[e.ii], name = POINTS[e.pi].name;
          var isNew = a && i === 0;
          var fade = isNew ? 1 : (1 - (a ? i - 1 : i) * 0.18).toFixed(2);
          f += '<div class="' + (isNew ? 'slidein' : '') + '" style="display:flex;gap:14px;align-items:center;padding:14px 18px;border-bottom:1px solid #22262A;' + (isNew ? 'background:rgba(255,107,26,0.06);' : '') + 'opacity:' + fade + '">' +
            '<div class="cartile">' + CAR + '</div>' +
            '<div style="display:flex;flex-direction:column;gap:4px;min-width:0">' +
            '<div style="font-size:14px;font-weight:600;color:' + (isNew ? '#ECE8E1' : '#CFCBC4') + ';white-space:nowrap;overflow:hidden;text-overflow:ellipsis">' + esc(it.title) + '</div>' +
            '<div class="mono" style="font-size:11px;color:' + (isNew ? '#FF8A47' : '#8C8A85') + '">' + esc(name) + ' · ' + e.tm + '</div>' +
            '</div></div>';
        });
        feedEl.innerHTML = f;
      }
      if (countEl) countEl.textContent = String(state.n).padStart(3, '0');
    };

    var fire = function () {
      var last = state.alert;
      var pi = pick(POINTS.length, last ? last.pi : null);
      var ii = pick(ITEMS.length, last ? last.ii : null);
      state.alert = null; render();
      clearTimeout(t1);
      t1 = setTimeout(function () {
        var a = { pi: pi, ii: ii, tm: new Date().toTimeString().slice(0, 8) };
        state.alert = a;
        state.feed = [a].concat(state.feed).slice(0, CONFIG.feedMax);
        state.n += 1;
        render();
      }, 70);
      var lo = CONFIG.minDelay, hi = Math.max(lo, CONFIG.maxDelay);
      clearTimeout(t2);
      t2 = setTimeout(fire, (lo + Math.random() * (hi - lo)) * 1000);
    };

    render();
    setTimeout(fire, 900);
  }

  /* ---------- inventory wall (decorative) ---------- */
  var wall = document.getElementById('yw-wall');
  if (wall) {
    var MODELS = ['CAMRY', 'CIVIC', 'F-150', 'SILVERADO', 'TACOMA', 'OUTBACK', 'RAM 1500', 'WRANGLER', 'ACCORD', 'COROLLA', 'EXPLORER', 'FORESTER', 'RAV4', 'CR-V', 'SIERRA', 'MALIBU', 'ALTIMA', 'IMPREZA', 'TAHOE', 'PRIUS', 'ESCAPE', 'GRAND CHEROKEE', 'SENTRA', 'FOCUS'];
    var cells = '', total = 260;
    var hits = {};
    while (Object.keys(hits).length < 9) hits[Math.floor(Math.random() * total)] = true;
    for (var i = 0; i < total; i++) {
      var yr = String(Math.floor(Math.random() * 26) + 2000).slice(2);
      cells += '<div class="wall-cell' + (hits[i] ? ' hit' : '') + '">’' + yr + ' ' + MODELS[Math.floor(Math.random() * MODELS.length)] + '</div>';
    }
    wall.innerHTML = cells;
  }

  /* ---------- vehicle marquee (decorative) ---------- */
  var track = document.getElementById('yw-track');
  if (track) {
    var chips = '';
    var places = ['BOISE', 'NAMPA', 'CALDWELL', 'GARDEN CITY', 'TWIN FALLS'];
    ITEMS.forEach(function (it, i) {
      chips += '<div class="chip"><div class="cartile">' + CAR + '</div><div style="display:flex;flex-direction:column;gap:5px">' +
        '<span class="t">' + esc(it.title) + '</span><span class="m mono">' + esc(places[i % places.length] + ' · ' + it.meta.toUpperCase()) + '</span></div></div>';
    });
    track.innerHTML = chips + chips;
  }

  /* ---------- email handoff to the signup page ----------
     The email goes through sessionStorage instead of the URL, so it never
     lands in server logs, browser history, or referrer headers. */
  var form = document.getElementById('yw-signup');
  if (form) {
    form.addEventListener('submit', function () {
      var input = document.getElementById('yw-email');
      try {
        if (input && input.value) sessionStorage.setItem('yw-email', input.value);
      } catch (e) { /* storage blocked: they just retype it */ }
    });
  }
})();
