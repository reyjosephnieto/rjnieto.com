/* Original, decorative research geometry. No dependencies or external assets. */
(() => {
  "use strict";

  function initialise() {
    const body = document.body;
    // The shared include can run on pages with their own Quarto body classes.
    // Mathematical readers retain a static surface and create no canvas.
    if (!body || body.classList.contains("ds-lecture-notes") ||
        document.querySelector(".home-research-backdrop")) return;
    const isHomepage = body.classList.contains("home-research-page");
    const canvas = document.createElement("canvas");
    let context;
    try { context = canvas.getContext("2d", { alpha: false }); } catch (_) { return; }
    if (!context) return;
    body.classList.add("research-background-page");
    const backdrop = document.createElement("div");
    backdrop.className = "home-research-backdrop";
    backdrop.setAttribute("aria-hidden", "true");
    canvas.className = "home-research-canvas";
    canvas.setAttribute("aria-hidden", "true");
    canvas.tabIndex = -1;
    canvas.dataset.frames = "0";
    canvas.dataset.running = "false";
    canvas.dataset.profile = isHomepage ? "home" : "quiet";
    canvas.dataset.layout = "sides";
    backdrop.appendChild(canvas);
    body.insertBefore(backdrop, body.firstChild);

    const motion = window.matchMedia ?
      window.matchMedia("(prefers-reduced-motion: reduce)") : { matches: false };
    let width = 0, height = 0, ratio = 1, mobile = false;
    let contentLeft = 0, contentRight = 0, layoutLeft = 0, layoutRight = 0;
    let nodes = [], faces = [], meshEdges = [], neuralEdges = [], bridgeEdges = [];
    let glow, clock = 0, frames = 0, animation = 0, resizeJob = 0;
    let lastPaint = null, dirty = true, suspended = false;

    // A seeded cloud keeps the composition stable when its canvas is resized.
    function makeGeometry() {
      let seed = 17029;
      const random = () => {
        seed = (1664525 * seed + 1013904223) >>> 0;
        return seed / 4294967296;
      };
      const normal = () => Math.sqrt(-2 * Math.log(Math.max(.00001, random()))) *
        Math.cos(2 * Math.PI * random());
      const clamp = (x, low, high) => Math.max(low, Math.min(high, x));
      const count = mobile ? 45 : Math.min(100, Math.max(80, Math.round(width / 14) + 18));
      const around = mobile ? 8 : 10, across = mobile ? 2 : 3;
      nodes = []; faces = []; meshEdges = []; neuralEdges = []; bridgeEdges = [];
      for (let i = 0; i < around; i++) {
        for (let j = 0; j < across; j++) {
          nodes.push({ kind: "mesh", u: i * 2 * Math.PI / around,
            v: -.27 + .54 * j / (across - 1), radius: 1.1, phase: random() * 6.28 });
        }
      }
      const edgeKeys = new Set();
      function meshEdge(a, b) {
        const key = Math.min(a, b) + ":" + Math.max(a, b);
        if (!edgeKeys.has(key)) { edgeKeys.add(key); meshEdges.push([a, b]); }
      }
      for (let i = 0; i < around; i++) {
        // Reversing the transverse index at the seam gives one half-twist.
        const next = j => i + 1 === around ? across - 1 - j : (i + 1) * across + j;
        for (let j = 0; j < across - 1; j++) {
          const a = i * across + j, b = a + 1, c = next(j), d = next(j + 1);
          faces.push([a, b, c], [b, d, c]);
          [[a, b], [a, c], [b, c], [b, d], [c, d]].forEach(e => meshEdge(...e));
        }
      }

      const perLayer = mobile ? 3 : 6, layerStart = nodes.length;
      for (let layer = 0; layer < 3; layer++) {
        for (let j = 0; j < perLayer; j++) {
          nodes.push({ kind: "neural", side: "right",
            x: (layoutRight + (width - layoutRight) * (.18 + .32 * layer)) / width,
            y: .12 + .76 * j / (perLayer - 1), radius: 1.6,
            phase: random() * 6.28, weight: random() });
        }
      }
      for (let layer = 0; layer < 2; layer++) {
        for (let j = 0; j < perLayer; j++) {
          for (const step of [0, 1]) {
            neuralEdges.push({ a: layerStart + layer * perLayer + j,
              b: layerStart + (layer + 1) * perLayer + (j + step) % perLayer,
              weight: .35 + .65 * random(), phase: random() });
          }
        }
      }
      const bridgePaths = mobile ? 2 : 3, bridgePoints = mobile ? 4 : 5;
      const cloudCount = Math.min(mobile ? 10 : 24,
        count - nodes.length - bridgePaths * bridgePoints);
      for (let i = 0, n = cloudCount; i < n; i++) {
        const side = i % 2 ? "right" : "left";
        const fraction = clamp(.5 + normal() * .22, .08, .92);
        const x = (side === "left" ? layoutLeft * fraction :
          layoutRight + (width - layoutRight) * fraction) / width;
        const y = clamp(.08 + .84 * (i + .5) / n + normal() * .025, .07, .93);
        nodes.push({ kind: "cloud", side, x, y, phase: random() * 6.28,
          radius: .9 + random(), class: y > .51 + .10 * Math.sin((x - .3) * 9) });
      }
      // Several sparse paths carry movement through different reading heights.
      for (let path = 0; path < bridgePaths; path++) {
        const leftAnchor = Math.floor(path * around / bridgePaths) * across;
        for (let i = 0; i < bridgePoints; i++) {
          const fraction = (i + 1) / (bridgePoints + 1);
          const x = layoutLeft * .8 +
            (layoutRight + (width - layoutRight) * .2 - layoutLeft * .8) * fraction;
          const wave = Math.sin(fraction * Math.PI * 2);
          const y = mobile ? (path ? .80 - .55 * fraction - .045 * wave :
            .20 + .55 * fraction + .045 * wave) :
            (path === 0 ? .10 + .34 * fraction + .045 * wave :
              path === 1 ? .45 + .10 * fraction - .09 * wave :
                .90 - .34 * fraction + .045 * wave);
          nodes.push({ kind: "bridge", x: x / width, y,
            phase: random() * 6.28, radius: .8 + random() * .8 });
          bridgeEdges.push([i ? nodes.length - 2 : leftAnchor, nodes.length - 1]);
        }
        bridgeEdges.push([nodes.length - 1,
          layerStart + Math.round(path * (perLayer - 1) / (bridgePaths - 1))]);
      }
      while (nodes.length < count) {
        const side = nodes.length % 2 ? "left" : "right";
        const fraction = .08 + .84 * random();
        const x = (side === "left" ? layoutLeft * fraction :
          layoutRight + (width - layoutRight) * fraction) / width;
        nodes.push({ kind: "field", side, x, y: .08 + .84 * random(),
          phase: random() * 6.28, radius: .8 + random() * .8 });
      }
      canvas.dataset.nodes = String(nodes.length);
      canvas.dataset.bridges = String(bridgePaths);
      canvas.dataset.bridgePaths = String(bridgePaths);
      canvas.dataset.bridgeNodes = String(bridgePaths * bridgePoints);
      canvas.dataset.bridgePulsePairs = String(bridgeEdges.length);
    }

    function positions() {
      const drift = .075 * Math.sin(clock * .085);
      const angle = .35 + clock * .032;
      const tilt = .90 + .12 * Math.sin(clock * .07);
      const scaleX = Math.min(layoutLeft * .34, height * .30);
      const scaleY = Math.min(height * .34, Math.max(layoutLeft * .72, height * .20));
      return nodes.map(node => {
        if (node.kind === "mesh") {
          const ring = 1 + node.v * Math.cos(node.u / 2);
          const x = ring * Math.cos(node.u), y = ring * Math.sin(node.u);
          const z = node.v * Math.sin(node.u / 2);
          const rx = x * Math.cos(angle) + z * Math.sin(angle);
          const rz = -x * Math.sin(angle) + z * Math.cos(angle);
          const ry = y * Math.cos(tilt) - rz * Math.sin(tilt);
          const depth = y * Math.sin(tilt) + rz * Math.cos(tilt);
          const perspective = 2.9 / (2.9 - depth * .30);
          return { x: layoutLeft * .48 + rx * scaleX * perspective,
            y: height * (.43 + drift) + ry * scaleY * .69 * perspective, depth };
        }
        const sideWidth = node.side === "left" ? layoutLeft : width - layoutRight;
        const movement = node.side ? Math.min(width * .011, sideWidth * .055) : width * .011;
        return { x: Math.max(3, Math.min(width - 3,
          width * node.x + movement * Math.sin(clock * .15 + node.phase))),
          y: height * (node.y + drift + .013 * Math.sin(clock * .18 + node.phase)),
          depth: 0 };
      });
    }

    function line(a, b, colour, thickness = 1.5) {
      context.beginPath(); context.moveTo(a.x, a.y); context.lineTo(b.x, b.y);
      context.strokeStyle = colour; context.lineWidth = thickness; context.stroke();
    }

    function pulse(a, b, phase) {
      const opacity = Math.sin(phase * Math.PI) * .72;
      context.beginPath();
      context.arc(a.x + (b.x - a.x) * phase,
        a.y + (b.y - a.y) * phase, 2.5, 0, Math.PI * 2);
      context.fillStyle = "rgba(215,191,135," + opacity + ")";
      context.fill();
    }

    function paint() {
      context.setTransform(ratio, 0, 0, ratio, 0, 0);
      context.fillStyle = "#111b26"; context.fillRect(0, 0, width, height);
      context.fillStyle = glow; context.fillRect(0, 0, width, height);
      const points = positions();
      const flow = height * .075 * Math.sin(clock * .085);
      let left = 0, centre = 0, right = 0, visible = 0;
      for (const point of points) {
        if (point.x < layoutLeft) left++;
        else if (point.x > layoutRight) right++;
        else centre++;
        if (point.x >= 0 && point.x <= width && point.y >= 0 && point.y <= height) visible++;
      }
      canvas.dataset.nodeLeft = String(left);
      canvas.dataset.nodeCentre = String(centre);
      canvas.dataset.nodeRight = String(right);
      canvas.dataset.nodeVisible = String(visible);

      // Density contours and a curved classification boundary share the same field.
      for (const [x, y, span] of [[layoutLeft * .5, height * .68, layoutLeft],
        [layoutRight + (width - layoutRight) * .5, height * .32, width - layoutRight]]) {
        context.save();
        context.translate(x, y + flow);
        context.rotate(-.27 + .03 * Math.sin(clock * .10));
        context.strokeStyle = "rgba(116,188,199,.12)"; context.lineWidth = 1.5;
        for (const extent of [.65, 1, 1.4]) {
          context.beginPath(); context.ellipse(0, 0, Math.max(16, span * .28) * extent,
            height * .14 * extent, 0, 0, Math.PI * 2); context.stroke();
        }
        context.restore();
      }
      context.beginPath();
      for (let i = 0; i <= 28; i++) {
        const fraction = i / 28;
        const x = layoutLeft * .8 +
          (layoutRight + (width - layoutRight) * .2 - layoutLeft * .8) * fraction;
        const y = height * (.25 + .48 * fraction + .06 * Math.sin(fraction * Math.PI * 2)) + flow;
        if (i) context.lineTo(x, y); else context.moveTo(x, y);
      }
      context.strokeStyle = "rgba(113,185,174,.13)"; context.lineWidth = 1.5; context.stroke();

      for (const face of faces) {
        context.beginPath();
        face.forEach((index, i) => {
          const point = points[index];
          if (i) context.lineTo(point.x, point.y); else context.moveTo(point.x, point.y);
        });
        context.closePath(); context.fillStyle = "rgba(77,169,176,.019)"; context.fill();
      }
      for (const [a, b] of meshEdges) line(points[a], points[b], "rgba(123,203,209,.19)");
      for (const [a, b] of bridgeEdges) line(points[a], points[b], "rgba(135,196,213,.12)");

      // Two nearest neighbours per point keep the common graph sparse and bounded.
      const radius = Math.min(155, Math.max(92, width * .13));
      const used = new Set();
      for (let i = 0; i < points.length; i++) {
        const nearest = [];
        for (let j = 0; j < points.length; j++) {
          if (i === j || (nodes[i].kind === "mesh" && nodes[j].kind === "mesh")) continue;
          const dx = points[i].x - points[j].x, dy = points[i].y - points[j].y;
          const distance = dx * dx + dy * dy;
          if (distance >= radius * radius) continue;
          if (!nearest[0] || distance < nearest[0].distance) {
            nearest[1] = nearest[0]; nearest[0] = { index: j, distance };
          } else if (!nearest[1] || distance < nearest[1].distance) {
            nearest[1] = { index: j, distance };
          }
        }
        for (const neighbour of nearest.filter(Boolean)) {
          const j = neighbour.index, key = Math.min(i, j) + ":" + Math.max(i, j);
          if (used.has(key)) continue;
          used.add(key);
          const alpha = .06 + .16 * (1 - Math.sqrt(neighbour.distance) / radius);
          line(points[i], points[j], "rgba(135,196,213," + alpha + ")");
        }
      }
      neuralEdges.forEach((edge, index) => {
        const a = points[edge.a], b = points[edge.b];
        line(a, b, "rgba(105,195,190," + (.08 + edge.weight * .12) + ")", 1.2 + edge.weight * .9);
        if (index % 2 !== 0) return;
        const phase = (clock * .17 + edge.phase) % 1;
        pulse(a, b, phase);
        pulse(b, a, (phase + .5) % 1);
      });
      // Matching counterflows on the mesh add vertical and diagonal movement.
      const meshPulseCount = mobile ? 6 : 12;
      for (let i = 0; i < meshPulseCount; i++) {
        const [from, to] = meshEdges[Math.floor(i * meshEdges.length / meshPulseCount)];
        const phase = (clock * .17 + i * .61803398875) % 1;
        pulse(points[from], points[to], phase);
        pulse(points[to], points[from], (phase + .5) % 1);
      }
      // Half-cycle counterflows keep a moving light on every connecting edge.
      bridgeEdges.forEach(([from, to], index) => {
        const phase = (clock * .17 + index * .38196601125) % 1;
        pulse(points[from], points[to], phase);
        pulse(points[to], points[from], (phase + .5) % 1);
      });
      points.forEach((point, index) => {
        const node = nodes[index];
        context.beginPath(); context.arc(point.x, point.y, node.radius * 3.5, 0, Math.PI * 2);
        context.fillStyle = node.kind === "cloud" && node.class ?
          "rgba(95,185,167,.64)" : "rgba(170,218,230,.60)";
        context.fill();
      });
      frames += 1; canvas.dataset.frames = String(frames);
      dirty = false; body.classList.add("home-research-ready");
    }

    function stop() {
      if (animation) window.cancelAnimationFrame(animation);
      animation = 0; lastPaint = null; canvas.dataset.running = "false";
      canvas.dataset.mode = motion.matches ? "reduced" : "animated";
    }

    function tick(timestamp) {
      animation = 0;
      if (document.hidden || motion.matches || suspended) { stop(); return; }
      const interval = 1000 / (mobile ? 18 : 24);
      if (lastPaint === null) lastPaint = timestamp;
      else if (timestamp - lastPaint >= interval - .5) {
        clock += 2 * Math.min(timestamp - lastPaint, 80) / 1000;
        lastPaint = timestamp; paint();
      }
      animation = window.requestAnimationFrame(tick);
    }

    function reconcile() {
      canvas.dataset.mode = motion.matches ? "reduced" : "animated";
      if (document.hidden || suspended) { stop(); return; }
      if (dirty) paint();
      if (motion.matches) { stop(); return; }
      if (!animation) {
        lastPaint = null; canvas.dataset.running = "true";
        animation = window.requestAnimationFrame(tick);
      }
    }

    function measure() {
      resizeJob = 0;
      const nextWidth = Math.max(1, Math.round(document.documentElement.clientWidth || window.innerWidth));
      const nextHeight = Math.max(1, Math.round(window.innerHeight || document.documentElement.clientHeight));
      const nextRatio = Math.min(window.devicePixelRatio || 1, 1.6,
        Math.sqrt(3000000 / (nextWidth * nextHeight)));
      const main = document.querySelector("#quarto-document-content");
      const bounds = main ? main.getBoundingClientRect() :
        { left: nextWidth * .24, right: nextWidth * .76 };
      const nextLeft = Math.max(0, Math.min(nextWidth, bounds.left));
      const nextRight = Math.max(nextLeft, Math.min(nextWidth, bounds.right));
      if (nextWidth !== width || nextHeight !== height || Math.abs(nextRatio - ratio) > .001 ||
          Math.abs(nextLeft - contentLeft) > .5 || Math.abs(nextRight - contentRight) > .5) {
        width = nextWidth; height = nextHeight; ratio = nextRatio; mobile = width < 700;
        contentLeft = nextLeft; contentRight = nextRight;
        const minimumBand = mobile ? width * .20 : Math.min(width * .18, 92);
        layoutLeft = Math.max(contentLeft, minimumBand);
        layoutRight = Math.min(contentRight, width - minimumBand);
        for (const target of [document.documentElement, body]) {
          target.style.setProperty("--research-content-left", contentLeft + "px");
          target.style.setProperty("--research-content-right", contentRight + "px");
        }
        canvas.dataset.contentLeft = contentLeft.toFixed(1);
        canvas.dataset.contentRight = contentRight.toFixed(1);
        canvas.dataset.layoutLeft = layoutLeft.toFixed(1);
        canvas.dataset.layoutRight = layoutRight.toFixed(1);
        canvas.width = Math.max(1, Math.floor(width * ratio));
        canvas.height = Math.max(1, Math.floor(height * ratio));
        document.documentElement.style.setProperty("--home-research-height", height + "px");
        body.style.setProperty("--home-research-height", height + "px");
        makeGeometry();
        glow = context.createRadialGradient(width * .50, height * .42, 0,
          width * .50, height * .42, Math.max(width, height) * .70);
        glow.addColorStop(0, "rgba(23,66,81,.66)");
        glow.addColorStop(1, "rgba(17,27,38,0)");
        dirty = true;
      }
      reconcile();
    }

    function scheduleMeasure() {
      if (!resizeJob) resizeJob = window.requestAnimationFrame(measure);
    }

    measure();
    window.addEventListener("resize", scheduleMeasure, { passive: true });
    window.addEventListener("orientationchange", scheduleMeasure, { passive: true });
    document.addEventListener("visibilitychange", reconcile);
    window.addEventListener("pagehide", () => { suspended = true; stop(); });
    window.addEventListener("pageshow", () => { suspended = false; scheduleMeasure(); });
    if (motion.addEventListener) motion.addEventListener("change", reconcile);
    else if (motion.addListener) motion.addListener(reconcile);
    if (window.visualViewport) {
      window.visualViewport.addEventListener("resize", scheduleMeasure, { passive: true });
    }
    const main = document.querySelector("#quarto-document-content");
    if (main && window.ResizeObserver) new ResizeObserver(scheduleMeasure).observe(main);
    if (document.fonts && document.fonts.ready) document.fonts.ready.then(scheduleMeasure);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initialise, { once: true });
  } else initialise();
})();
