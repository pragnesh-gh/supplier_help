import * as THREE from "./vendor/three.module.min.js";

// Geometry is illustrative. IDs are exact manifest supplier-filter keys.
export function mountParts(
  root,
  { region, counts = {}, selected = "", onSelect = () => {} },
) {
  const parts = region?.parts || [],
    count = (id) =>
      Number(counts instanceof Map ? counts.get(id) || 0 : counts[id] || 0);
  root.classList.add("parts-assembly");
  root.innerHTML = `<style>.parts-assembly{position:relative;height:100%;min-height:0;min-width:0;overflow:hidden;border-radius:12px;background:radial-gradient(ellipse at 50% 35%,#fafbfd,#e9edf2)}.parts-assembly canvas{display:block;width:100%;height:100%;touch-action:none;cursor:grab}.parts-assembly canvas:active{cursor:grabbing}.parts-assembly .pa-note{position:absolute;left:14px;bottom:10px;font-size:12px;color:#687280;pointer-events:none}.parts-assembly .pa-tip{position:absolute;z-index:2;pointer-events:none;padding:7px 10px;border:1px solid #d8dde5;border-radius:7px;background:#fff;color:#172536;box-shadow:0 3px 12px #23304613;font-size:12px;white-space:nowrap}.parts-assembly svg{width:100%;height:100%}.parts-assembly svg [role=button]{cursor:pointer}.parts-assembly svg [role=button]:focus rect{stroke:#b82d3b;stroke-width:3}</style><div class="pa-note">Illustrative exploded assembly &#183; drag to rotate &#183; select a component</div><div class="pa-tip" hidden></div>`;
  const tip = root.querySelector(".pa-tip");
  let renderer;
  try {
    renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
  } catch {
    return fallback();
  }
  renderer.setPixelRatio(Math.min(devicePixelRatio || 1, 2));
  renderer.setClearColor(0, 0);
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  const canvas = renderer.domElement;
  root.prepend(canvas);
  canvas.setAttribute(
    "aria-label",
    `${region?.label || "System"} illustrative exploded assembly. Use component buttons to filter suppliers.`,
  );
  const scene = new THREE.Scene(),
    camera = new THREE.PerspectiveCamera(33, 1, 0.1, 100),
    assembly = new THREE.Group();
  scene.add(assembly);
  scene.add(new THREE.HemisphereLight(0xffffff, 0x8895a8, 2.6));
  for (const [x, y, z, intensity] of [
    [-4, 8, 6, 3.2],
    [5, 2, -4, 1.4],
  ]) {
    const l = new THREE.DirectionalLight(0xffffff, intensity);
    l.position.set(x, y, z);
    scene.add(l);
  }
  const groups = new Map(),
    meshes = [],
    metal = 0x8b99a9,
    dark = 0x354454,
    rubber = 0x262c34,
    red = 0xb82d3b;
  function add(id, geometry, x, y, z, color = metal, rotation) {
    if (!groups.has(id)) {
      const g = new THREE.Group();
      g.userData.partID = id;
      groups.set(id, g);
      assembly.add(g);
    }
    const m = new THREE.Mesh(
      geometry,
      new THREE.MeshStandardMaterial({
        color,
        metalness: color === rubber ? 0.12 : 0.55,
        roughness: 0.38,
      }),
    );
    m.position.set(x, y, z);
    if (rotation) m.rotation.set(...rotation);
    m.userData = { partID: id, color };
    groups.get(id).add(m);
    meshes.push(m);
    return m;
  }
  const box = (id, x, y, z, w, h, d, c = metal) =>
    add(id, new THREE.BoxGeometry(w, h, d), x, y, z, c);
  const cyl = (id, x, y, z, r, h, c = metal, rot = [0, 0, Math.PI / 2]) =>
    add(id, new THREE.CylinderGeometry(r, r, h, 40), x, y, z, c, rot);
  function line(a, b) {
    const g = new THREE.BufferGeometry().setFromPoints([
        new THREE.Vector3(...a),
        new THREE.Vector3(...b),
      ]),
      l = new THREE.Line(
        g,
        new THREE.LineDashedMaterial({
          color: 0x9aa9bb,
          transparent: true,
          opacity: 0.42,
          dashSize: 0.09,
          gapSize: 0.08,
        }),
      );
    l.computeLineDistances();
    assembly.add(l);
  }
  function spring(id, x, y, z) {
    const pts = [];
    for (let i = 0; i <= 140; i++) {
      const t = i / 140;
      pts.push(
        new THREE.Vector3(
          x + 0.18 * Math.cos(t * Math.PI * 12),
          y + t * 0.6,
          z + 0.18 * Math.sin(t * Math.PI * 12),
        ),
      );
    }
    add(
      id,
      new THREE.TubeGeometry(
        new THREE.CatmullRomCurve3(pts),
        140,
        0.043,
        7,
        false,
      ),
      0,
      0,
      0,
      dark,
    );
  }
  if (region?.id === "bogie_structure") {
    // Longitudinal Z, wheel/axle X. The frame floats above the suspension.
    for (const x of [-0.78, 0.78]) {
      box("bogie_frame", x, 1.05, 0, 0.27, 0.32, 2.65);
      for (const z of [-1, 1]) box("bogie_frame", x, 1.05, z, 0.46, 0.22, 0.5);
    }
    for (const z of [-0.7, 0.7])
      box("bogie_frame", 0, 1.05, z, 1.5, 0.25, 0.22);
    box("bogie_frame", 0, 1.1, 0, 0.65, 0.2, 0.65, dark);
    for (const z of [-1, 1]) {
      cyl("axle", 0, -0.58, z, 0.095, 2.45, dark);
      for (const x of [-1.58, 1.58]) {
        cyl("wheel", x, -0.58, z, 0.5, 0.16, dark);
        cyl("wheel", x + (x < 0 ? 0.09 : -0.09), -0.58, z, 0.43, 0.08, metal);
        cyl("wheel", x, -0.58, z, 0.16, 0.21, metal);
      }
      for (const x of [-0.8, 0.8]) {
        box("axle_bearing", x, -0.47, z, 0.34, 0.3, 0.35, dark);
        cyl("axle_bearing", x, -0.47, z, 0.15, 0.38, metal);
        spring("suspension", x, -0.13, z);
        line([x, -0.4, z], [x, 0.96, z]);
      }
      for (const x of [-1.14, 1.14]) {
        cyl("damper", x, 0.37, z, 0.07, 0.53, red, [0, 0, 0.17]);
        cyl("damper", x, 0.04, z, 0.035, 0.24, metal, [0, 0, 0.17]);
      }
      line([-1.6, -0.58, z], [1.6, -0.58, z]);
    }
  } else
    parts.forEach((p, i) => {
      const x = (i - (parts.length - 1) / 2) * 1.55,
        id = p.id;
      if (id === "door_leaf") {
        for (const z of [-0.18, 0.18]) {
          box(id, x, 0.1, z, 0.66, 1.8, 0.08);
          box(id, x, 0.35, z + 0.05, 0.43, 0.64, 0.035, 0x455e72);
        }
      } else if (id === "door_drive") {
        box(id, x, 0.7, 0, 1.3, 0.14, 0.2);
        cyl(id, x, 0.75, 0.24, 0.15, 0.55, dark);
      } else if (id === "brake_disc") {
        cyl(id, x, 0, 0, 0.65, 0.16);
        cyl(id, x, 0, 0, 0.18, 0.25, dark);
        for (let k = 0; k < 10; k++) {
          const a = (k * Math.PI) / 5;
          box(
            id,
            x + 0.48 * Math.cos(a),
            0.48 * Math.sin(a),
            0.1,
            0.06,
            0.09,
            0.03,
            dark,
          );
        }
      } else if (id === "traction_motor" || id === "transformer") {
        cyl(id, x, 0, 0, 0.48, 0.9);
        for (let k = -3; k <= 3; k++)
          cyl(id, x + k * 0.13, 0, 0, 0.53, 0.025, dark);
        box(id, x, -0.52, 0, 0.9, 0.12, 0.65);
      } else if (id === "pantograph") {
        box(id, x, -0.6, 0, 1.1, 0.1, 0.5, dark);
        for (const sign of [-1, 1])
          box(id, x + sign * 0.22, 0, 0, 0.07, 1.05, 0.08).rotation.z =
            sign * 0.48;
        box(id, x, 0.6, 0, 1.1, 0.08, 0.22);
      } else if (id === "seat") {
        box(id, x, -0.1, 0.2, 0.78, 0.18, 0.7, dark);
        box(id, x, 0.38, -0.13, 0.78, 0.9, 0.18, 0x5c6c81);
        box(id, x, -0.58, 0, 0.08, 0.8, 0.08);
        box(id, x, -0.94, 0, 0.7, 0.08, 0.4);
      } else if (id === "ventilation_fan") {
        cyl(id, x, 0, 0, 0.62, 0.14, dark, [Math.PI / 2, 0, 0]);
        for (let k = 0; k < 6; k++) {
          const a = (k * Math.PI) / 3;
          box(
            id,
            x + 0.28 * Math.cos(a),
            0.28 * Math.sin(a),
            0.12,
            0.5,
            0.14,
            0.05,
          ).rotation.z = a + 0.4;
        }
        cyl(id, x, 0, 0.17, 0.13, 0.12, metal, [Math.PI / 2, 0, 0]);
      } else if (id === "coupler") {
        box(id, x, 0, 0, 1.05, 0.2, 0.23, dark);
        box(id, x + 0.5, 0, 0, 0.32, 0.5, 0.5);
      } else if (id === "body_structure") {
        box(id, x, 0, 0, 1.1, 0.12, 0.8);
        for (const sx of [-0.5, 0.5]) box(id, x + sx, 0.4, 0, 0.07, 0.8, 0.8);
        box(id, x, 0.8, 0, 1.1, 0.1, 0.8);
      } else if (["glazing", "interior_panel", "air_filter"].includes(id)) {
        box(id, x, 0, 0, 1.05, 1.2, 0.1, id === "glazing" ? 0x526b81 : metal);
        for (let j = -4; j <= 4; j++)
          box(id, x + j * 0.1, 0, 0.07, 0.025, 1.05, 0.02, dark);
      } else if (id === "brake_actuator") {
        cyl(id, x, 0, 0, 0.3, 0.6);
        cyl(id, x + 0.42, 0, 0, 0.08, 0.45, dark);
        box(id, x, -0.4, 0, 0.6, 0.1, 0.5);
      } else if (id === "gearbox") {
        box(id, x, 0, 0, 0.7, 0.8, 0.7);
        cyl(id, x + 0.5, 0, 0, 0.12, 0.5, dark);
      } else if (id === "hvac_unit") {
        box(id, x, 0, 0, 1.1, 0.65, 0.8);
        for (const sx of [-0.26, 0.26])
          cyl(id, x + sx, 0.34, 0, 0.2, 0.03, dark, [0, 0, 0]);
      } else {
        box(id, x, 0, 0, 1.05, 0.65, 0.65);
        box(
          id,
          x,
          0.08,
          0.34,
          0.78,
          0.32,
          0.025,
          id.includes("interface") || id.includes("information")
            ? 0x263f52
            : dark,
        );
        for (let j = -2; j <= 2; j++)
          box(
            id,
            x + j * 0.14,
            -0.2,
            0.345,
            0.04,
            0.04,
            0.025,
            j === 2 ? red : metal,
          );
      }
      if (i < parts.length - 1) line([x + 0.57, 0, 0], [x + 0.98, 0, 0]);
    });
  // Move intact component groups from an illustrative assembled arrangement.
  // The mesh geometry is never scaled: wheels, springs and housings keep their shape.
  const assembledOffsets = new Map();
  const bogieOffsets = {
    bogie_frame: [0, -0.52, 0],
    axle: [0, 0.12, 0],
    wheel: [0, 0.12, 0],
    axle_bearing: [0, 0.12, 0],
    suspension: [0, -0.06, 0],
    damper: [0, -0.16, 0],
  };
  [...groups.entries()].forEach(([id, group], i) => {
    const center = new THREE.Box3().setFromObject(group).getCenter(new THREE.Vector3());
    // Other systems start as a compact, layered assembly, then separate laterally.
    const offset = region?.id === "bogie_structure"
      ? new THREE.Vector3(...(bogieOffsets[id] || [0, 0, 0]))
      : new THREE.Vector3(-center.x, 0, (i - (groups.size - 1) / 2) * 0.34);
    assembledOffsets.set(group, offset);
  });
  const guides = assembly.children.filter((child) => child.isLine);
  const motionPreference = window.matchMedia("(prefers-reduced-motion: reduce)");
  let entering = !motionPreference.matches,
    entranceStart = null;
  root.dataset.entrance = entering ? "assembling" : "complete";
  const ease = (t) => t * t * (3 - 2 * t);
  function placeComponents(progress) {
    for (const [group, offset] of assembledOffsets)
      group.position.copy(offset).multiplyScalar(1 - progress);
    for (const guide of guides) guide.material.opacity = 0.42 * progress;
  }
  placeComponents(entering ? 0 : 1);
  let yaw = -0.52,
    pitch = 0.32,
    disposed = false,
    frame = 0,
    drag,
    fallbackController = null;
  function render(time) {
    frame = 0;
    if (disposed) return;
    if (entering) {
      entranceStart ??= time;
      const elapsed = time - entranceStart;
      const turn = ease(Math.min(1, elapsed / 1550));
      const split = ease(THREE.MathUtils.clamp((elapsed - 350) / 1200, 0, 1));
      yaw = -0.52 - 0.65 * (1 - turn);
      placeComponents(split);
      root.dataset.entrance = split ? "splitting" : "assembling";
      if (elapsed >= 1550) finishEntrance();
    }
    assembly.rotation.set(pitch, yaw, 0);
    renderer.render(scene, camera);
    if (entering) invalidate();
  }
  function finishEntrance() {
    if (!entering) return;
    entering = false;
    yaw = -0.52;
    placeComponents(1);
    root.dataset.entrance = "complete";
    // Keep picking accurate if an interaction interrupts between animation frames.
    assembly.rotation.set(pitch, yaw, 0);
    assembly.updateMatrixWorld(true);
    invalidate();
  }
  function motionChanged(event) {
    if (event.matches) finishEntrance();
  }
  motionPreference.addEventListener("change", motionChanged);
  function invalidate() {
    if (!frame) frame = requestAnimationFrame(render);
  }
  function highlight(id = "") {
    if (fallbackController) {
      fallbackController.highlight(id);
      return;
    }
    if (id !== selected) finishEntrance();
    selected = id;
    for (const m of meshes) {
      const active = m.userData.partID === id;
      m.material.color.setHex(active ? red : m.userData.color);
      m.material.emissive.setHex(active ? 0x32070a : 0);
      m.material.transparent = !!id && !active;
      m.material.opacity = id && !active ? 0.38 : 1;
    }
    invalidate();
  }
  function resize() {
    const w = root.clientWidth,
      h = root.clientHeight;
    if (!w || !h) return;
    renderer.setSize(w, h, false);
    camera.aspect = w / h;
    camera.position.set(0, 2.3, Math.max(8.2, 7.8 / camera.aspect));
    camera.lookAt(0, 0.15, 0);
    camera.updateProjectionMatrix();
    invalidate();
  }
  const observer = new ResizeObserver(resize);
  observer.observe(root);
  const ray = new THREE.Raycaster(),
    pointer = new THREE.Vector2();
  function hit(e) {
    const r = canvas.getBoundingClientRect();
    pointer.set(
      ((e.clientX - r.left) / r.width) * 2 - 1,
      (-(e.clientY - r.top) / r.height) * 2 + 1,
    );
    ray.setFromCamera(pointer, camera);
    return ray.intersectObjects(meshes, false)[0]?.object.userData.partID || "";
  }
  function down(e) {
    if (e.button !== 0) return;
    finishEntrance();
    drag = { x: e.clientX, y: e.clientY, yaw, pitch, moved: false };
    canvas.setPointerCapture(e.pointerId);
    tip.hidden = true;
  }
  function move(e) {
    if (drag) {
      const dx = e.clientX - drag.x,
        dy = e.clientY - drag.y;
      if (Math.hypot(dx, dy) > 5) drag.moved = true;
      yaw = THREE.MathUtils.clamp(drag.yaw + dx * 0.008, -1.3, 1.3);
      pitch = THREE.MathUtils.clamp(drag.pitch + dy * 0.006, -0.1, 0.8);
      invalidate();
      return;
    }
    const id = hit(e),
      part = parts.find((p) => p.id === id);
    tip.hidden = !part;
    canvas.style.cursor = part ? "pointer" : "grab";
    if (part) {
      tip.textContent = `${part.label} \u00b7 ${count(id).toLocaleString()} suppliers`;
      const r = root.getBoundingClientRect();
      tip.style.left = `${Math.min(Math.max(8, e.clientX - r.left + 12), Math.max(8, r.width - 240))}px`;
      tip.style.top = `${Math.max(8, e.clientY - r.top - 38)}px`;
    }
  }
  function up(e) {
    if (!drag) return;
    const click = !drag.moved;
    drag = null;
    if (canvas.hasPointerCapture(e.pointerId))
      canvas.releasePointerCapture(e.pointerId);
    if (click) {
      const id = hit(e);
      if (id) onSelect(id === selected ? "" : id);
    }
  }
  function leave() {
    tip.hidden = true;
  }
  function cancel() {
    drag = null;
    tip.hidden = true;
  }
  const handlers = {
    pointerdown: down,
    pointermove: move,
    pointerup: up,
    pointercancel: cancel,
    pointerleave: leave,
  };
  for (const [name, fn] of Object.entries(handlers))
    canvas.addEventListener(name, fn);
  highlight(selected);
  resize();
  // Entrance runs once per mounted system. Filtering preserves this instance.
  function disposeWebGL(releaseContext = false) {
    if (disposed) return;
    disposed = true;
    observer.disconnect();
    entering = false;
    motionPreference.removeEventListener("change", motionChanged);
    cancelAnimationFrame(frame);
    delete root.dataset.entrance;
    for (const [name, fn] of Object.entries(handlers))
      canvas.removeEventListener(name, fn);
    canvas.removeEventListener("webglcontextlost", contextLost);
    scene.traverse((o) => {
      o.geometry?.dispose();
      o.material?.dispose();
    });
    renderer.dispose();
    if (releaseContext) renderer.forceContextLoss();
    canvas.remove();
    tip.hidden = true;
  }
  function contextLost(event) {
    event.preventDefault();
    disposeWebGL();
    fallbackController = fallback();
  }
  canvas.addEventListener("webglcontextlost", contextLost);
  return {
    highlight,
    resetView() {
      if (fallbackController) return;
      finishEntrance();
      yaw = -0.52;
      pitch = 0.32;
      invalidate();
    },
    destroy() {
      disposeWebGL(true);
      if (fallbackController) fallbackController.destroy();
      else {
        root.replaceChildren();
        root.classList.remove("parts-assembly");
      }
    },
  };
  function fallback() {
    root.querySelector(".pa-note").textContent =
      "3D unavailable \u00b7 choose a labelled component";
    const ns = "http://www.w3.org/2000/svg",
      svg = document.createElementNS(ns, "svg");
    svg.setAttribute("viewBox", `0 0 ${Math.max(500, parts.length * 115)} 230`);
    svg.setAttribute(
      "aria-label",
      `${region?.label || "System"} component selection`,
    );
    root.prepend(svg);
    parts.forEach((p, i) => {
      const g = document.createElementNS(ns, "g");
      g.setAttribute("role", "button");
      g.setAttribute("tabindex", "0");
      g.setAttribute("aria-label", `${p.label}, ${count(p.id)} suppliers`);
      g.dataset.part = p.id;
      const rect = document.createElementNS(ns, "rect");
      for (const [k, v] of Object.entries({
        x: 15 + i * 115,
        y: 50 + (i % 2) * 25,
        width: 100,
        height: 95,
        rx: 8,
        fill: "#8b99a9",
      }))
        rect.setAttribute(k, String(v));
      g.append(rect);
      const t = document.createElementNS(ns, "text");
      for (const [k, v] of Object.entries({
        x: 65 + i * 115,
        y: 180,
        "text-anchor": "middle",
        "font-size": 12,
      }))
        t.setAttribute(k, String(v));
      t.textContent = p.label;
      g.append(t);
      const click = () => onSelect(selected === p.id ? "" : p.id);
      g.addEventListener("click", click);
      g.addEventListener("keydown", (e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          click();
        }
      });
      svg.append(g);
    });
    function highlight(id) {
      selected = id;
      svg.querySelectorAll("[data-part]").forEach((g) => {
        g.setAttribute("aria-pressed", String(g.dataset.part === id));
        g.querySelector("rect").setAttribute(
          "fill",
          g.dataset.part === id ? "#b82d3b" : "#8b99a9",
        );
      });
    }
    highlight(selected);
    return {
      highlight,
      resetView() {},
      destroy() {
        root.replaceChildren();
        root.classList.remove("parts-assembly");
      },
    };
  }
}
