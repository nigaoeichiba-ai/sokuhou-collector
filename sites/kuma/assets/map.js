/* kuma-sokuho.com /map/: the municipal sightings of the last days on a Geospatial Authority of Japan tile map, and "near me".
   The position of the visitor is used inside this page only (never sent anywhere). Everything is built with textContent, never innerHTML. */
(function () {
  var box = document.getElementById("kuma-map");
  if (!box || !window.L) return;
  var DAY = 86400000;
  var prefSel = document.getElementById("map-pref");
  var nearBtn = document.getElementById("near-btn");
  var nearMsg = document.getElementById("near-msg");
  var nearBox = document.getElementById("near-list");
  var params = new URLSearchParams(location.search);

  var map = L.map(box, { preferCanvas: true, minZoom: 4, maxZoom: 17 }).setView([37.5, 138.5], 5);
  L.tileLayer("https://cyberjapandata.gsi.go.jp/xyz/pale/{z}/{x}/{y}.png", {
    attribution: '<a href="https://maps.gsi.go.jp/development/ichiran.html" target="_blank" rel="noopener">地理院タイル</a>', maxZoom: 17
  }).addTo(map);
  box.querySelectorAll(".map-fallback").forEach(function (e) { e.remove(); });

  var layer = L.layerGroup().addTo(map);
  var userLayer = L.layerGroup().addTo(map);
  var data = null, points = [];

  function daysAgo(p) { return Math.round((Date.parse(data.today) - Date.parse(p[2])) / DAY); }
  function style(p) {
    var k = daysAgo(p);
    if (k <= 7) return { color: "#7f1d1d", fillColor: "#dc2626", radius: 8, fillOpacity: .85, weight: 2 };
    if (k <= 30) return { color: "#9a3412", fillColor: "#f97316", radius: 6, fillOpacity: .75, weight: 1.5 };
    return { color: "#78716c", fillColor: "#d6d3d1", radius: 5, fillOpacity: .7, weight: 1 };
  }
  function label(p) {
    var d = p[2].split("-");
    var k = daysAgo(p);
    return Number(d[1]) + "月" + Number(d[2]) + "日(" + (k <= 0 ? "きょう" : k === 1 ? "きのう" : k + "日前") + ") " + p[5] + p[6].replace(p[5], "") + "(" + p[3] + ")";
  }
  function popup(p) {
    var el = document.createElement("div");
    el.textContent = label(p);
    return el;
  }
  function render() {
    layer.clearLayers();
    var pref = prefSel.value;
    var city = params.get("city") || "";
    var shown = points.filter(function (p) { return (!pref || p[4] === pref) && (!city || p[5] === city); });
    shown.slice().reverse().forEach(function (p) {   // newest drawn last, so it lies on top
      L.circleMarker([p[0], p[1]], style(p)).bindPopup(function () { return popup(p); }).addTo(layer);
    });
    if (shown.length) {
      var b = L.latLngBounds(shown.map(function (p) { return [p[0], p[1]]; }));
      map.fitBounds(b.pad(.1), { maxZoom: 13 });
    }
    return shown;
  }

  fetch("/map/points.json").then(function (r) { return r.json(); }).then(function (j) {
    data = j; points = j.points;
    Object.keys(j.prefs).forEach(function (slug) {
      var o = document.createElement("option"); o.value = slug; o.textContent = j.prefs[slug]; prefSel.appendChild(o);
    });
    if (params.get("pref") && j.prefs[params.get("pref")]) prefSel.value = params.get("pref");
    render();
    prefSel.addEventListener("change", function () { params.delete("city"); render(); });
    if (navigator.geolocation) nearBtn.hidden = false;
  }).catch(function () {
    nearMsg.textContent = "地図のデータを読み込めませんでした。時間をおいて、もう一度お試しください。";
  });

  function km(a, b) {
    var R = 6371, rad = Math.PI / 180;
    var dLat = (b[0] - a[0]) * rad, dLon = (b[1] - a[1]) * rad;
    var h = Math.sin(dLat / 2) * Math.sin(dLat / 2) + Math.cos(a[0] * rad) * Math.cos(b[0] * rad) * Math.sin(dLon / 2) * Math.sin(dLon / 2);
    return 2 * R * Math.asin(Math.sqrt(h));
  }
  nearBtn.addEventListener("click", function () {
    nearMsg.textContent = "現在地を調べています…";
    navigator.geolocation.getCurrentPosition(function (pos) {
      var me = [pos.coords.latitude, pos.coords.longitude];
      var ranked = points.map(function (p) { return { p: p, d: km(me, [p[0], p[1]]) }; }).sort(function (a, b) { return a.d - b.d; });
      var within = ranked.filter(function (x) { return x.d <= 10; }).length;
      var top = ranked.slice(0, 10);
      userLayer.clearLayers();
      L.circleMarker(me, { radius: 9, color: "#1d4ed8", fillColor: "#3b82f6", fillOpacity: .9, weight: 3 }).bindTooltip("現在地").addTo(userLayer);
      var slot = nearBox.querySelector(".near-slot"); slot.textContent = "";
      var list = document.createElement("ol"); list.className = "near-list"; slot.appendChild(list);
      top.forEach(function (x) {
        var li = document.createElement("li");
        li.textContent = "約" + (x.d < 10 ? x.d.toFixed(1) : Math.round(x.d)) + "km: " + label(x.p);
        list.appendChild(li);
      });
      nearBox.hidden = !top.length;
      if (!top.length) { nearMsg.textContent = "この地図には、記録がありません。"; return; }
      nearMsg.textContent = ranked[0].d > 30
        ? "30km以内に、この地図の記録はありません(自治体が公表していない地域は、地図に出ません)。いちばん近い記録を、下に載せています。"
        : "10km以内に、直近" + data.days + "日の記録が" + within + "件あります(自治体が公表しているものだけです)。";
      var b = L.latLngBounds([me].concat(top.slice(0, 5).map(function (x) { return [x.p[0], x.p[1]]; })));
      map.fitBounds(b.pad(.2), { maxZoom: 14 });
    }, function () {
      nearMsg.textContent = "現在地を取得できませんでした。ブラウザの位置情報の許可を確認してください。";
    }, { enableHighAccuracy: false, timeout: 15000, maximumAge: 300000 });
  });
})();
