// Poll the check status while the pipeline runs; reload when the stage or status changes.
(function () {
  const box = document.getElementById("progress");
  if (!box) return;
  const id = box.dataset.id;
  const stageEl = document.getElementById("stage");
  let lastStage = stageEl.textContent, lastClaims = 0;
  async function tick() {
    try {
      const r = await fetch(`/api/checks/${id}`);
      const c = await r.json();
      const n = (c.claims || []).length;
      if (c.status === "done" || c.status === "error" || n !== lastClaims || (c.content && !document.querySelector(".meta"))) {
        location.reload();
        return;
      }
      if (c.stage !== lastStage) { stageEl.textContent = c.stage; lastStage = c.stage; }
      lastClaims = n;
    } catch (e) { /* network hiccup: try again */ }
    setTimeout(tick, 2000);
  }
  setTimeout(tick, 2000);
})();
