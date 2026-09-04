/* Training tracker — injected by the proxy, never added to the deck source.
 *
 * It watches the grading the deck already does and reports the outcome. It does
 * not grade, does not change what a rep sees, and adds no visible element.
 *
 * ── HOW IT DECIDES WHAT HAPPENED ──────────────────────────────────────────
 * A deck marks an answer by changing the DOM: a class, an aria attribute, a
 * revealed explanation. The generic adapter below reads the most common of
 * those signals. It is a starting point, NOT a verified integration.
 *
 * ── BEFORE TRUSTING THE NUMBERS ───────────────────────────────────────────
 * Open one deck, click a right answer and a wrong one, and check the console
 * with ?tracker=debug. If the events logged do not match what you clicked, add
 * an entry to ADAPTERS keyed by the deck slug. That is the intended extension
 * point — the generic path is deliberately conservative and will report
 * nothing rather than guess when the signal is ambiguous.
 */
(function () {
  "use strict";

  var script = document.currentScript ||
    document.querySelector('script[src*="tracker.js"]');
  if (!script) return;

  var DECK = script.dataset.deck;
  var ENDPOINT = script.dataset.endpoint || "/api/events";
  var DEBUG = /[?&]tracker=debug/.test(location.search);
  var log = function () {
    if (DEBUG) console.log.apply(console, ["[tracker]"].concat([].slice.call(arguments)));
  };

  /* ── per-deck overrides ────────────────────────────────────────────────
   * Fill one in after reading a deck's source. Any field may be omitted.
   *   option:    CSS selector matching a clickable answer option
   *   question:  selector for the element that groups one question's options
   *   verdict(optionEl, questionEl) -> true | false | null   (null = unknown)
   *   index(questionEl) -> zero-based question number
   */
  var ADAPTERS = {
    // "dubai-training-deck-1": { option: ".quiz .opt", question: ".quiz",
    //   verdict: function (el) { return el.classList.contains("is-right"); } },
  };
  var A = ADAPTERS[DECK] || {};

  var OPTION_SEL = A.option ||
    '[data-correct],[data-answer],[data-option],.option,.answer,.choice,.quiz-option,' +
    'li[role="option"],button[role="radio"],label:has(input[type=radio])';
  var QUESTION_SEL = A.question ||
    '[data-question],.question,.quiz,.quiz-question,fieldset,section';

  var RIGHT = /(^|[\s_-])(correct|right|success|is-correct|answer-correct|true)([\s_-]|$)/i;
  var WRONG = /(^|[\s_-])(incorrect|wrong|error|fail|is-wrong|answer-wrong|false)([\s_-]|$)/i;

  function signals(el) {
    if (!el) return "";
    return (el.className || "") + " " + (el.getAttribute("data-state") || "") +
      " " + (el.getAttribute("aria-invalid") === "true" ? "wrong" : "") +
      " " + (el.getAttribute("data-correct") || "");
  }

  /* true / false / null-if-unclear */
  function verdict(optionEl, questionEl) {
    if (A.verdict) return A.verdict(optionEl, questionEl);
    var own = signals(optionEl);
    if (WRONG.test(own)) return false;
    if (RIGHT.test(own)) return true;
    var marked = questionEl && questionEl.querySelector(
      '.correct,.is-correct,.right,[data-correct="true"]');
    if (marked) return marked === optionEl || marked.contains(optionEl);
    return null;
  }

  function questionIndex(questionEl) {
    if (A.index) return A.index(questionEl);
    if (!questionEl) return null;
    var attr = questionEl.getAttribute("data-index") ||
      questionEl.getAttribute("data-question") ||
      questionEl.getAttribute("data-q");
    if (attr !== null && attr !== "" && !isNaN(+attr)) return +attr;
    var peers = document.querySelectorAll(QUESTION_SEL);
    var i = [].indexOf.call(peers, questionEl);
    return i < 0 ? null : i;
  }

  function optionIndex(optionEl, questionEl) {
    var opts = (questionEl || document).querySelectorAll(OPTION_SEL);
    var i = [].indexOf.call(opts, optionEl);
    return i < 0 ? null : i;
  }

  /* ── buffering ─────────────────────────────────────────────────────────
   * Events queue and flush on a timer, on tab-hide and on unload, so a rep who
   * closes the tab mid-deck still has their progress recorded.
   */
  var queue = [];
  var opened = Date.now();
  var lastAt = Date.now();
  var seen = Object.create(null);
  var sending = false;

  function flush(final) {
    if (!queue.length && !final) return;
    var body = JSON.stringify({
      deck: DECK,
      elapsed_ms: Date.now() - opened,
      final: !!final,
      events: queue.splice(0, queue.length)
    });
    if (final && navigator.sendBeacon) {
      navigator.sendBeacon(ENDPOINT, new Blob([body], { type: "application/json" }));
      return;
    }
    if (sending) return;
    sending = true;
    fetch(ENDPOINT, {
      method: "POST", credentials: "same-origin",
      headers: { "content-type": "application/json" }, body: body, keepalive: true
    }).catch(function (e) { log("send failed", e); })
      .then(function () { sending = false; });
  }

  document.addEventListener("click", function (ev) {
    var optionEl = ev.target.closest && ev.target.closest(OPTION_SEL);
    if (!optionEl) return;
    var questionEl = optionEl.closest(QUESTION_SEL);

    /* The deck marks the answer during its own click handler, so read after it. */
    setTimeout(function () {
      var ok = verdict(optionEl, questionEl);
      var qi = questionIndex(questionEl);
      var oi = optionIndex(optionEl, questionEl);
      if (ok === null || qi === null || oi === null) {
        log("ignored — unclear signal", { verdict: ok, question: qi, option: oi });
        return;                       // report nothing rather than guess
      }
      if (seen[qi]) { log("already answered", qi); return; }
      seen[qi] = true;
      var now = Date.now();
      queue.push({ q: qi, chosen: oi, correct: !!ok, ms: now - lastAt });
      lastAt = now;
      log("recorded", queue[queue.length - 1]);
      if (queue.length >= 4) flush(false);
    }, 60);
  }, true);

  setInterval(function () { flush(false); }, 15000);
  document.addEventListener("visibilitychange", function () {
    if (document.visibilityState === "hidden") flush(true);
  });
  window.addEventListener("pagehide", function () { flush(true); });

  log("ready", { deck: DECK, adapter: ADAPTERS[DECK] ? "custom" : "generic" });
})();
