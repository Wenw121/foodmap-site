/* Amino Acid Food Map — progressive enhancement for the homepage.
   Search / category & band filter / column sort operate on the static table
   already in the DOM; compare + scatter read the inline JSON payload. */
(function () {
  "use strict";

  var dataEl = document.getElementById("foodsData");
  var cfgEl = document.getElementById("uiConfig");
  if (!dataEl || !cfgEl) return;
  var FOODS = JSON.parse(dataEl.textContent);
  var UI = JSON.parse(cfgEl.textContent);
  var BY_SLUG = {};
  FOODS.forEach(function (f) { BY_SLUG[f.slug] = f; });

  var table = document.getElementById("foodTable");
  var tbody = table.querySelector("tbody");
  var rows = Array.prototype.slice.call(tbody.querySelectorAll("tr"));
  var search = document.getElementById("searchBox");
  var catFilter = document.getElementById("catFilter");
  var aminoSelect = document.getElementById("aminoSelect");
  var aminoMax = document.getElementById("aminoMax");
  var diaasMin = document.getElementById("diaasMin");
  var aminoMaxLabel = document.getElementById("aminoMaxLabel");
  var diaasMinLabel = document.getElementById("diaasMinLabel");
  var presetBtn = document.getElementById("presetHiLo");
  var noResults = document.getElementById("noResults");
  var scatterHost = document.getElementById("scatter");
  var scatterTitle = document.getElementById("scatterTitle");
  var scatterTip = document.createElement("div");
  scatterTip.className = "dot-tip";
  scatterTip.hidden = true;
  if (scatterHost) scatterHost.style.position = "relative";
  var GROUP_COLOR = { Animal: "#b5532f", Plant: "#4a8a5c", Spice: "#c8932f", Special: "#6b6b70" };
  var GROUP_ORDER = ["Animal", "Plant", "Spice", "Special"];
  /* amino columns now shown all at once in the table; the selector below
     drives only the scatter axis + the amino slider/preset. */
  var AMINO_COL_KEYS = ["met", "cys", "leu", "bcaa", "arg", "gly", "lys"];

  var curAmino = "met";
  var aminoSliderMax = 1;

  function aa(tr, key) {
    var v = parseFloat(tr.dataset["aa" + key.charAt(0).toUpperCase() + key.slice(1)]);
    return isNaN(v) ? null : v;
  }
  function aminoLabel(key) {
    var o = UI.aminoOptions.filter(function (x) { return x.key === key; })[0];
    return o ? o.label : key;
  }
  function tertiles(key) {
    var vals = rows.map(function (r) { return aa(r, key); })
      .filter(function (v) { return v !== null; }).sort(function (a, b) { return a - b; });
    var n = vals.length;
    return { lo: vals[Math.floor(n / 3)], hi: vals[Math.floor(2 * n / 3)],
             min: vals[0], max: vals[n - 1] };
  }
  function bandOf(v, t) { return v === null ? null : v < t.lo ? "lower" : v >= t.hi ? "higher" : "intermediate"; }

  /* shade every amino column low->high by its own tertiles (a heatmap "map"),
     done once on load since tertiles are over the full data set */
  function colorCells() {
    AMINO_COL_KEYS.forEach(function (key) {
      var t = tertiles(key);
      rows.forEach(function (tr) {
        var cell = tr.querySelector(".aa-" + key);
        if (!cell) return;
        var b = bandOf(aa(tr, key), t);
        cell.classList.remove("cell-lower", "cell-intermediate", "cell-higher");
        if (b) cell.classList.add("cell-" + b);
      });
    });
  }
  /* mark which amino column is the one currently plotted on the scatter */
  function highlightCol(key) {
    table.querySelectorAll("th.aacol").forEach(function (th) {
      th.classList.toggle("col-active", th.dataset.amino === key);
    });
  }
  /* the selector drives the scatter axis + the amino slider/preset */
  function updateAmino(key) {
    curAmino = key;
    var t = tertiles(key);
    highlightCol(key);
    aminoSliderMax = Math.ceil(t.max);
    aminoMax.min = Math.floor(t.min);
    aminoMax.max = aminoSliderMax;
    aminoMax.step = 1;
    aminoMax.value = aminoSliderMax;
    updateLabels();
  }
  function renderLegend() {
    var host = document.getElementById("scatterLegend");
    if (!host) return;
    var present = {};
    FOODS.forEach(function (f) { if (f.group) present[f.group] = 1; });
    var labels = UI.groupLabels || {};
    host.innerHTML = GROUP_ORDER.filter(function (g) { return present[g]; }).map(function (g) {
      return '<span class="leg"><span class="sw" style="background:' + (GROUP_COLOR[g] || "#888") +
        '"></span>' + esc(labels[g] || g) + "</span>";
    }).join("");
  }
  function updateLabels() {
    aminoMaxLabel.textContent = UI.maxLabel + " " + aminoLabel(curAmino) + ": " + aminoMax.value + " " + UI.unit;
    diaasMinLabel.textContent = UI.minDiaasLabel + ": " + diaasMin.value;
    presetBtn.textContent = UI.presetLabel + " " + aminoLabel(curAmino);
  }

  /* ---------- filtering ---------- */
  function applyFilters() {
    var q = (search.value || "").trim().toLowerCase();
    var cat = catFilter.value;
    var amax = parseFloat(aminoMax.value);
    var dmin = parseFloat(diaasMin.value);
    var shown = 0;
    rows.forEach(function (tr) {
      var av = aa(tr, curAmino);
      var dv = parseFloat(tr.dataset.diaas);
      var okAmino = (amax >= aminoSliderMax) || (av !== null && av <= amax);
      var okDiaas = (dmin <= 0) || (!isNaN(dv) && dv >= dmin);
      var ok = (!q || tr.dataset.search.indexOf(q) !== -1) &&
               (!cat || tr.dataset.cat === cat) && okAmino && okDiaas;
      tr.hidden = !ok;
      if (ok) shown++;
    });
    noResults.hidden = shown !== 0;
    drawScatter();
  }
  search.addEventListener("input", applyFilters);
  catFilter.addEventListener("input", applyFilters);
  aminoSelect.addEventListener("change", function () { updateAmino(aminoSelect.value); applyFilters(); });
  aminoMax.addEventListener("input", function () { updateLabels(); applyFilters(); });
  diaasMin.addEventListener("input", function () { updateLabels(); applyFilters(); });
  presetBtn.addEventListener("click", function () {
    var t = tertiles(curAmino);
    aminoMax.value = Math.round(t.lo);
    diaasMin.value = Math.min(75, UI.diaasMax);
    updateLabels(); applyFilters();
  });

  /* ---------- sorting ---------- */
  var NUMERIC = { protein: 1, diaas: 1 };
  function sortBy(key, dir) {
    var isAmino = AMINO_COL_KEYS.indexOf(key) !== -1;
    var sorted = rows.slice().sort(function (a, b) {
      var av, bv;
      if (isAmino) { av = aa(a, key); bv = aa(b, key); }
      else if (NUMERIC[key]) { av = parseFloat(a.dataset[key]); bv = parseFloat(b.dataset[key]); }
      else {
        av = (a.dataset[key] || "").toLowerCase(); bv = (b.dataset[key] || "").toLowerCase();
        return dir * av.localeCompare(bv);
      }
      if (av === null || isNaN(av)) av = -Infinity;
      if (bv === null || isNaN(bv)) bv = -Infinity;
      return dir * (av - bv);
    });
    sorted.forEach(function (tr) { tbody.appendChild(tr); });
  }
  table.querySelectorAll("th[data-sort]").forEach(function (th) {
    var dir = 1;
    th.addEventListener("click", function () {
      table.querySelectorAll("th").forEach(function (o) { o.classList.remove("sorted-asc", "sorted-desc"); });
      dir = -dir;
      th.classList.add(dir === 1 ? "sorted-asc" : "sorted-desc");
      sortBy(th.dataset.sort, dir);
    });
  });

  /* init */
  diaasMin.min = 0; diaasMin.max = UI.diaasMax; diaasMin.step = 1; diaasMin.value = 0;
  colorCells();
  renderLegend();
  updateAmino("met");
  applyFilters();

  /* ---------- compare ---------- */
  var selected = [];
  var panel = document.getElementById("comparePanel");
  var body = document.getElementById("compareBody");
  var clearBtn = document.getElementById("compareClear");

  table.querySelectorAll("input.cmp").forEach(function (cb) {
    cb.addEventListener("change", function () {
      var slug = cb.closest("tr").dataset.slug;
      if (cb.checked) {
        if (selected.length >= UI.compareMax) { cb.checked = false; return; }
        selected.push(slug);
      } else {
        selected = selected.filter(function (s) { return s !== slug; });
      }
      renderCompare();
    });
  });
  clearBtn.addEventListener("click", function () {
    selected = [];
    table.querySelectorAll("input.cmp").forEach(function (c) { c.checked = false; });
    renderCompare();
  });

  function nameOf(f) { return UI.lang === "en" ? f.name_en : f.name_zh; }
  var AMINO_KEYS = ["Met", "Cys", "Leu", "BCAA", "Arg", "Gly", "Trp"];

  function renderCompare() {
    if (!selected.length) { panel.hidden = true; body.innerHTML = ""; return; }
    panel.hidden = false;
    var foods = selected.map(function (s) { return BY_SLUG[s]; });
    var html = "<table><thead><tr><th></th>";
    foods.forEach(function (f) { html += "<th>" + esc(nameOf(f)) + "</th>"; });
    html += "</tr></thead><tbody>";
    html += rowLine(UI.protein, foods, function (f) { return f.protein; });
    html += rowLine(UI.diaas, foods, function (f) { return f.diaas; });
    AMINO_KEYS.forEach(function (k) {
      html += rowLine(k, foods, function (f) { return f.amino[k]; });
    });
    html += "</tbody></table>";
    body.innerHTML = html;
  }
  function rowLine(label, foods, get) {
    var s = "<tr><th>" + esc(label) + "</th>";
    foods.forEach(function (f) {
      var v = get(f);
      s += "<td class='num'>" + (v == null ? UI.na : v) + "</td>";
    });
    return s + "</tr>";
  }

  /* ---------- scatter (vanilla SVG): X = selected amino acid, Y = DIAAS.
     Driven by the *visible* table rows so it tracks every filter. ---------- */
  function niceStep(maxv) {
    if (maxv <= 12) return 2;
    if (maxv <= 30) return 5;
    if (maxv <= 70) return 10;
    return 20;
  }
  function drawScatter() {
    if (!scatterHost) return;
    var xLabel = aminoLabel(curAmino);
    if (scatterTitle) scatterTitle.textContent = xLabel + " vs " + UI.scatterY;

    var pts = [];
    rows.forEach(function (tr) {
      if (tr.hidden) return;
      var x = aa(tr, curAmino);
      var y = parseFloat(tr.dataset.diaas);
      if (x === null || isNaN(y)) return;
      var f = BY_SLUG[tr.dataset.slug] || {};
      pts.push({ x: x, y: y, slug: tr.dataset.slug, name: nameOf(f), group: f.group });
    });
    if (!pts.length) {
      scatterHost.innerHTML = '<p class="scatter-empty hint">' + esc(UI.na) + "</p>";
      return;
    }

    var W = 820, H = 460, m = { t: 16, r: 16, b: 48, l: 52 };
    var iw = W - m.l - m.r, ih = H - m.t - m.b;
    var xs = pts.map(function (p) { return p.x; });
    var ys = pts.map(function (p) { return p.y; });
    var xmax = Math.max.apply(null, xs) * 1.05 || 1;
    var ymin = Math.min.apply(null, ys) - 5, ymax = Math.max.apply(null, ys) + 5;
    if (ymax - ymin < 1) ymax = ymin + 1;
    function X(v) { return m.l + (v / xmax) * iw; }
    function Y(v) { return m.t + ih - ((v - ymin) / (ymax - ymin)) * ih; }

    var svg = ['<svg viewBox="0 0 ' + W + ' ' + H + '" role="img" aria-label="' + esc(xLabel) + ' vs ' + esc(UI.scatterY) + '">'];
    svg.push(line(m.l, m.t + ih, m.l + iw, m.t + ih));
    svg.push(line(m.l, m.t, m.l, m.t + ih));
    var xStep = niceStep(xmax);
    for (var gx = 0; gx <= xmax; gx += xStep) {
      svg.push(line(X(gx), m.t + ih, X(gx), m.t + ih + 5));
      svg.push(txt(X(gx), m.t + ih + 18, gx, "middle"));
    }
    for (var gy = Math.ceil(ymin / 20) * 20; gy <= ymax; gy += 20) {
      svg.push(line(m.l - 5, Y(gy), m.l, Y(gy)));
      svg.push(txt(m.l - 9, Y(gy) + 4, gy, "end"));
    }
    svg.push(txt(m.l + iw / 2, H - 6, xLabel, "middle", "axis"));
    svg.push('<text x="16" y="' + (m.t + ih / 2) + '" transform="rotate(-90 16 ' + (m.t + ih / 2) + ')" text-anchor="middle" class="axis">' + esc(UI.scatterY) + "</text>");
    pts.forEach(function (p) {
      var c = GROUP_COLOR[p.group] || "#888";
      svg.push('<circle class="dot" cx="' + X(p.x).toFixed(1) + '" cy="' + Y(p.y).toFixed(1) +
        '" r="5" fill="' + c + '" fill-opacity="0.78" data-slug="' + p.slug +
        '" data-name="' + esc(p.name) + '" data-x="' + p.x + '" data-y="' + p.y + '"><title>' +
        esc(p.name) + " · " + esc(xLabel) + " " + p.x + " · " + esc(UI.scatterY) + " " + p.y + "</title></circle>");
    });
    svg.push("</svg>");
    scatterHost.innerHTML = svg.join("");
    scatterHost.appendChild(scatterTip);
    scatterTip.hidden = true;

    scatterHost.querySelectorAll(".dot").forEach(function (d) {
      d.addEventListener("click", function () { location.href = "foods/" + d.dataset.slug + "/"; });
      d.addEventListener("mouseenter", showTip);
      d.addEventListener("mousemove", showTip);
      d.addEventListener("mouseleave", hideTip);
    });

    function showTip(e) {
      var d = e.currentTarget;
      scatterTip.innerHTML = "<strong>" + esc(d.getAttribute("data-name")) + "</strong><br>" +
        esc(xLabel) + " " + d.dataset.x + " · " + esc(UI.scatterY) + " " + d.dataset.y;
      var hr = scatterHost.getBoundingClientRect();
      var x = e.clientX - hr.left + 12, y = e.clientY - hr.top + 12;
      if (x > hr.width - 150) x = hr.width - 150;
      scatterTip.style.left = Math.max(4, x) + "px";
      scatterTip.style.top = y + "px";
      scatterTip.hidden = false;
    }
    function hideTip() { scatterTip.hidden = true; }

    function line(x1, y1, x2, y2) {
      return '<line x1="' + x1 + '" y1="' + y1 + '" x2="' + x2 + '" y2="' + y2 + '" stroke="#ccc7bd" stroke-width="1"/>';
    }
    function txt(x, y, t, anchor, cls) {
      return '<text x="' + x + '" y="' + y + '" text-anchor="' + anchor + '" font-size="11" fill="#6b6b70"' +
        (cls ? ' class="' + cls + '"' : "") + ">" + esc(String(t)) + "</text>";
    }
  }

  function esc(s) {
    return String(s).replace(/[&<>"]/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c];
    });
  }

  drawScatter();
})();
