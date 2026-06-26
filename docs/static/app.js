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
  var aminoSelect = document.getElementById("aminoSelect");
  var aminoMax = document.getElementById("aminoMax");
  var diaasMin = document.getElementById("diaasMin");
  var aminoMaxLabel = document.getElementById("aminoMaxLabel");
  var diaasMinLabel = document.getElementById("diaasMinLabel");
  var presetBtn = document.getElementById("presetHiLo");
  var noResults = document.getElementById("noResults");
  /* amino columns shown all at once in the table; the selector below
     highlights one column and drives the amino slider/preset. */
  var AMINO_COL_KEYS = ["met", "cys", "leu", "bcaa", "arg", "gly", "lys"];

  var curAmino = "all";
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
  /* mark which amino column is currently emphasized by the selector */
  function highlightCol(key) {
    table.querySelectorAll("th.aacol").forEach(function (th) {
      th.classList.toggle("col-active", th.dataset.amino === key);
    });
  }
  /* the selector highlights one column and drives the amino slider/preset */
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
  updateAmino("all");
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

  function esc(s) {
    return String(s).replace(/[&<>"]/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c];
    });
  }
})();
