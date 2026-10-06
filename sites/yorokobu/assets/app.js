// Reveal-on-scroll for cards and sections; the page is fully readable without it (.rv only applies once JS adds .js).
(function () {
  var reduced = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  if (reduced || !("IntersectionObserver" in window)) return;
  document.documentElement.classList.add("js");
  var els = document.querySelectorAll(".tile, .chip-ic, .item, .keepsake, ul.check li, ul.warn li");
  var io = new IntersectionObserver(function (entries) {
    entries.forEach(function (e) {
      if (e.isIntersecting) { e.target.classList.add("in"); io.unobserve(e.target); }
    });
  }, { rootMargin: "0px 0px -6% 0px" });
  els.forEach(function (el, i) {
    el.classList.add("rv");
    el.style.transitionDelay = Math.min(i % 8, 7) * 40 + "ms";
    io.observe(el);
  });
  // never leave content hidden (crawlers, screenshots, slow scrolling): everything shows after 1.6 s
  setTimeout(function () { els.forEach(function (el) { el.classList.add("in"); }); }, 1600);
})();

// Gift finder: jump to the occasion x recipient page (and the budget block) when that page exists, else to the occasion page.
(function () {
  var f = document.querySelector("form.finder");
  if (!f) return;
  var pairs = {};
  try { JSON.parse(f.getAttribute("data-pairs") || "[]").forEach(function (k) { pairs[k] = 1; }); } catch (e) {}
  f.addEventListener("submit", function (e) {
    e.preventDefault();
    var o = f.elements.o.value, r = f.elements.r.value, b = f.elements.b.value;
    var key = o + "-" + r;
    location.href = pairs[key] ? "/gift/" + key + "/" + (b ? "#t-" + b : "") : "/occasion/" + o + "/";
  });
})();
