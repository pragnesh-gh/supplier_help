import {
  WebGLRenderer,
  Scene,
  PerspectiveCamera,
  Group,
  HemisphereLight,
  DirectionalLight,
  MeshStandardMaterial,
  MeshBasicMaterial,
  Mesh,
  BoxGeometry,
  CylinderGeometry,
  BufferGeometry,
  Float32BufferAttribute,
  DoubleSide,
  Color,
  Raycaster,
  Vector2,
  Vector3,
} from "./vendor/three.module.min.js";

export function mountTrain(container, options) {
  // Stretch the carbody and fittings, but keep circular wheel geometry round.
  const lengthScale = 1.45;
  const selectionColor = "#2267e8";
  const defaultYaw = 0, defaultPitch = 0.16;
  const motionPreference = window.matchMedia("(prefers-reduced-motion: reduce)");
  let entranceFrame = 0;
  const viewTarget = new Vector3(-0.25, 1.75, 0);
  // A single entrance orbit, then a stable view with no idle rotation or inertia.
  let counts = options.counts || {},
    selected = options.selected,
    hovered = null,
    disposed = false;
  const regions = options.regions || [],
    byId = new Map(regions.map((r) => [r.id, r]));
  const root = document.createElement("div");
  root.className = "ts-scene";
  container.replaceChildren();
  root.innerHTML = `<style>
.ts-scene{position:relative;width:100%;height:100%;min-height:0;flex:1 1 auto;overflow:hidden;background:radial-gradient(ellipse at 50% 65%,#edf2f3 0%,#f8fafb 65%,#fff 100%);isolation:isolate}.ts-scene canvas{display:block;width:100%;height:100%;touch-action:none;cursor:grab}.ts-scene canvas:active{cursor:grabbing}.ts-scene .ts-tip{position:absolute;z-index:3;pointer-events:none;max-width:270px;padding:9px 12px;border:1px solid #dce2e6;border-radius:6px;background:#fff;color:#1e2a33;box-shadow:0 3px 14px #142d3620;font:12px/1.5 'Segoe UI',sans-serif}.ts-scene .ts-hint{position:absolute;bottom:12px;left:16px;color:#687983;font:12px 'Segoe UI',sans-serif;pointer-events:none}.train-scene .ts-scene .ts-fallback{width:100%;height:100%;display:none!important}.train-scene .ts-scene.ts-failed .ts-fallback{display:block!important}.ts-scene.ts-failed canvas{display:none}.ts-scene .ts-fallback [data-region]{cursor:pointer;stroke:#60727b;stroke-width:1.2;transition:fill .12s}.ts-scene .ts-fallback [data-region].ts-active{stroke:#2267e8;stroke-width:4}.ts-scene .ts-fallback [data-region].ts-hover{stroke:#2267e8;stroke-width:3}.ts-scene .ts-fallback [data-region]:focus{outline:none;stroke:#2563eb;stroke-width:3}@media(prefers-reduced-motion:reduce){.ts-scene .ts-fallback [data-region]{transition:none}}@media print{.ts-scene canvas,.ts-scene .ts-hint,.ts-scene .ts-tip{display:none!important}.train-scene .ts-scene .ts-fallback{display:block!important}}
</style><div class="ts-tip" hidden></div><span class="ts-hint">Drag to rotate · select a system to explore</span>`;
  container.append(root);
  const tip = root.querySelector(".ts-tip"),
    hint = root.querySelector(".ts-hint");
  const svgNS = "http://www.w3.org/2000/svg";
  const svg = document.createElementNS(svgNS, "svg");
  svg.classList.add("ts-fallback");
  svg.setAttribute("aria-hidden", "true");
  svg.setAttribute("inert", "");
  svg.setAttribute("viewBox", "0 0 900 340");
  svg.setAttribute("role", "group");
  svg.setAttribute("aria-label", "Train systems, illustrative side elevation");
  const title = document.createElementNS(svgNS, "title");
  title.textContent = "Train systems — illustrative side elevation";
  svg.append(title);
  function svgShape(id, d, fill) {
    const p = document.createElementNS(svgNS, "path");
    p.setAttribute("d", d);
    p.setAttribute("fill", fill);
    p.dataset.region = id;
    p.setAttribute("tabindex", "0");
    p.setAttribute("role", "button");
    p.setAttribute(
      "aria-label",
      `${byId.get(id)?.label || id}: ${Number(counts[id]?.total || 0).toLocaleString()} records`,
    );
    p.addEventListener("pointerenter", (e) => showTip(id, e));
    p.addEventListener("pointermove", (e) => positionTip(e));
    p.addEventListener("pointerleave", () => setHover(null));
    p.addEventListener("focus", () => {
      setHover(id);
      tip.hidden = true;
    });
    p.addEventListener("blur", () => setHover(null));
    p.addEventListener("click", () => options.onSelect?.(id));
    p.addEventListener("keydown", (e) => {
      if (e.key === "Enter" || e.key === " ") {
        e.preventDefault();
        options.onSelect?.(id);
      }
    });
    svg.append(p);
  }
  svg.innerHTML =
    '<ellipse cx="450" cy="262" rx="400" ry="10" fill="#dce3e6"/><path d="M55 230V151Q55 125 83 125H710Q750 125 781 158L839 214Q852 233 826 233H55Z" fill="#fafbfc" stroke="#8c9da5"/><path d="M56 199H821L838 216H56Z" fill="#cc263a"/>';
  svgShape("carbody", "M60 180H710V198H60Z", "#eef2f4");
  svgShape(
    "interiors",
    "M116 145H243V176H116Z M274 145H401V176H274Z M432 145H559V176H432Z M590 145H680V176H590Z",
    "#233c4c",
  );
  svgShape("doors", "M82 143H105V228H82Z M691 143H717V228H691Z", "#dbe4e8");
  svgShape("control_cab", "M732 143Q755 147 777 174L797 191H732Z", "#233c4c");
  svgShape("hvac", "M402 111H521V124H402Z", "#82949e");
  svgShape(
    "electrical_auxiliary",
    "M225 112H327V124H225Z M240 112L277 83L314 112 M258 83H295",
    "#687b87",
  );
  svgShape("traction", "M270 235H397V254H270Z", "#526674");
  svgShape("braking", "M486 235H576V254H486Z", "#82929d");
  svgShape(
    "bogie_structure",
    "M130 234H233V252H130Z M640 234H743V252H640Z M146 250a16 16 0 1 0 32 0a16 16 0 1 0 -32 0 M194 250a16 16 0 1 0 32 0a16 16 0 1 0 -32 0 M650 250a16 16 0 1 0 32 0a16 16 0 1 0 -32 0 M698 250a16 16 0 1 0 32 0a16 16 0 1 0 -32 0",
    "#344957",
  );
  // Keep the printable / no-WebGL elevation grounded on the same sleeper track.
  const track = document.createElementNS(svgNS, "g");
  for (let x = 50; x <= 850; x += 28) {
    const sleeper = document.createElementNS(svgNS, "rect");
    for (const [key, value] of Object.entries({ x, y: 267, width: 12, height: 12, fill: "#a7afb2" }))
      sleeper.setAttribute(key, value);
    track.append(sleeper);
  }
  const rail = document.createElementNS(svgNS, "path");
  rail.setAttribute("d", "M45 267H865 M45 274H865");
  rail.setAttribute("stroke", "#7a8d97");
  rail.setAttribute("stroke-width", "3");
  track.append(rail);
  svg.insertBefore(track, svg.firstChild);
  root.prepend(svg);
  let fitView = () => {};
  let renderer,
    scene,
    camera,
    assembly,
    resizeObserver,
    frame = 0,
    yaw = defaultYaw,
    pitch = defaultPitch,
    distance = 19,
    drag = null;
  const canvasEvents = new AbortController();
  const meshes = [],
    proxies = [],
    disposables = [];
  function positionTip(e) {
    const r = root.getBoundingClientRect();
    tip.style.left =
      Math.max(8, Math.min(e.clientX - r.left + 14, r.width - 285)) + "px";
    tip.style.top =
      Math.max(8, Math.min(e.clientY - r.top + 14, r.height - 80)) + "px";
  }
  function showTip(id, e) {
    setHover(id);
    const c = counts[id] || {};
    tip.textContent = `${byId.get(id)?.label || id} · ${Number(c.total || 0).toLocaleString()} suppliers assigned · ${c.scored || 0} scored · ${c.researchOnly || 0} research-only · demo assignment`;
    tip.hidden = false;
    if (e) positionTip(e);
  }
  function paint() {
    for (const m of meshes) {
      const active = m.userData.regionId && m.userData.regionId === selected;
      const over = m.userData.regionId && m.userData.regionId === hovered;
      m.material.color.set(m.userData.base);
      if (active) m.material.color.set(selectionColor);
      else if (over) m.material.color.lerp(new Color(selectionColor),0.55);
      m.material.emissive.set(active ? (selectionColor) : "#000000");
      m.material.emissiveIntensity = active ? 0.16 : 0;

    }
    svg.querySelectorAll("[data-region]").forEach((p) => {
      p.classList.toggle("ts-active", p.dataset.region === selected);
      p.classList.toggle("ts-hover", p.dataset.region === hovered);
      p.setAttribute("aria-pressed", String(p.dataset.region === selected));
    });
    requestRender();
  }
  function setHover(id) {
    hovered = id;
    if (!id) tip.hidden = true;
    if (renderer)
      renderer.domElement.style.cursor = drag
        ? "grabbing"
        : id
          ? "pointer"
          : "grab";
    paint();
  }
  function requestRender() {
    if (renderer && !disposed && !frame)
      frame = requestAnimationFrame(() => {
        frame = 0;
        if (renderer && !disposed) renderer.render(scene, camera);
      });
  }
  function releaseWebGL(forceContext = false) {
    stopEntrance();
    if (frame) cancelAnimationFrame(frame);
    frame = 0;
    drag = null;
    resizeObserver?.disconnect();
    resizeObserver = null;
    canvasEvents.abort();
    disposables.splice(0).forEach((asset) => asset.dispose());
    meshes.length = 0;
    proxies.length = 0;
    const previous = renderer;
    renderer = null;
    if (previous) {
      previous.dispose();
      if (forceContext) previous.forceContextLoss();
      previous.domElement.remove();
    }
    scene?.clear();
  }
  function fallback() {
    releaseWebGL();
    root.classList.add("ts-failed");
    svg.removeAttribute("aria-hidden");
    svg.removeAttribute("inert");
    tip.hidden = true;
    hint.textContent = "Illustrative side elevation · select a system";
    if (frame) cancelAnimationFrame(frame);
    frame = 0;
  }
  function cameraView() {
    if (!renderer) return;
    camera.position.set(
      viewTarget.x + Math.sin(yaw) * distance,
      viewTarget.y + Math.sin(pitch) * distance,
      Math.cos(yaw) * distance,
    );
    camera.lookAt(viewTarget);
    camera.updateMatrixWorld();
    requestRender();
  }
  function stopEntrance() {
    if (entranceFrame) cancelAnimationFrame(entranceFrame);
    entranceFrame = 0;
    root.dataset.entrance = "complete";
  }
  function motionChanged(event) {
    if (!event.matches) return;
    stopEntrance();
    yaw = defaultYaw;
    pitch = defaultPitch;
    if (renderer) fitView();
  }
  function startEntrance() {
    if (motionPreference.matches) {
      root.dataset.entrance = "complete";
      return;
    }
    const started = performance.now();
    root.dataset.entrance = "turning";
    function step(time) {
      entranceFrame = 0;
      if (disposed || !renderer) return;
      const t = Math.min(1, (time - started) / 1550);
      const eased = t * t * (3 - 2 * t);
      yaw = defaultYaw - 0.58 * (1 - eased);
      pitch = defaultPitch + 0.24 * (1 - eased);
      fitView();
      if (t < 1) entranceFrame = requestAnimationFrame(step);
      else root.dataset.entrance = "complete";
    }
    step(started);
  }
  try {
    renderer = new WebGLRenderer({
      antialias: true,
      alpha: true,
      powerPreference: "low-power",
    });
    renderer.shadowMap.enabled = true;
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    renderer.setClearColor(0xffffff, 0);
    renderer.domElement.setAttribute("aria-hidden", "true");
    root.prepend(renderer.domElement);
    scene = new Scene();
    camera = new PerspectiveCamera(28, 1, 0.1, 100);
    assembly = new Group();
    scene.add(assembly);
    scene.add(new HemisphereLight(0xffffff, 0x83939c, 2.5));
    const light = new DirectionalLight(0xffffff, 3);
    light.position.set(-6, 12, 9);
    light.castShadow = true;
    light.shadow.mapSize.set(2048, 2048);
    Object.assign(light.shadow.camera, { left: -13, right: 13, top: 8, bottom: -8 });
    light.shadow.bias = -0.001;
    disposables.push(light.shadow);
    scene.add(light);
    function detail(id, geo, x, y, z, color = "#e6e9eb", opacity = 1) {
      const mat = new MeshStandardMaterial({
        color,
        roughness: 0.57,
        metalness: 0.16,
        transparent: opacity < 1,
        opacity,
      });
      if (!(geo instanceof CylinderGeometry)) geo.scale(lengthScale, 1, 1);
      const mesh = new Mesh(geo, mat);
      mesh.castShadow = id !== null;
      mesh.receiveShadow = true;
      mesh.position.set(x * lengthScale, y, z);
      mesh.userData = { regionId: id, base: color };
      assembly.add(mesh);
      meshes.push(mesh);
      disposables.push(geo, mat);
      return mesh;
    }
    function box(id, x, y, z, w, h, d, color, opacity) {
      return detail(id, new BoxGeometry(w, h, d), x, y, z, color, opacity);
    }
    function proxy(id, x, y, z, w, h, d) {
      const geo = new BoxGeometry(w, h, d),
        mat = new MeshBasicMaterial({ visible: false });
      const m = new Mesh(geo, mat);
      geo.scale(lengthScale, 1, 1);
      m.position.set(x * lengthScale, y, z);
      m.userData.regionId = id;
      assembly.add(m);
      proxies.push(m);
      disposables.push(geo, mat);
    }
    const roof = "#667b88",
      body = "#fafbfd",
      glass = "#213b4b";
    // Rounded cross-sections form one continuous shell and a swept, tapered nose.
    const rings = [
      [-6.1, 0.85, 1.08, 2.85],
      [-5.9, 1, 1, 3],
      [3.5, 1, 1, 3],
      [4.25, 0.96, 1.02, 2.92],
      [4.9, 0.8, 1.05, 2.6],
      [5.7, 0.45, 1.12, 1.98],
      [6.2, 0.1, 1.2, 1.48],
    ];
    const vertices = [],
      indices = [],
      n = 24;
    for (const [x, w, low, high] of rings)
      for (let j = 0; j < n; j++) {
        const a = (j / n) * Math.PI * 2,
          s = Math.sin(a),
          c = Math.cos(a);
        vertices.push(
          x,
          low +
            (high - low) *
              (0.5 + 0.5 * Math.sign(s) * Math.pow(Math.abs(s), 0.55)),
          w * Math.sign(c) * Math.pow(Math.abs(c), 0.5),
        );
      }
    for (let k = 0; k < rings.length - 1; k++)
      for (let j = 0; j < n; j++) {
        const a = k * n + j,
          b = k * n + ((j + 1) % n),
          c = (k + 1) * n + j,
          d = (k + 1) * n + ((j + 1) % n);
        indices.push(a, b, c, b, d, c);
      }
    for (let j = 1; j < n - 1; j++) {
      indices.push(0, j + 1, j);
      const a = (rings.length - 1) * n;
      indices.push(a, a + j, a + j + 1);
    }
    const shell = new BufferGeometry();
    shell.setAttribute("position", new Float32BufferAttribute(vertices, 3));
    shell.setIndex(indices);
    shell.computeVertexNormals();
    const skin = detail("carbody", shell, 0, 0, 0, body);
    skin.material.side = DoubleSide;
    for (const z of [-1.01, 1.01]) {
      box("carbody", -1.12, 1.55, z, 9.9, 0.19, 0.03, "#cf263b");
      for (const x of [-4.35, -2.6, -0.85, 0.9, 2.65])
        box("interiors", x, 2.37, z, 1.35, 0.51, 0.035, glass);
      proxy("interiors", -1, 2.37, z * 1.05, 9, 0.6, 0.13);
      proxy("carbody", -1, 1.7, z * 1.04, 8.7, 0.4, 0.12);
      for (const x of [-5.45, 3.55]) {
        box("doors", x, 1.99, z * 1.01, 0.57, 1.65, 0.035, "#e1e8eb");
        box("doors", x, 2.4, z * 1.035, 0.36, 0.48, 0.025, glass);
        box("doors", x, 1.55, z * 1.04, 0.58, 0.19, 0.025, "#cf263b");
        proxy("doors", x, 2, z * 1.09, 0.69, 1.7, 0.15);
      }
      proxy("control_cab", 4.7, 2.18, z * 0.8, 1.7, 1.04, 0.35);
      const stripe = box(
        "carbody",
        4.73,
        1.55,
        z * 0.77,
        1.65,
        0.19,
        0.035,
        "#cf263b",
      );
      stripe.rotation.y = z > 0 ? 0.4 : -0.4;
      box("control_cab", 5.55, 1.39, z * 0.42, 0.3, 0.1, 0.09, "#fff4d5");
    }
    // Glazing follows the actual shell triangles rather than a rotated box.
    // Two panes wrap the upper nose, with a narrow white centre mullion.
    function clipAtX(polygon, boundary, keepAfter) {
      const result = [];
      for (let i = 0; i < polygon.length; i++) {
        const from = polygon[i], to = polygon[(i + 1) % polygon.length];
        const fromInside = keepAfter ? from.x >= boundary : from.x <= boundary;
        const toInside = keepAfter ? to.x >= boundary : to.x <= boundary;
        if (fromInside) result.push(from);
        if (fromInside !== toInside)
          result.push(from.clone().lerp(to, (boundary - from.x) / (to.x - from.x)));
      }
      return result;
    }
    for (const firstAngle of [1, 7]) {
      const glazing = [];
      for (let k = 3; k < 5; k++)
        for (let j = firstAngle; j < firstAngle + 4; j++) {
          const a = k * n + j, b = a + 1, c = a + n, d = c + 1;
          for (const triangle of [[a, b, c], [b, d, c]]) {
            const polygon = clipAtX(clipAtX(triangle.map(index => new Vector3().fromArray(vertices, index * 3)), 4.34, true), 5.18, false);
            // Clip the shell facets themselves, keeping the pane exactly flush.
            // A tiny outward offset prevents z-fighting with the white shell.
            for (const point of polygon) {
              const t = (point.x - rings[k][0]) / (rings[k + 1][0] - rings[k][0]);
              const centreY = ((rings[k][2] + rings[k][3]) * (1 - t) + (rings[k + 1][2] + rings[k + 1][3]) * t) / 2;
              point.add(new Vector3(0, point.y - centreY, point.z).normalize().multiplyScalar(0.008));
            }
            for (let i = 1; i < polygon.length - 1; i++)
              glazing.push(...polygon[0].toArray(), ...polygon[i].toArray(), ...polygon[i + 1].toArray());
          }
        }
      const geometry = new BufferGeometry();
      geometry.setAttribute("position", new Float32BufferAttribute(glazing, 3));
      geometry.computeVertexNormals();
      const pane = detail("control_cab", geometry, 0, 0, 0, glass);
      pane.material.side = DoubleSide;
      pane.material.roughness = 0.24;
    }
    box("hvac", 0.5, 3.09, 0, 2, 0.22, 1.2, "#a1afb7");
    proxy("hvac", 0.5, 3.1, 0, 2.2, 0.35, 1.45);
    box("electrical_auxiliary", -3.2, 3.06, 0, 1.6, 0.16, 1.1, roof);
    for (const [x, angle] of [
      [-3.45, 0.65],
      [-2.85, -0.65],
    ]) {
      const m = box("electrical_auxiliary", x, 3.38, 0, 0.8, 0.05, 0.06, roof);
      m.rotation.z = angle;
    }
    box("electrical_auxiliary", -3.15, 3.65, 0, 0.7, 0.045, 1.2, roof);
    proxy("electrical_auxiliary", -3.2, 3.4, 0, 1.8, 0.7, 1.45);
    box("traction", -1.8, 0.81, 0, 2.2, 0.37, 1.4, "#526674");
    proxy("traction", -1.8, 0.8, 0, 2.3, 0.5, 1.9);
    box("braking", 1, 0.81, 0, 1.5, 0.37, 1.4, "#82929d");
    proxy("braking", 1, 0.8, 0, 1.6, 0.5, 1.9);
    // Shallow bogie: horizontal side frames, recessed suspension, steel wheel faces.
    for (const x of [-4.1, 3.6]) {
      box("bogie_structure", x, 0.91, 0, 1.72, 0.12, 1.45, "#35434c");
      for (const z of [-0.65, 0.65]) {
        box("bogie_structure", x, 0.65, z, 1.52, 0.10, 0.15, "#394952");
        for (const dx of [-0.32, 0.32])
          box("bogie_structure", x + dx, 0.80, z * 0.68, 0.20, 0.16, 0.25, "#26333b");
      }
      proxy("bogie_structure", x, 0.55, 0, 1.9, 0.7, 2.05);
      for (const dx of [-0.52, 0.52]) {
        const axle = detail("bogie_structure", new CylinderGeometry(0.065,0.065,1.8,16), x+dx,0.43,0,"#596670");
        axle.rotation.x = Math.PI / 2;
        for (const z of [-0.89, 0.89]) {
          const sign = Math.sign(z);
          for (const [radius, depth, offset, color, id] of [
            [0.34,0.19,0,"#28323a","bogie_structure"],
            [0.30,0.018,0.10,"#7c8990","bogie_structure"],
            [0.245,0.022,0.114,"#3c4851","bogie_structure"],
            [0.09,0.038,0.134,"#86939a","braking"]
          ]) {
            const wheel=detail(id,new CylinderGeometry(radius,radius,depth,40),x+dx,0.43,z+sign*offset,color);
            wheel.rotation.x=Math.PI/2;
            wheel.material.metalness=0.55;
          }
          for(let j=0;j<6;j++) {
            const a=j*Math.PI/3;
            const bolt=detail("bogie_structure",new CylinderGeometry(0.018,0.018,0.018,8),x+dx+Math.cos(a)*0.17/lengthScale,0.43+Math.sin(a)*0.17,z+sign*0.132,"#1d282e");
            bolt.rotation.x=Math.PI/2;
          }
        }
      }
    }
    for (const z of [-0.9, 0.9])
      box(null, 0, 0.07, z, 13.3, 0.04, 0.055, "#c2cdd3");
    // Sleeper tops meet the rails; the wheel treads meet the rail heads.
    for (let x = -6.4; x <= 6.5; x += 0.43)
      box(null, x, -0.005, 0, 0.13, 0.09, 2.65, "#a7afb2");
    box(null, 0, -0.15, 0, 13.7, 0.16, 3.35, "#e4e9e9");
    const raycaster = new Raycaster(),
      pointer = new Vector2();
    function hit(e) {
      const r = renderer.domElement.getBoundingClientRect();
      pointer.set(
        ((e.clientX - r.left) / r.width) * 2 - 1,
        (-(e.clientY - r.top) / r.height) * 2 + 1,
      );
      scene.updateMatrixWorld();
      camera.updateMatrixWorld();
      raycaster.setFromCamera(pointer, camera);
      return (
        raycaster.intersectObjects(proxies, false)[0]?.object.userData
          .regionId || null
      );
    }
    const canvas = renderer.domElement;
    const listenCanvas = (type, callback) => canvas.addEventListener(type, callback, { signal: canvasEvents.signal });
    listenCanvas("webglcontextlost", (e) => {
      if (disposed) return;
      e.preventDefault();
      fallback();
    });
    listenCanvas("pointerdown", (e) => {
      if (e.button !== 0) return;
      stopEntrance();
      drag = { x: e.clientX, y: e.clientY, yaw, pitch, moved: 0 };
      canvas.setPointerCapture(e.pointerId);
      tip.hidden = true;
    });
    listenCanvas("pointermove", (e) => {
      if (drag) {
        const dx = e.clientX - drag.x,
          dy = e.clientY - drag.y;
        drag.moved = Math.max(drag.moved, Math.hypot(dx, dy));
        if (drag.moved >= 4) {
          yaw = Math.max(-0.61, Math.min(0.61, drag.yaw + dx * 0.004));
          pitch = Math.max(0.14, Math.min(0.524, drag.pitch + dy * 0.003));
          resize();
          setHover(null);
        }
      } else {
        const id = hit(e);
        if (id) showTip(id, e);
        else setHover(null);
      }
    });
    listenCanvas("pointerup", (e) => {
      if (!drag) return;
      const click =
        drag.moved < 4 &&
        Math.hypot(e.clientX - drag.x, e.clientY - drag.y) < 4;
      drag = null;
      if (canvas.hasPointerCapture(e.pointerId))
        canvas.releasePointerCapture(e.pointerId);
      if (click) {
        const id = hit(e);
        if (id) options.onSelect?.(id);
      }
    });
    listenCanvas("pointercancel", () => {
      drag = null;
      setHover(null);
    });
    listenCanvas("pointerleave", () => {
      if (!drag) setHover(null);
    });
    function resize() {
      if (!renderer || disposed) return;
      const w = Math.max(1, root.clientWidth),
        h = Math.max(1, root.clientHeight);
      renderer.setSize(w, h, false);
      camera.aspect = w / h;
      camera.fov = 28;
      camera.updateProjectionMatrix();
      // Fit the assembly on resize, preserving its useful size when the app changes card height.
      // The bounds include roof equipment and wheel/rail edges; no orbit-time zoom.
      distance = 19;
      for (let pass = 0; pass < 3; pass++) {
        cameraView();
        let extentX = 0,
          extentY = 0;
        for (const x of [-6.9 * lengthScale, 6.9 * lengthScale])
          for (const y of [-0.23, 3.75])
            for (const z of [-1.7, 1.7]) {
              const point = new Vector3(x, y, z).project(camera);
              extentX = Math.max(extentX, Math.abs(point.x));
              extentY = Math.max(extentY, Math.abs(point.y));
            }
        distance *= Math.max(extentX / 0.92, extentY / 0.84);
      }
      cameraView();
    }
    fitView = resize;
    resizeObserver = new ResizeObserver(resize);
    resizeObserver.observe(root);
    resize();
    startEntrance();
  } catch (error) {
    console.warn("Train WebGL unavailable; using interactive SVG.", error);
    fallback();
  }
  const beforePrint = () => {
    svg.removeAttribute("aria-hidden");
    svg.removeAttribute("inert");
  };
  const afterPrint = () => {
    if (!root.classList.contains("ts-failed")) {
      svg.setAttribute("aria-hidden", "true");
      svg.setAttribute("inert", "");
    }
  };
  window.addEventListener("beforeprint", beforePrint);
  window.addEventListener("afterprint", afterPrint);
  motionPreference.addEventListener("change", motionChanged);
  paint();
  return {
    update(next = {}) {
      if (Object.hasOwn(next, "counts")) counts = next.counts || {};
      if (Object.hasOwn(next, "selected")) selected = next.selected;
      paint();
    },
    highlight(id) {
      setHover(id);
    },
    resetView() {
      stopEntrance();
      yaw = defaultYaw;
      pitch = defaultPitch;
      if (camera) fitView();
      setHover(null);
    },
    destroy() {
      disposed = true;
      motionPreference.removeEventListener("change", motionChanged);
      window.removeEventListener("beforeprint", beforePrint);
      window.removeEventListener("afterprint", afterPrint);
      releaseWebGL(true);
      root.remove();
    },
  };
}
