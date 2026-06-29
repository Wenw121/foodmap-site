/* Site-wide analytics helper.
   Sends GA4 events when gtag is present (i.e. the build had MEASUREMENT_ID set);
   a harmless no-op otherwise, so local/dev builds and JS-only fallbacks are safe.
   Interaction events for the homepage tool live in app.js and call window.track. */
(function () {
  "use strict";

  window.track = function (name, params) {
    try {
      if (typeof window.gtag === "function") {
        window.gtag("event", name, params || {});
      }
    } catch (e) {}
  };

  /* delegated clicks for any element carrying data-event (language_switch,
     source_link_click, tool_cta_click) — capture phase so the event is queued
     before any navigation. */
  document.addEventListener("click", function (e) {
    var t = e.target;
    if (!t || !t.closest) return;
    var el = t.closest("[data-event]");
    if (!el) return;
    var params = {};
    if (el.dataset.label) params.label = el.dataset.label;
    if (el.dataset.to) params.to = el.dataset.to;
    if (el.dataset.from) params.from = el.dataset.from;
    window.track(el.getAttribute("data-event"), params);
  }, true);

  /* food_page_open: fires on every /foods/* load, including direct organic landings. */
  if (document.body && document.body.dataset.page === "food") {
    window.track("food_page_open", { slug: document.body.dataset.slug || "" });
  }
})();
