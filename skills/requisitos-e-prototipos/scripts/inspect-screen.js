(() => {
  const screen = document.querySelector("#screen");
  if (!screen || !screen.children.length || screen.querySelector(".screen-error")) {
    throw new Error("Abra um fluxo renderizado antes de inspecioná-lo.");
  }
  const project = JSON.parse(document.querySelector("#prototype-project").textContent);
  const current = document.querySelector('.flow-btn[aria-current="true"]');
  const query = new URLSearchParams(location.search);
  const flow = current ? project.flows[Number(current.dataset.flow)].id : query.get("flow");
  const title = document.querySelector(".stage-ver")?.textContent;
  const versions = window.Proto.registry[flow] || [];
  const versionFromUrl = Number(query.get("v"));
  const version = versions[versionFromUrl - 1]?.name === title
    ? versionFromUrl : versions.findIndex(entry => entry.name === title) + 1;
  if (!flow || !version) throw new Error("Fluxo ou versão sem identificação.");

  const checks = {transition_properties: true, will_change: true, hit_area: true};
  const violations = [];
  const compositor = new Set(["auto", "transform", "opacity", "filter"]);
  const interactive = 'button, a[href], select, textarea, input:not([type="hidden"]), summary, [role="button"], [role="link"], [role="radio"], [role="checkbox"], [role="switch"], [role="tab"], [role="combobox"], [role="slider"], [contenteditable="true"]';
  const scrollPositions = new Map();
  const previewRect = screen.getBoundingClientRect();
  const scaleX = previewRect.width / screen.offsetWidth || 1;
  const scaleY = previewRect.height / screen.offsetHeight || 1;
  let testedControls = 0;
  function record(check, element, detail) {
    checks[check] = false;
    violations.push({check, element: element.id || element.tagName.toLowerCase(), detail});
  }
  function reveal(area) {
    for (let node = area.parentElement; node; node = node.parentElement) {
      if (!scrollPositions.has(node) && (node.scrollHeight > node.clientHeight || node.scrollWidth > node.clientWidth)) {
        scrollPositions.set(node, [node.scrollLeft, node.scrollTop]);
      }
    }
    area.scrollIntoView({block: "center", inline: "center", behavior: "instant"});
  }
  function hitsControl(element, x, y) {
    const hit = document.elementFromPoint(x, y);
    const target = hit?.closest(interactive);
    return target === element || (!target && hit?.closest("label")?.control === element);
  }
  function hitBox(element) {
    // A label can be beside its control. Probe each candidate where it really
    // receives pointer events. Normalize only the outer viewer's presentation scale.
    const areas = [element, ...Array.from(element.labels || []).filter(label => screen.contains(label))];
    return areas.some(area => {
      if (!area.getClientRects().length) return false;
      reveal(area);
      const rect = area.getBoundingClientRect();
      const cx = rect.x + rect.width / 2;
      const cy = rect.y + rect.height / 2;
      const edges = [[0, 0], [0, -19.5], [0, 19.5], [-19.5, 0], [19.5, 0]];
      return edges.every(([x, y]) => hitsControl(element, cx + x * scaleX, cy + y * scaleY));
    });
  }
  function inspectStyle(element, style, pseudo = "") {
    const props = style.transitionProperty.split(",").map(value => value.trim());
    const durations = style.transitionDuration.split(",").map(parseFloat);
    if (props.some((prop, i) => prop === "all" && durations[i % durations.length] > 0)) {
      record("transition_properties", element, pseudo + " transition: all com duração positiva");
    }
    if (style.willChange.split(",").some(prop => !compositor.has(prop.trim()))) {
      record("will_change", element, pseudo + " " + style.willChange);
    }
  }
  try {
    for (const element of [screen, ...screen.querySelectorAll("*")]) {
      const style = getComputedStyle(element);
      if (!element.getClientRects().length || style.visibility !== "visible") continue;
      inspectStyle(element, style);
      for (const name of ["::before", "::after"]) {
        const pseudo = getComputedStyle(element, name);
        if (pseudo.content !== "normal" && pseudo.content !== "none" && pseudo.display !== "none") {
          inspectStyle(element, pseudo, name);
        }
      }
      if (!element.matches(interactive) || element.matches(":disabled") || element.closest("[inert]")) continue;
      testedControls++;
      if (!hitBox(element)) record("hit_area", element, "Área acionável de 40 × 40 px não demonstrada");
    }
  } finally {
    for (const [node, [left, top]] of scrollPositions) node.scrollTo({left, top, behavior: "instant"});
  }
  return {flow, version, checks, tested_controls: testedControls, violations};
})()
