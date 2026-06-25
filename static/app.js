/* Methionine Food Map — progressive enhancement for the homepage.
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
  var bandFilter = document.getElementById("bandFilter");
  var noResults = document.getElementById("noResults");

  /* ---------- filtering ---------- */
  function applyFilters() {
    var q = (search.value || "").trim().toLowerCase();
    var cat = catFilter.value;
    var band = bandFilter.value;
    var shown = 0;
    rows.forEach(function (tr) {
      var ok =
        (!q || tr.dataset.search.indexOf(q) !== -1) &&
        (!cat || tr.dataset.cat === cat) &&
        (!band || tr.dataset.band === band);
      tr.hidden = !ok;
      if (ok) shown++;
    });
    noResults.hidden = shown !== 0;
  }
  [search, catFilter, bandFilter].forEach(function (el) {
    el.addEventListener("input", applyFilters);
  });

  /* ---------- sorting ---------- */
  var NUMERIC = { protein: 1, met: 1, diaas: 1 };
  function sortBy(key, dir) {
    var sorted = rows.slice().sort(function (a, b) {
      var av, bv;
      if (NUMERIC[key]) {
        av = parseFloat(a.dataset[key]); bv = parseFloat(b.dataset[key]);
        if (isNaN(av)) av = -Infinity;
        if (isNaN(bv)) bv = -Infinity;
        return dir * (av - bv);
      }
      av = (a.dataset[mapKey(key)] || "").toLowerCase();
      bv = (b.dataset[mapKey(key)] || "").toLowerCase();
      return dir * av.localeCompare(bv);
    });
    sorted.forEach(function (tr) { tbody.appendChild(tr); });
  }
  function mapKey(k) { return k === "name" ? "name" : k === "cat" ? "cat" : k; }
  table.querySelectorAll("th[data-sort]").forEach(function (th) {
    var dir = 1;
    th.addEventListener("click", function () {
      table.querySelectorAll("th").forEach(function (o) {
        o.classList.remove("sorted-asc", "sorted-desc");
      });
      dir = -dir;
      th.classList.add(dir === 1 ? "sorted-asc" : "sorted-desc");
      sortBy(th.dataset.sort, dir);
    });
  });

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

  /* ---------- scatter (vanilla SVG): X=met, Y=diaas ---------- */
  var GROUP_COLOR = { Animal: "#b5532f", Plant: "#4a8a5c", Spice: "#c8932f", Special: "#6b6b70" };
  function buildScatter() {
    var host = document.getElementById("scatter");
    if (!host) return;
    var pts = FOODS.filter(function (f) { return f.met != null && f.diaas != null; });
    if (!pts.length) { host.remove(); return; }
    var W = 820, H = 460, m = { t: 16, r: 16, b: 48, l: 52 };
    var iw = W - m.l - m.r, ih = H - m.t - m.b;
    var xs = pts.map(function (p) { return p.met; });
    var ys = pts.map(function (p) { return p.diaas; });
    var xmax = Math.max.apply(null, xs) * 1.05;
    var ymin = Math.min.apply(null, ys) - 5, ymax = Math.max.apply(null, ys) + 5;
    function X(v) { return m.l + (v / xmax) * iw; }
    function Y(v) { return m.t + ih - ((v - ymin) / (ymax - ymin)) * ih; }

    var svg = ['<svg viewBox="0 0 ' + W + ' ' + H + '" role="img" aria-label="' + esc(UI.scatterX) + ' vs ' + esc(UI.scatterY) + '">'];
    // axes
    svg.push(line(m.l, m.t + ih, m.l + iw, m.t + ih));
    svg.push(line(m.l, m.t, m.l, m.t + ih));
    // x ticks
    for (var gx = 0; gx <= xmax; gx += 20) {
      svg.push(line(X(gx), m.t + ih, X(gx), m.t + ih + 5));
      svg.push(txt(X(gx), m.t + ih + 18, gx, "middle"));
    }
    // y ticks
    for (var gy = Math.ceil(ymin / 20) * 20; gy <= ymax; gy += 20) {
      svg.push(line(m.l - 5, Y(gy), m.l, Y(gy)));
      svg.push(txt(m.l - 9, Y(gy) + 4, gy, "end"));
    }
    svg.push(txt(m.l + iw / 2, H - 6, UI.scatterX, "middle", "axis"));
    svg.push('<text x="' + (16) + '" y="' + (m.t + ih / 2) + '" transform="rotate(-90 16 ' + (m.t + ih / 2) + ')" text-anchor="middle" class="axis">' + esc(UI.scatterY) + "</text>");
    // points
    pts.forEach(function (p) {
      var c = GROUP_COLOR[p.group] || "#888";
      svg.push('<circle class="dot" cx="' + X(p.met).toFixed(1) + '" cy="' + Y(p.diaas).toFixed(1) +
        '" r="5" fill="' + c + '" fill-opacity="0.78" data-slug="' + p.slug + '"><title>' +
        esc(nameOf(p)) + " · Met " + p.met + " · DIAAS " + p.diaas + "</title></circle>");
    });
    svg.push("</svg>");
    host.innerHTML = svg.join("");

    host.querySelectorAll(".dot").forEach(function (d) {
      d.addEventListener("click", function () {
        location.href = "foods/" + d.dataset.slug + "/";
      });
    });

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

  buildScatter();
})();
