/* YardWatch landing page: interactive yard map, demo alerts, inventory wall,
   vehicle marquee, and the email handoff to the signup page. The map shows
   real inventory when you hover a yard; the pinging alerts and the marquee
   are sample data, labeled as such on the page. */
(function () {
  // Pin positions are in the map's own pixel space (400 x 414): real city
  // coordinates run through the same projection that drew idaho-south.svg.
  // The Treasure Valley pins are nudged apart a few pixels so they stay
  // distinct; five of the six yards sit within about 30 miles of each other.
  var POINTS = [
    { name: 'BOISE', key: 'boise', x: 127, y: 139 },
    { name: 'GARDEN CITY', key: 'garden-city', x: 112, y: 132 },
    { name: 'NAMPA', key: 'nampa', x: 81.5, y: 150 },
    { name: 'CALDWELL', key: 'caldwell', x: 66.8, y: 129.9 },
    { name: 'CALDWELL', key: 'caldwell-2', x: 77, y: 119 },
    { name: 'TWIN FALLS', key: 'twin-falls', x: 329.9, y: 312.5 }
  ];

  var STATIC_LABELS = [
    { text: 'TREASURE VALLEY', x: 56, y: 92 },
    { text: 'TWIN FALLS', x: 288, y: 330 }
  ];

  var ITEMS = [
    'Chevrolet Silverado 1500', 'Toyota Camry', 'Ford Explorer', 'Subaru Outback',
    'Honda Civic', 'Ram 1500', 'Jeep Wrangler', 'Toyota Tacoma'
  ];
  var ITEM_YEARS = [2016, 2010, 2011, 2008, 2004, 2014, 2012, 2007];

  var CONFIG = {
    mapW: 400, mapH: 414,
    popupW: 252,
    minDelay: 3, maxDelay: 6,
    feedMax: 5,
    maxRow: 165,
    topEdge: 100, bottomEdge: 340, rightHalf: 220
  };

  var MONTHS = ['JAN', 'FEB', 'MAR', 'APR', 'MAY', 'JUN', 'JUL', 'AUG', 'SEP', 'OCT', 'NOV', 'DEC'];

  var CAR = '<svg width="34" height="20" viewBox="0 0 339 202" fill="#FF6B1A" aria-hidden="true"><use href="#yw-car"></use></svg>';

  function esc(s) { return String(s).replace(/[&<>"]/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]; }); }
  function pct(v, total) { return (v / total * 100).toFixed(2) + '%'; }
  function pick(n, avoid) {
    var i = Math.floor(Math.random() * n);
    if (avoid != null && i === avoid) i = (i + 1 + Math.floor(Math.random() * (n - 1))) % n;
    return i;
  }
  function randomRow() { return 1 + Math.floor(Math.random() * CONFIG.maxRow); }
  function prettyDate(iso) {
    var m = /^(\d{4})-(\d{2})-(\d{2})/.exec(iso || '');
    return m ? MONTHS[+m[2] - 1] + ' ' + (+m[3]) : '';
  }

  // Real inventory per yard, embedded by the server.
  var yardsByKey = {};
  try {
    JSON.parse(document.getElementById('yw-yards').textContent).forEach(function (y) {
      yardsByKey[y.key] = y;
    });
  } catch (e) { /* no data: hovering just shows the pin's name */ }

  /* ---------- interactive map ---------- */
  var pinsEl = document.getElementById('yw-pins');
  var feedEl = document.getElementById('yw-feed');
  var countEl = document.getElementById('yw-count');

  if (pinsEl) {
    var state = { alert: null, hover: null, feed: [], n: 0 };
    var t1, t2, tLeave;
    var pinNodes = [];
    var popEl;

    // Pins are built once so keyboard focus survives updates; only the
    // popup and the "active" ring change.
    var build = function () {
      var html = '';
      STATIC_LABELS.forEach(function (l) {
        html += '<div class="mono" style="position:absolute;left:' + pct(l.x, CONFIG.mapW) + ';top:' + pct(l.y, CONFIG.mapH) + ';font-size:10px;font-weight:700;color:#6E6B66;white-space:nowrap;pointer-events:none">' + l.text + '</div>';
      });
      POINTS.forEach(function (p, i) {
        html += '<div class="pin" data-pi="' + i + '" style="position:absolute;left:' + pct(p.x, CONFIG.mapW) + ';top:' + pct(p.y, CONFIG.mapH) + ';width:0;height:0">' +
          '<div class="ring"></div><div class="ring ring2"></div><div class="ring ring3"></div>' +
          '<div class="pindot"></div>' +
          '<button type="button" class="pinhit" data-pi="' + i + '" aria-label="' + esc(p.name) + ': show current inventory"></button>' +
          '</div>';
      });
      html += '<div class="poplayer" style="position:absolute;inset:0;z-index:5;pointer-events:none"></div>';
      pinsEl.innerHTML = html;
      pinNodes = Array.prototype.slice.call(pinsEl.querySelectorAll('.pin'));
      popEl = pinsEl.querySelector('.poplayer');
    };

    // Where the popup goes: beside the pin, flipped or moved above/below it
    // when the (smaller, on phones) map has no room.
    var popupShift = function (p, popW) {
      var mapPx = pinsEl.parentNode.offsetWidth || CONFIG.mapW;
      var pinPx = p.x / CONFIG.mapW * mapPx;
      var flip = pinPx + 22 + popW > mapPx || p.x > CONFIG.rightHalf;
      var left = flip ? pinPx - 22 - popW : pinPx + 22;
      var clamped = Math.max(4, Math.min(left, mapPx - popW - 4));
      if (clamped !== left) {
        var above = p.y > CONFIG.topEdge + 40;
        return 'translate(' + Math.round(clamped - pinPx) + 'px, ' + (above ? 'calc(-100% - 20px)' : '20px') + ')';
      }
      var vert = p.y < CONFIG.topEdge ? '-12%' : (p.y > CONFIG.bottomEdge ? '-88%' : '-50%');
      return 'translate(' + Math.round(left - pinPx) + 'px, ' + vert + ')';
    };

    var popupHtml = function (p, header, rightTag, body) {
      var mapPx = pinsEl.parentNode.offsetWidth || CONFIG.mapW;
      var popW = Math.min(CONFIG.popupW, Math.round(mapPx * 0.66));
      return '<div style="position:absolute;left:' + pct(p.x, CONFIG.mapW) + ';top:' + pct(p.y, CONFIG.mapH) + ';width:0;height:0">' +
        '<div style="position:absolute;top:0;left:0;transform:' + popupShift(p, popW) + ';width:' + popW + 'px">' +
        '<div class="pop" style="background:rgba(17,19,20,0.96);border:1px solid #FF6B1A;border-radius:6px;overflow:hidden;box-shadow:0 24px 60px rgba(0,0,0,0.6),0 0 0 4px rgba(255,107,26,0.12)">' +
        '<div class="mono" style="display:flex;align-items:center;justify-content:space-between;gap:8px;padding:8px 12px;background:#FF6B1A;color:#0D0E0E;font-size:11px;font-weight:700">' +
        '<span style="display:flex;align-items:center;gap:8px"><span class="blink" style="width:7px;height:7px;border-radius:50%;background:#0D0E0E;display:inline-block;flex:none"></span>' + header + '</span><span>' + rightTag + '</span></div>' +
        body + '</div></div></div>';
    };

    var render = function () {
      var a = state.alert, h = state.hover;

      pinNodes.forEach(function (node, i) {
        node.classList.toggle('on', h === i || (h == null && !!a && a.pi === i));
      });

      var pop = '';
      if (h != null) {
        var p = POINTS[h], yard = yardsByKey[p.key];
        var body = '<div style="padding:12px 12px 14px;display:flex;flex-direction:column;gap:10px">';
        if (yard) {
          body += '<div class="mono" style="font-size:10px;color:#8C8A85">LAST ' + yard.recent.length + ' FOUND</div>';
          yard.recent.forEach(function (v) {
            body += '<div style="display:flex;flex-direction:column;gap:3px">' +
              '<div style="font-weight:600;font-size:13px;line-height:1.25;color:#ECE8E1">' + esc(v.title) + '</div>' +
              '<div class="mono" style="font-size:10px;color:#9A9A94">ROW ' + esc(v.row) + (v.date ? ' · ' + prettyDate(v.date) : '') + '</div></div>';
          });
        } else {
          body += '<div class="mono" style="font-size:11px;color:#9A9A94">No inventory data yet.</div>';
        }
        body += '</div>';
        pop = popupHtml(p, esc(p.name), yard ? yard.count.toLocaleString('en-US') + ' VEHICLES' : '', body);
      } else if (a) {
        var q = POINTS[a.pi];
        pop = popupHtml(q, 'NEW VEHICLE FOUND', a.tm,
          '<div role="status" aria-live="polite" style="padding:14px 12px;display:flex;flex-direction:column;gap:6px">' +
          '<div style="font-weight:600;font-size:15px;line-height:1.3;color:#ECE8E1">' + esc(a.title) + '</div>' +
          '<div class="mono" style="font-size:11px;color:#9A9A94">' + esc('Row ' + a.row + ' · ' + q.name) + '</div></div>');
      }
      popEl.innerHTML = pop;

      if (feedEl) {
        var f = '';
        state.feed.forEach(function (e, i) {
          var isNew = a && i === 0;
          var fade = isNew ? 1 : (1 - (a ? i - 1 : i) * 0.18).toFixed(2);
          f += '<div class="' + (isNew ? 'slidein' : '') + '" style="display:flex;gap:14px;align-items:center;padding:14px 18px;border-bottom:1px solid #22262A;' + (isNew ? 'background:rgba(255,107,26,0.06);' : '') + 'opacity:' + fade + '">' +
            '<div class="cartile">' + CAR + '</div>' +
            '<div style="display:flex;flex-direction:column;gap:4px;min-width:0">' +
            '<div style="font-size:14px;font-weight:600;color:' + (isNew ? '#ECE8E1' : '#CFCBC4') + ';white-space:nowrap;overflow:hidden;text-overflow:ellipsis">' + esc(e.title) + '</div>' +
            '<div class="mono" style="font-size:11px;color:' + (isNew ? '#FF8A47' : '#8C8A85') + '">' + esc(POINTS[e.pi].name) + ' · ' + e.tm + '</div>' +
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
        var a = { pi: pi, ii: ii, title: ITEM_YEARS[ii] + ' ' + ITEMS[ii], row: randomRow(), tm: new Date().toTimeString().slice(0, 8) };
        state.alert = a;
        state.feed = [a].concat(state.feed).slice(0, CONFIG.feedMax);
        state.n += 1;
        render();
      }, 70);
      var lo = CONFIG.minDelay, hi = Math.max(lo, CONFIG.maxDelay);
      clearTimeout(t2);
      t2 = setTimeout(fire, (lo + Math.random() * (hi - lo)) * 1000);
    };

    // Looking at a yard pauses the demo alerts; letting go resumes them.
    var setHover = function (pi) {
      clearTimeout(tLeave);
      if (state.hover === pi) return;
      state.hover = pi;
      if (pi != null) {
        clearTimeout(t1); clearTimeout(t2);
        state.alert = null;
      } else {
        clearTimeout(t2);
        t2 = setTimeout(fire, 1500);
      }
      render();
    };
    var leaveSoon = function () {
      clearTimeout(tLeave);
      tLeave = setTimeout(function () { setHover(null); }, 150);
    };
    var pinOf = function (e) {
      var el = e.target.closest ? e.target.closest('.pinhit') : null;
      return el ? +el.getAttribute('data-pi') : null;
    };

    pinsEl.addEventListener('pointerover', function (e) {
      if (e.pointerType !== 'mouse') return;
      var pi = pinOf(e);
      if (pi != null) setHover(pi);
    });
    pinsEl.addEventListener('pointerout', function (e) {
      if (e.pointerType === 'mouse' && pinOf(e) != null) leaveSoon();
    });
    // A tap also focuses the button; only keyboard focus should open a yard,
    // otherwise focus and click would cancel each other out.
    var touching = false;
    document.addEventListener('pointerdown', function (e) { touching = e.pointerType !== 'mouse'; }, true);
    document.addEventListener('keydown', function () { touching = false; }, true);
    pinsEl.addEventListener('focusin', function (e) {
      var pi = pinOf(e);
      if (pi != null && !touching) setHover(pi);
    });
    pinsEl.addEventListener('focusout', leaveSoon);
    // Touch and pen have no hover: a tap opens a yard, tapping it again closes it.
    pinsEl.addEventListener('click', function (e) {
      var pi = pinOf(e);
      if (pi == null || e.pointerType === 'mouse') return;
      setHover(e.pointerType && state.hover === pi ? null : pi);
    });
    document.addEventListener('pointerdown', function (e) {
      if (e.pointerType !== 'mouse' && state.hover != null && pinOf(e) == null) setHover(null);
    });

    build();
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

  /* ---------- vehicle marquee (decorative sample finds) ---------- */
  var track = document.getElementById('yw-track');
  if (track) {
    var chips = '';
    var places = ['BOISE', 'NAMPA', 'CALDWELL', 'GARDEN CITY', 'TWIN FALLS'];
    ITEMS.forEach(function (name, i) {
      chips += '<div class="chip"><div class="cartile">' + CAR + '</div><div style="display:flex;flex-direction:column;gap:5px">' +
        '<span class="t">' + esc(ITEM_YEARS[i] + ' ' + name) + '</span><span class="m mono">' + esc(places[i % places.length] + ' · ROW ' + randomRow()) + '</span></div></div>';
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
