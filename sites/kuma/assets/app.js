/* kuma-sokuho.com: remembers one "my prefecture" in this browser only (localStorage). The site works without it. */
(function () {
  var KEY = "kuma.mypref";
  function load() { try { return JSON.parse(localStorage.getItem(KEY) || "null"); } catch (e) { return null; } }
  function save(v) { try { if (v) localStorage.setItem(KEY, JSON.stringify(v)); else localStorage.removeItem(KEY); } catch (e) {} }
  var btn = document.querySelector("[data-mypref-toggle]");
  if (btn) {
    var me = { slug: btn.getAttribute("data-slug"), name: btn.getAttribute("data-name") };
    var sync = function () {
      var cur = load();
      var on = !!cur && cur.slug === me.slug;
      btn.setAttribute("aria-pressed", on ? "true" : "false");
      btn.textContent = on ? "マイ都道府県に設定中(解除する)" : "この県を「マイ都道府県」にする";
    };
    btn.hidden = false;
    btn.addEventListener("click", function () {
      var cur = load();
      save(cur && cur.slug === me.slug ? null : me);
      sync();
    });
    sync();
  }
  var box = document.getElementById("mypref");
  if (box) {
    var tiles = {};
    Array.prototype.forEach.call(document.querySelectorAll("svg.tilemap a[data-slug]"), function (a) {
      tiles[a.getAttribute("data-slug")] = { slug: a.getAttribute("data-slug"), name: a.getAttribute("data-name"), line: a.getAttribute("data-line") };
    });
    var pick = box.querySelector("select");
    var body = box.querySelector(".mp-body");
    var render = function () {
      var cur = load();
      if (cur && tiles[cur.slug]) {
        var t = tiles[cur.slug];
        body.innerHTML = "";
        var s = document.createElement("span"); s.textContent = t.line;
        var a = document.createElement("a"); a.href = "/" + t.slug + "/"; a.textContent = t.name + "のページを見る";
        body.appendChild(s); body.appendChild(a);
        pick.value = cur.slug;
      } else {
        body.textContent = "都道府県を選ぶと、次から、その県の数字と公式ページへの案内を、ここに表示します(この端末にだけ保存します)。";
      }
    };
    Object.keys(tiles).forEach(function (k) {
      var o = document.createElement("option"); o.value = k; o.textContent = tiles[k].name; pick.appendChild(o);
    });
    pick.addEventListener("change", function () { if (pick.value) { save({ slug: pick.value, name: tiles[pick.value].name }); render(); } });
    box.hidden = false;
    render();
  }
})();
