/* Reader footer placement and oversized exercise expressions. */
(() => {
  "use strict";

  async function initialise() {
    if (!document.body.classList.contains("ds-lecture-notes")) return;
    const main = document.querySelector("#quarto-document-content");
    if (!main) return;

    const navigation = main.querySelector(".ds-chapter-navigation");
    if (navigation) main.appendChild(navigation);

    try { await window.MathJax?.startup?.promise; } catch (_) { /* Keep the text readable if typesetting fails. */ }
    await document.fonts.ready;
    const paragraphs = [...main.querySelectorAll(".ds-exercises p")]
      .filter(p => p.querySelector(".math.inline"));
    let frame = 0;
    let width = main.getBoundingClientRect().width;

    function update() {
      frame = 0;
      for (const p of paragraphs) p.classList.remove("ds-wide-expression");
      const wide = paragraphs.filter(p => [...p.querySelectorAll(".math.inline")]
        .some(math => math.getBoundingClientRect().width > p.clientWidth + 1));
      for (const p of wide) p.classList.add("ds-wide-expression");
    }

    function schedule() {
      if (!frame) frame = window.requestAnimationFrame(update);
    }

    update();
    if (window.ResizeObserver) {
      const observer = new ResizeObserver(entries => {
        const nextWidth = entries[0].contentRect.width;
        if (Math.abs(nextWidth - width) > 0.5) {
          width = nextWidth;
          schedule();
        }
      });
      observer.observe(main);
    } else {
      window.addEventListener("resize", schedule, { passive: true });
    }
  }

  if (document.readyState === "complete") initialise();
  else window.addEventListener("load", initialise, { once: true });
})();
