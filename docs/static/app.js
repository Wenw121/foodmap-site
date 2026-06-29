/* Protein Map — progressive enhancement for the homepage.
   Search / category / amino filters + column sort operate on the static table
   already in the DOM; the compare panel reads the inline JSON payload. */
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
  var noResults = document.getElementById("noResults");
  /* the table shows all amino columns at once, each shaded by its own tertiles */
  var AMINO_COL_KEYS = ["met", "cys", "leu", "bcaa", "arg", "gly", "lys"];

  function aa(tr, key) {
    var v = parseFloat(tr.dataset["aa" + key.charAt(0).toUpperCase() + key.slice(1)]);
    return isNaN(v) ? null : v;
  }
  /* smooth green -> yellow -> red gradient (low -> high), MyFitnessPal-style.
     anchors must match the legend bar in style.css */
  var HEAT_STOPS = [[125, 205, 135], [250, 224, 120], [242, 140, 130]];
  function lerp(a, b, t) { return Math.round(a + (b - a) * t); }
  function heatColor(t) {
    if (t < 0) t = 0; else if (t > 1) t = 1;
    var seg = t <= 0.5 ? 0 : 1;
    var lt = t <= 0.5 ? t / 0.5 : (t - 0.5) / 0.5;
    var a = HEAT_STOPS[seg], b = HEAT_STOPS[seg + 1];
    return "rgb(" + lerp(a[0], b[0], lt) + "," + lerp(a[1], b[1], lt) + "," + lerp(a[2], b[2], lt) + ")";
  }
  /* colour each amino cell on a continuous gradient by its percentile rank
     within its own column, so colours blend smoothly instead of in 3 steps */
  function colorCells() {
    AMINO_COL_KEYS.forEach(function (key) {
      var vals = rows.map(function (r) { return aa(r, key); })
        .filter(function (v) { return v !== null; }).sort(function (a, b) { return a - b; });
      var n = vals.length;
      rows.forEach(function (tr) {
        var cell = tr.querySelector(".aa-" + key);
        if (!cell) return;
        var v = aa(tr, key);
        if (v === null) { cell.style.backgroundColor = ""; return; }
        var idx = 0;
        while (idx < n && vals[idx] < v) idx++;
        var t = n > 1 ? idx / (n - 1) : 0.5;
        cell.style.backgroundColor = heatColor(t);
      });
    });
  }
  /* ---------- filtering (search + category) ---------- */
  function applyFilters() {
    var q = (search.value || "").trim().toLowerCase();
    var cat = catFilter.value;
    var shown = 0;
    rows.forEach(function (tr) {
      var ok = (!q || tr.dataset.search.indexOf(q) !== -1) &&
               (!cat || tr.dataset.cat === cat);
      tr.hidden = !ok;
      if (ok) shown++;
    });
    noResults.hidden = shown !== 0;
  }
  search.addEventListener("input", applyFilters);
  catFilter.addEventListener("input", applyFilters);

  /* ---------- analytics (no-op unless gtag is present) ---------- */
  function track(name, params) { if (window.track) window.track(name, params); }
  var searchTimer;
  search.addEventListener("input", function () {
    clearTimeout(searchTimer);
    searchTimer = setTimeout(function () {
      var q = (search.value || "").trim();
      if (q) track("search_used", { q_len: q.length });
    }, 800);
  });
  catFilter.addEventListener("change", function () {
    track("filter_used", { type: "category", key: catFilter.value || "all" });
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
      track("filter_used", { type: "sort", key: th.dataset.sort, dir: dir });
    });
  });

  /* init */
  colorCells();
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
      track("compare_clicked", { action: cb.checked ? "add" : "remove", count: selected.length });
      renderCompare();
    });
  });
  clearBtn.addEventListener("click", function () {
    selected = [];
    table.querySelectorAll("input.cmp").forEach(function (c) { c.checked = false; });
    track("compare_clicked", { action: "clear" });
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

  function esc(s) {
    return String(s).replace(/[&<>"]/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c];
    });
  }
})();
