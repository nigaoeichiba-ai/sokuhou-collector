/* kuma-sokuho.com /search/: type a municipality or prefecture name and the table of municipalities narrows to the rows that contain it.
   The table is in the page itself (it works without this script, as a full list); nothing is sent anywhere.  Text is only read and shown/hidden, never written as HTML. */
(function () {
  var tools = document.getElementById("finder-tools");
  var input = document.getElementById("finder-q");
  var table = document.getElementById("finder-table");
  var msg = document.getElementById("finder-msg");
  if (!tools || !input || !table || !msg) return;
  var rows = Array.prototype.slice.call(table.tBodies[0].rows);
  var total = rows.length;

  function norm(s) { return (s || "").normalize("NFKC").toLowerCase().replace(/\s+/g, ""); }
  function apply() {
    var q = norm(input.value);
    var shown = 0;
    rows.forEach(function (tr) {
      var hit = !q || norm(tr.getAttribute("data-q")).indexOf(q) !== -1;
      tr.hidden = !hit;
      if (hit) shown++;
    });
    msg.textContent = q ? (shown ? shown + "件が見つかりました(全" + total + "か所)" : "見つかりません。市町村の名前の一部(例: 盛岡、岩国)か、都道府県の名前で、探してください。") : "全" + total + "か所を、表示しています。";
    var url = new URL(location.href);
    if (q) url.searchParams.set("q", input.value.trim()); else url.searchParams.delete("q");
    history.replaceState(null, "", url.pathname + url.search);
  }

  tools.hidden = false;
  input.addEventListener("input", apply);
  tools.addEventListener("submit", function (e) { e.preventDefault(); apply(); });
  var q0 = new URLSearchParams(location.search).get("q");
  if (q0) input.value = q0;
  apply();
})();
