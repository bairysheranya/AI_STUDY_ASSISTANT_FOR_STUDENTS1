/* ============================================================
   StudyAI — app.js
   All client-side functionality in one file
   ============================================================ */
"use strict";

/* ── Flash auto-dismiss ──────────────────────────────────────*/
function initFlash() {
  document.querySelectorAll(".flash").forEach(function(el) {
    setTimeout(function() {
      el.style.transition = "opacity .4s, transform .4s";
      el.style.opacity = "0";
      el.style.transform = "translateX(110%)";
      setTimeout(function() { el.remove(); }, 420);
    }, 4500);
  });
}

/* ── Mobile sidebar ──────────────────────────────────────────*/
function initSidebar() {
  var ham     = document.getElementById("ham");
  var sidebar = document.getElementById("sidebar");
  var overlay = document.getElementById("overlay");
  if (!ham || !sidebar) return;

  ham.addEventListener("click", function() {
    sidebar.classList.toggle("open");
    if (overlay) overlay.classList.toggle("visible");
  });
  if (overlay) {
    overlay.addEventListener("click", function() {
      sidebar.classList.remove("open");
      overlay.classList.remove("visible");
    });
  }
}

/* ── Upload drag-and-drop ────────────────────────────────────*/
function initUpload() {
  var zone  = document.getElementById("drop-zone");
  var input = document.getElementById("file-input");
  var chosen = document.getElementById("file-chosen");
  if (!zone || !input) return;

  zone.addEventListener("click", function() { input.click(); });

  zone.addEventListener("dragover", function(e) {
    e.preventDefault();
    zone.classList.add("over");
  });
  zone.addEventListener("dragleave", function() {
    zone.classList.remove("over");
  });
  zone.addEventListener("drop", function(e) {
    e.preventDefault();
    zone.classList.remove("over");
    if (e.dataTransfer.files.length) {
      input.files = e.dataTransfer.files;
      showChosen(e.dataTransfer.files[0].name);
    }
  });
  input.addEventListener("change", function() {
    if (input.files.length) showChosen(input.files[0].name);
  });

  function showChosen(name) {
    if (chosen) {
      chosen.textContent = "Selected: " + name;
      chosen.style.display = "block";
    }
    var hint = zone.querySelector(".dz-text");
    if (hint) hint.innerHTML = "<strong>File ready:</strong> " + esc(name);
  }
}

/* ── Quiz timer ──────────────────────────────────────────────*/
var _secs = 0, _timer = null;

function initTimer() {
  var el = document.getElementById("timer");
  if (!el) return;
  _secs = 0;
  _timer = setInterval(function() {
    _secs++;
    var m = String(Math.floor(_secs / 60)).padStart(2, "0");
    var s = String(_secs % 60).padStart(2, "0");
    el.textContent = m + ":" + s;
  }, 1000);
}

/* ── Quiz form submit ────────────────────────────────────────*/
function initQuiz() {
  var form   = document.getElementById("quiz-form");
  var result = document.getElementById("quiz-result");
  var qdEl   = document.getElementById("qdata");
  if (!form || !qdEl) return;

  var questions = JSON.parse(qdEl.textContent);
  initTimer();

  form.addEventListener("submit", async function(e) {
    e.preventDefault();
    if (_timer) clearInterval(_timer);

    var btn = form.querySelector("[type=submit]");
    btn.disabled = true;
    btn.textContent = "Checking answers…";

    var answers = {};
    questions.forEach(function(q, i) {
      if (q.type === "mcq") {
        var sel = form.querySelector("input[name='q" + i + "']:checked");
        answers[i] = sel ? sel.value : "";
      } else {
        var inp = form.querySelector("input[name='q" + i + "']");
        answers[i] = inp ? inp.value.trim() : "";
      }
    });

    try {
      var resp = await fetch("/quiz/submit", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ questions: questions, answers: answers })
      });
      var data = await resp.json();
      renderResult(data, form, result);
    } catch (err) {
      alert("Network error — please try again.");
      btn.disabled = false;
      btn.textContent = "Submit Quiz";
    }
  });
}

