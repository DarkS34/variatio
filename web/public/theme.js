// The same decision `state/theme.ts` makes, taken before the stylesheet paints, so a dark
// preference does not flash the light ground first. It is a file and not an inline script
// because the API serves the app under `script-src 'self'`: inline, the browser blocks it
// and the ground flashes on every load.
(function () {
  var media = matchMedia("(prefers-color-scheme: dark)");
  var pref = localStorage.getItem("vg.theme");
  var dark = pref === "dark" || (pref !== "light" && media.matches);
  document.documentElement.dataset.theme = dark ? "dark" : "light";

  // The favicon follows the BROWSER and never `vg.theme`: it is drawn on the tab strip,
  // which belongs to the browser's theme and not to the page's — a page forced to light
  // inside a dark browser still sits in a dark strip.
  //
  // Swapped from here rather than left to a `prefers-color-scheme` query inside the SVG,
  // which is what the file used to carry: Chromium rasterises a favicon without matching
  // that query, so the dark ink stayed dark on a dark strip and the mark disappeared. One
  // mechanism and not two that can disagree, which is why neither file carries the query
  // any more.
  var icon = document.querySelector("link[rel='icon']");
  var paint = function () {
    if (icon) icon.href = media.matches ? "/favicon-dark.svg" : "/favicon.svg";
  };
  paint();
  media.addEventListener("change", paint);
})();
