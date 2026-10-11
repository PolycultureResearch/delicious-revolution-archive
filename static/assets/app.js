// One shared player for the episode list, plus the search filter.
(function () {
  var audio = document.getElementById("audio");
  var player = document.getElementById("player");
  var now = document.getElementById("now");
  var current = null;

  if (audio) {
    document.addEventListener("click", function (ev) {
      var btn = ev.target.closest(".play");
      if (!btn) return;
      if (current === btn) {
        audio.paused ? audio.play() : audio.pause();
        return;
      }
      if (current) current.classList.remove("is-playing");
      current = btn;
      audio.src = btn.dataset.src;
      now.textContent = btn.dataset.title;
      player.hidden = false;
      audio.play();
    });
    audio.addEventListener("play", function () { if (current) current.classList.add("is-playing"); });
    audio.addEventListener("pause", function () { if (current) current.classList.remove("is-playing"); });
    audio.addEventListener("ended", function () { if (current) current.classList.remove("is-playing"); });
  }

  var q = document.getElementById("q");
  if (q) {
    var status = document.getElementById("find-status");
    var eps = Array.prototype.slice.call(document.querySelectorAll(".ep"));
    var seasons = Array.prototype.slice.call(document.querySelectorAll(".season"));
    q.addEventListener("input", function () {
      var terms = q.value.toLowerCase().trim().split(/\s+/).filter(Boolean);
      var shown = 0;
      eps.forEach(function (li) {
        var hay = li.dataset.search;
        var hit = terms.every(function (t) { return hay.indexOf(t) !== -1; });
        li.hidden = !hit;
        if (hit) shown++;
      });
      seasons.forEach(function (s) { s.hidden = !s.querySelector(".ep:not([hidden])"); });
      status.textContent = terms.length ? (shown ? shown + " of " + eps.length + " episodes" : "No episodes match. Try a guest's name or a single word.") : "";
    });
  }
})();
