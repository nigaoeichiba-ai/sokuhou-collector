/* The print button of the cheat sheets (/oseibo/ /nenga/): shown only when scripts run, since it cannot work without them. */
(function () {
  Array.prototype.forEach.call(document.querySelectorAll("[data-print]"), function (b) {
    b.hidden = false;
    b.addEventListener("click", function () { window.print(); });
  });
})();
