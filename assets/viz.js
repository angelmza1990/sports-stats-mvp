/* Small helpers shared by every infographic: DOM, tables, tooltips, resizing. */
window.Viz = (function () {
  "use strict";

  const reduceMotion = matchMedia("(prefers-reduced-motion: reduce)").matches;

  function el(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text != null) node.textContent = text;
    return node;
  }

  /** A small colored key (square, or a short line with cls "line"). */
  function swatch(colorCss, cls) {
    const i = el("i", cls);
    i.style.setProperty("--c", colorCss);
    return i;
  }

  /** Fill a legend container with [{label, color}] items. */
  function legend(containerId, items, kind) {
    const root = document.getElementById(containerId);
    root.replaceChildren();
    items.forEach(({ label, color }) => {
      const item = el("span");
      item.append(swatch(color, kind === "line" ? "line" : ""), document.createTextNode(label));
      root.append(item);
    });
  }

  /** Pill-style tab group. options: [{key, label}] */
  function segmented(containerId, options, initial, onChange) {
    const root = document.getElementById(containerId);
    const buttons = options.map((o) => {
      const b = el("button", null, o.label);
      b.type = "button";
      b.setAttribute("role", "tab");
      b.setAttribute("aria-selected", String(o.key === initial));
      b.addEventListener("click", () => {
        buttons.forEach((x) => x.setAttribute("aria-selected", String(x === b)));
        onChange(o.key);
      });
      root.append(b);
      return b;
    });
  }

  function table(containerId, headers, rows) {
    const root = document.getElementById(containerId);
    const wrap = el("div", "scroll");
    const t = el("table");
    const thead = el("thead");
    const head = el("tr");
    headers.forEach((h) => head.append(el("th", null, h)));
    thead.append(head);
    t.append(thead);
    const body = el("tbody");
    rows.forEach((r) => {
      const tr = el("tr");
      r.forEach((c) => tr.append(el("td", null, c)));
      body.append(tr);
    });
    t.append(body);
    wrap.append(t);
    root.replaceChildren(wrap);
  }

  /** Re-render whenever the container changes width. Returns a function that forces a re-render. */
  function responsive(target, render) {
    const node = typeof target === "string" ? document.getElementById(target) : target;
    let lastWidth = 0;
    const run = () => {
      const width = Math.floor(node.clientWidth);
      if (width && width !== lastWidth) {
        lastWidth = width;
        render(width);
      }
    };
    new ResizeObserver(() => requestAnimationFrame(run)).observe(node);
    run();
    return () => {
      lastWidth = 0;
      run();
    };
  }

  /* ---------- Tooltip ---------- */

  let tip;
  function tipNode() {
    if (!tip) {
      tip = el("div", "tooltip");
      tip.setAttribute("role", "status");
      tip.hidden = true;
      document.body.append(tip);
    }
    return tip;
  }

  function moveTip(event) {
    const t = tipNode();
    let x, y;
    if (event.clientX != null && event.type.startsWith("pointer")) {
      x = event.clientX;
      y = event.clientY;
    } else {
      const r = event.target.getBoundingClientRect();
      x = r.right;
      y = r.top + r.height / 2;
    }
    const { width, height } = t.getBoundingClientRect();
    let left = x + 14;
    let top = y + 14;
    if (left + width > innerWidth - 8) left = x - width - 14;
    if (top + height > innerHeight - 8) top = y - height - 14;
    t.style.left = `${Math.max(8, left)}px`;
    t.style.top = `${Math.max(8, top)}px`;
  }

  function showTip(event, build) {
    const t = tipNode();
    t.replaceChildren();
    build(t);
    t.hidden = false;
    moveTip(event);
  }

  function hideTip() {
    tipNode().hidden = true;
  }

  const ttTitle = (text) => el("div", "tt-title", text);
  const ttNote = (text) => el("div", "tt-note", text);
  function ttRow(colorCss, value, label) {
    const row = el("div", "tt-row");
    row.append(swatch(colorCss), el("b", null, String(value)), document.createTextNode(label));
    return row;
  }

  /** Wire hover + keyboard focus on a d3 selection to the tooltip. */
  function tooltipOn(selection, build) {
    selection
      .attr("tabindex", 0)
      .on("pointerenter pointermove", (event, d) => showTip(event, (t) => build(t, d)))
      .on("focus", (event, d) => showTip(event, (t) => build(t, d)))
      .on("pointerleave blur", hideTip);
  }

  /** Same, for plain DOM elements. */
  function tooltipOnNode(node, build) {
    node.tabIndex = 0;
    const show = (event) => showTip(event, build);
    node.addEventListener("pointerenter", show);
    node.addEventListener("pointermove", show);
    node.addEventListener("focus", show);
    node.addEventListener("pointerleave", hideTip);
    node.addEventListener("blur", hideTip);
  }

  /** Horizontal bar path: 4px rounded data end, square baseline. */
  function barPath(x, y, w, h, r = 4) {
    if (w <= 0) return `M${x},${y}h0v${h}h0Z`;
    const rr = Math.min(r, w, h / 2);
    return `M${x},${y}h${w - rr}a${rr},${rr} 0 0 1 ${rr},${rr}v${h - 2 * rr}a${rr},${rr} 0 0 1 -${rr},${rr}h-${w - rr}Z`;
  }

  /** Vertical column path: rounded top, square baseline at y + h. */
  function columnPath(x, y, w, h, r = 4) {
    if (h <= 0) return `M${x},${y + h}h${w}v0h-${w}Z`;
    const rr = Math.min(r, h, w / 2);
    return `M${x},${y + h}v${-(h - rr)}a${rr},${rr} 0 0 1 ${rr},-${rr}h${w - 2 * rr}a${rr},${rr} 0 0 1 ${rr},${rr}v${h - rr}Z`;
  }

  function isDark() {
    const set = document.documentElement.dataset.theme;
    if (set) return set === "dark";
    return matchMedia("(prefers-color-scheme: dark)").matches;
  }

  /** Run fn whenever the light/dark theme changes (toggle or OS setting). */
  function onThemeChange(fn) {
    document.addEventListener("themechange", fn);
    matchMedia("(prefers-color-scheme: dark)").addEventListener("change", fn);
  }

  return {
    reduceMotion, el, swatch, legend, segmented, table, responsive,
    showTip, hideTip, ttTitle, ttNote, ttRow, tooltipOn, tooltipOnNode,
    barPath, columnPath, isDark, onThemeChange,
  };
})();