function renderResult(data, form, el) {
  if (!el) return;
  var score = data.score, correct = data.correct, total = data.total, weak = data.weak || [];
  var emoji = score >= 80 ? "🏆" : score >= 60 ? "👍" : "📚";
  var label = score >= 80 ? "Excellent!" : score >= 60 ? "Good job!" : "Keep studying!";
  var time  = _secs > 0 ? " &nbsp;·&nbsp; Time: <strong>" + Math.floor(_secs/60) + "m " + (_secs%60) + "s</strong>" : "";

  var weakHtml = "";
  if (weak.length) {
    var rows = weak.map(function(w) {
      return '<div class="weak-result-item"><span style="font-size:1.1rem;flex-shrink:0">🔍</span>' +
        '<div><div class="wri-topic">' + esc(w.topic) + '</div>' +
        '<div class="wri-sug">' + esc(w.suggestion || "Review this topic.") + '</div></div></div>';
    }).join("");
    weakHtml = '<div style="margin-top:1.25rem;text-align:left">' +
      '<h4 style="font-family:\'DM Sans\',sans-serif;color:var(--rose);margin-bottom:.6rem;font-size:.9rem">⚠️ Weak Topics Detected</h4>' +
      rows + '</div>';
  }

  el.innerHTML =
    '<div class="card result-center" style="padding:2rem">' +
    '<div class="score-ring"><div class="score-pct">' + score + '%</div><div class="score-lbl">Score</div></div>' +
    '<div style="font-size:1.3rem;margin-bottom:.3rem">' + emoji + '</div>' +
    '<h3 style="font-family:\'DM Sans\',sans-serif;margin-bottom:.3rem">' + label + '</h3>' +
    '<p class="hint">You got <strong>' + correct + '</strong> of <strong>' + total + '</strong> correct.' + time + '</p>' +
    weakHtml +
    '<div style="display:flex;gap:.75rem;justify-content:center;margin-top:1.25rem;flex-wrap:wrap">' +
    '<a href="/upload" class="btn btn-outline">📚 Review Notes</a>' +
    '<a href="/quiz" class="btn btn-primary">🔄 New Quiz</a></div></div>';

  form.style.display = "none";
  el.scrollIntoView({ behavior: "smooth", block: "start" });
}

/* ── Delete note ─────────────────────────────────────────────*/
function initDeleteNote() {
  document.querySelectorAll(".del-btn").forEach(function(btn) {
    btn.addEventListener("click", async function() {
      if (!confirm("Delete this note permanently?")) return;
      var id  = btn.dataset.id;
      var row = document.getElementById("note-" + id);
      try {
        var r = await fetch("/api/notes/" + id, { method: "DELETE" });
        var d = await r.json();
        if (d.success && row) {
          row.style.transition = "opacity .3s, transform .3s";
          row.style.opacity    = "0";
          row.style.transform  = "translateX(30px)";
          setTimeout(function() { row.remove(); }, 320);
        }
      } catch (e) {
        alert("Could not delete — please try again.");
      }
    });
  });
}

/* ── Copy text ───────────────────────────────────────────────*/
function copyText(id) {
  var el = document.getElementById(id);
  if (!el) return;
  var text = el.innerText || el.textContent;
  if (navigator.clipboard) {
    navigator.clipboard.writeText(text).catch(function() { fallbackCopy(text); });
  } else {
    fallbackCopy(text);
  }
  // Visual feedback
  var btns = document.querySelectorAll("[onclick=\"copyText('" + id + "')\"]");
  btns.forEach(function(b) {
    var orig = b.textContent;
    b.textContent = "✅ Copied!";
    setTimeout(function() { b.textContent = orig; }, 2000);
  });
}

function fallbackCopy(text) {
  var ta = document.createElement("textarea");
  ta.value = text; ta.style.position = "fixed"; ta.style.opacity = "0";
  document.body.appendChild(ta); ta.select();
  try { document.execCommand("copy"); } catch (e) {}
  document.body.removeChild(ta);
}

/* ── Difficulty bar animation ────────────────────────────────*/
function initDiffBar() {
  document.querySelectorAll(".diff-fill[data-score]").forEach(function(el) {
    setTimeout(function() {
      el.style.width = Math.min(parseInt(el.dataset.score, 10) * 10, 100) + "%";
    }, 350);
  });
}

/* ── Concept map ─────────────────────────────────────────────*/
function drawConceptMap(data, containerId) {
  var container = document.getElementById(containerId);
  if (!container || !data) return;

  var nodes = data.nodes || [];
  var W = container.offsetWidth  || 780;
  var H = container.offsetHeight || 500;
  var CX = W / 2, CY = H / 2;

  /* Position nodes radially by level */
  var byLevel = {};
  nodes.forEach(function(n) {
    if (!byLevel[n.level]) byLevel[n.level] = [];
    byLevel[n.level].push(n);
  });
  var radii = [0, 148, 275, 380];
  var pos = {};
  Object.keys(byLevel).sort(function(a,b){return a-b;}).forEach(function(lv) {
    var li = parseInt(lv, 10);
    var group = byLevel[lv];
    var r = radii[li] !== undefined ? radii[li] : li * 130;
    group.forEach(function(node, idx) {
      var angle = (2 * Math.PI * idx / group.length) - Math.PI / 2;
      pos[node.id] = { x: CX + r * Math.cos(angle), y: CY + r * Math.sin(angle), node: node };
    });
  });

  var NS = "http://www.w3.org/2000/svg";
  var svg = document.createElementNS(NS, "svg");
  svg.setAttribute("viewBox", "0 0 " + W + " " + H);
  svg.style.width  = "100%";
  svg.style.height = "100%";

  /* Glow filter */
  var defs = document.createElementNS(NS, "defs");
  defs.innerHTML = '<filter id="glow"><feGaussianBlur stdDeviation="3" result="b"/>' +
    '<feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>';
  svg.appendChild(defs);

  /* Edges */
  nodes.forEach(function(node) {
    if (node.parent === null || node.parent === undefined) return;
    var p = pos[node.parent], c = pos[node.id];
    if (!p || !c) return;
    var line = document.createElementNS(NS, "line");
    line.setAttribute("x1", p.x); line.setAttribute("y1", p.y);
    line.setAttribute("x2", c.x); line.setAttribute("y2", c.y);
    line.setAttribute("stroke", "#e2e8f0"); line.setAttribute("stroke-width", "1.5");
    svg.appendChild(line);
  });

  /* Nodes */
  Object.values(pos).forEach(function(p) {
    var node    = p.node;
    var isRoot  = node.level === 0;
    var isSub   = node.level === 1;
    var r       = isRoot ? 44 : isSub ? 36 : 28;
    var fill    = isRoot ? "#f4a824" : isSub ? "#0d1b2a" : "#243447";
    var stroke  = isRoot ? "#e09a1a" : "rgba(255,255,255,.1)";
    var tc      = isRoot ? "#1a1200" : "#ffffff";
    var fs      = isRoot ? 11.5 : isSub ? 10 : 9;
    var fw      = isRoot ? "800" : isSub ? "600" : "500";

    var g = document.createElementNS(NS, "g");
    g.style.cursor = "pointer";

    var circle = document.createElementNS(NS, "circle");
    circle.setAttribute("cx", p.x); circle.setAttribute("cy", p.y);
    circle.setAttribute("r", r);
    circle.setAttribute("fill", fill);
    circle.setAttribute("stroke", stroke);
    circle.setAttribute("stroke-width", "1.5");
    g.appendChild(circle);

    /* Word-wrap label */
    var words = (node.label || "").split(" ");
    var lines = [], cur = "";
    var maxCh = isRoot ? 10 : 11;
    words.forEach(function(w) {
      if ((cur + " " + w).trim().length > maxCh && cur) {
        lines.push(cur.trim()); cur = w;
      } else { cur += " " + w; }
    });
    if (cur.trim()) lines.push(cur.trim());

    var lineH = fs + 3;
    lines.forEach(function(ln, li) {
      var t = document.createElementNS(NS, "text");
      t.setAttribute("x", p.x);
      t.setAttribute("y", p.y + (li - (lines.length - 1) / 2) * lineH);
      t.setAttribute("text-anchor", "middle");
      t.setAttribute("dominant-baseline", "central");
      t.setAttribute("fill", tc);
      t.setAttribute("font-size", fs);
      t.setAttribute("font-family", "'DM Sans',sans-serif");
      t.setAttribute("font-weight", fw);
      t.textContent = ln;
      g.appendChild(t);
    });

    g.addEventListener("mouseenter", function() { circle.setAttribute("filter", "url(#glow)"); });
    g.addEventListener("mouseleave", function() { circle.removeAttribute("filter"); });
    svg.appendChild(g);
  });

  container.innerHTML = "";
  container.appendChild(svg);
}

/* ── Markdown render (for summary + ask pages) ───────────────*/
function renderMarkdown() {
  if (typeof marked === "undefined") return;
  document.querySelectorAll(".ai-card").forEach(function(el) {
    var raw = el.textContent.trim();
    if (raw && raw.length > 10) {
      el.innerHTML = marked.parse(raw);
    }
  });
}

/* ── Utility ─────────────────────────────────────────────────*/
function esc(s) {
  var d = document.createElement("div");
  d.textContent = s;
  return d.innerHTML;
}

/* ── Bootstrap ───────────────────────────────────────────────*/
document.addEventListener("DOMContentLoaded", function() {
  initFlash();
  initSidebar();
  initUpload();
  initQuiz();
  initDeleteNote();
  initDiffBar();
  renderMarkdown();
});
