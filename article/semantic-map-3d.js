(function () {
  const payload = window.semanticMap3D;
  const container = document.querySelector("[data-semantic-map-3d]");
  if (!container || !payload || !window.THREE) return;

  const records = payload.records || [];
  const tooltip = container.querySelector(".map-tooltip");
  const legend = container.querySelector(".map-legend");
  const clusterFilters = container.querySelector("[data-cluster-filters]");
  const canvasHost = container.querySelector(".map-canvas");
  const yearReadout = container.querySelector("[data-year-readout]");
  const visibleReadout = container.querySelector("[data-visible-readout]");
  const resetViewButton = container.querySelector("[data-reset-map]");
  const resetFiltersButton = container.querySelector("[data-reset-filters]");
  const yearMinInput = container.querySelector("[data-year-min]");
  const yearMaxInput = container.querySelector("[data-year-max]");
  const yearRangeLabel = container.querySelector("[data-year-range-label]");
  const formFilter = container.querySelector("[data-form-filter]");
  const sourceFilter = container.querySelector("[data-source-filter]");
  const signalFilter = container.querySelector("[data-signal-filter]");
  const whoFilter = container.querySelector("[data-who-filter]");

  const colors = payload.clusterColors || {};
  const clusters = Object.keys(colors);
  const allClusterSet = new Set(clusters);
  let activeClusters = new Set(clusters);
  let visibleRecords = records.slice();

  const scene = new THREE.Scene();
  scene.background = new THREE.Color(0xffffff);

  const camera = new THREE.PerspectiveCamera(42, 1, 0.1, 1000);
  const initialCamera = new THREE.Vector3(0, -78, 56);
  camera.position.copy(initialCamera);
  camera.lookAt(0, 0, 0);

  const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
  canvasHost.appendChild(renderer.domElement);

  const group = new THREE.Group();
  scene.add(group);

  const axes = new THREE.Group();
  group.add(axes);

  const axisMaterial = new THREE.LineBasicMaterial({ color: 0xd8dde3, transparent: true, opacity: 0.9 });
  const tickMaterial = new THREE.LineBasicMaterial({ color: 0xb8c0c8, transparent: true, opacity: 0.78 });
  const makeLine = (points, material = axisMaterial) => new THREE.Line(new THREE.BufferGeometry().setFromPoints(points), material);
  axes.add(makeLine([new THREE.Vector3(-34, 0, -25), new THREE.Vector3(34, 0, -25)]));
  axes.add(makeLine([new THREE.Vector3(0, -28, -25), new THREE.Vector3(0, 28, -25)]));
  axes.add(makeLine([new THREE.Vector3(-34, -28, -23), new THREE.Vector3(-34, -28, 24)]));

  const yearSpan = Math.max(1, payload.yearMax - payload.yearMin);
  const yearToZ = (year) => ((year - payload.yearMin) / yearSpan - 0.5) * 46;
  const yearTicks = Array.from(new Set([1950, 1970, 1990, 2010, payload.yearMax]))
    .filter((year) => year >= payload.yearMin && year <= payload.yearMax);

  yearTicks.forEach((year) => {
    const z = yearToZ(year);
    axes.add(makeLine([new THREE.Vector3(-35.4, -28, z), new THREE.Vector3(-32.8, -28, z)], tickMaterial));
    const label = makeTextSprite(String(year), {
      color: "#687078",
      background: "rgba(255,255,255,0.86)",
      fontSize: 34,
    });
    label.position.set(-30.8, -25.8, z);
    label.scale.set(7.2, 2.5, 1);
    axes.add(label);
  });

  const zLabel = makeTextSprite("year", {
    color: "#254f4a",
    background: "rgba(255,255,255,0.9)",
    fontSize: 34,
  });
  zLabel.position.set(-30.8, -25.8, 26.5);
  zLabel.scale.set(7.2, 2.5, 1);
  axes.add(zLabel);

  let pointGeometry = new THREE.BufferGeometry();
  const material = new THREE.PointsMaterial({
    size: 4.6,
    vertexColors: true,
    transparent: true,
    opacity: 0.86,
    sizeAttenuation: false,
  });
  const points = new THREE.Points(pointGeometry, material);
  group.add(points);

  const highlight = new THREE.Mesh(
    new THREE.SphereGeometry(1.15, 24, 16),
    new THREE.MeshBasicMaterial({ color: 0x1f2328, transparent: true, opacity: 0.95 })
  );
  highlight.visible = false;
  group.add(highlight);

  const raycaster = new THREE.Raycaster();
  const highlightBaseRadius = 1.15;
  const cursorRadiusPixels = 7;
  raycaster.params.Points.threshold = 0.8;
  const pointer = new THREE.Vector2();
  let hoveredIndex = -1;
  let pinnedIndex = -1;
  let pinnedPosition = null;
  let isDragging = false;
  let dragMode = "rotate";
  let pointerDown = null;
  let tooltipHasPointer = false;
  let hideTooltipTimer = null;
  let previous = { x: 0, y: 0 };
  let rotationVelocity = { x: 0.0015, y: 0.002 };

  initialiseControls();
  applyFilters();

  function makeTextSprite(text, options) {
    const canvas = document.createElement("canvas");
    canvas.width = 320;
    canvas.height = 128;
    const context = canvas.getContext("2d");
    context.clearRect(0, 0, canvas.width, canvas.height);
    context.fillStyle = options.background || "rgba(255,255,255,0.82)";
    context.fillRect(0, 24, canvas.width, 76);
    context.fillStyle = options.color || "#687078";
    context.font = `700 ${options.fontSize || 32}px Inter, Arial, sans-serif`;
    context.textAlign = "center";
    context.textBaseline = "middle";
    context.fillText(text, canvas.width / 2, 63);
    const texture = new THREE.CanvasTexture(canvas);
    texture.minFilter = THREE.LinearFilter;
    texture.needsUpdate = true;
    return new THREE.Sprite(new THREE.SpriteMaterial({ map: texture, transparent: true }));
  }

  function initialiseControls() {
    legend.innerHTML = clusters
      .map((label) => `<span><i style="background:${colors[label]}"></i>${escapeHtml(label)}</span>`)
      .join("");

    clusterFilters.innerHTML = clusters
      .map((label) => {
        const count = records.filter((record) => record.cluster === label).length;
        return `<button type="button" data-cluster="${escapeHtml(label)}" aria-pressed="true">
          <i style="background:${colors[label]}"></i>${escapeHtml(label)} <b>${count}</b>
        </button>`;
      })
      .join("");

    yearMinInput.min = payload.yearMin;
    yearMinInput.max = payload.yearMax;
    yearMinInput.value = payload.yearMin;
    yearMaxInput.min = payload.yearMin;
    yearMaxInput.max = payload.yearMax;
    yearMaxInput.value = payload.yearMax;

    fillSelect(formFilter, "All genres", payload.forms || uniqueValues("form"));
    fillSelect(sourceFilter, "All sources", payload.sources || uniqueValues("source"));
    fillSelect(signalFilter, "All signals", payload.signals || uniqueSignals());
    fillSelect(whoFilter, "All life focuses", payload.whoAbout || uniqueWhoAbout());

    [yearMinInput, yearMaxInput, formFilter, sourceFilter, signalFilter, whoFilter].forEach((control) => {
      control.addEventListener("input", applyFilters);
      control.addEventListener("change", applyFilters);
    });

    clusterFilters.addEventListener("click", (event) => {
      const button = event.target.closest("[data-cluster]");
      if (!button) return;
      const cluster = button.dataset.cluster;
      if (activeClusters.has(cluster)) {
        activeClusters.delete(cluster);
      } else {
        activeClusters.add(cluster);
      }
      button.setAttribute("aria-pressed", String(activeClusters.has(cluster)));
      applyFilters();
    });

    resetFiltersButton.addEventListener("click", resetFilters);
  }

  function fillSelect(select, allLabel, values) {
    select.innerHTML = [`<option value="">${escapeHtml(allLabel)}</option>`]
      .concat(values.map((value) => `<option value="${escapeHtml(value)}">${escapeHtml(value)}</option>`))
      .join("");
  }

  function uniqueValues(key) {
    return Array.from(new Set(records.map((record) => record[key]).filter(Boolean))).sort();
  }

  function uniqueSignals() {
    return Array.from(new Set(records.flatMap((record) => record.signals || []))).sort();
  }

  function uniqueWhoAbout() {
    return Array.from(new Set(records.flatMap((record) => record.whoAbout || []))).sort();
  }

  function resetFilters() {
    activeClusters = new Set(allClusterSet);
    clusterFilters.querySelectorAll("[data-cluster]").forEach((button) => {
      button.setAttribute("aria-pressed", "true");
    });
    yearMinInput.value = payload.yearMin;
    yearMaxInput.value = payload.yearMax;
    formFilter.value = "";
    sourceFilter.value = "";
    signalFilter.value = "";
    whoFilter.value = "";
    applyFilters();
  }

  function applyFilters() {
    let minYear = Number(yearMinInput.value);
    let maxYear = Number(yearMaxInput.value);
    if (minYear > maxYear) {
      if (document.activeElement === yearMinInput) {
        maxYear = minYear;
        yearMaxInput.value = maxYear;
      } else {
        minYear = maxYear;
        yearMinInput.value = minYear;
      }
    }

    const form = formFilter.value;
    const source = sourceFilter.value;
    const signal = signalFilter.value;
    const who = whoFilter.value;
    visibleRecords = records.filter((record) => {
      const year = Number(record.year || payload.yearMin);
      return (
        year >= minYear &&
        year <= maxYear &&
        activeClusters.has(record.cluster) &&
        (!form || record.form === form) &&
        (!source || record.source === source) &&
        (!signal || (record.signals || []).includes(signal)) &&
        (!who || (record.whoAbout || []).includes(who))
      );
    });

    replacePointGeometry(visibleRecords);
    clearPinnedCard();
    setHover(-1, { clientX: 0, clientY: 0 }, { force: true });
    yearRangeLabel.textContent = `${minYear}-${maxYear}`;
    visibleReadout.textContent = `${visibleRecords.length.toLocaleString()} shown`;
    container.dataset.recordCount = String(records.length);
    container.dataset.visibleCount = String(visibleRecords.length);
  }

  function replacePointGeometry(activeRecords) {
    const positions = new Float32Array(activeRecords.length * 3);
    const pointColors = new Float32Array(activeRecords.length * 3);
    const color = new THREE.Color();
    activeRecords.forEach((record, index) => {
      positions[index * 3] = record.x;
      positions[index * 3 + 1] = record.y;
      positions[index * 3 + 2] = record.z;
      color.set(record.color || "#65717d");
      pointColors[index * 3] = color.r;
      pointColors[index * 3 + 1] = color.g;
      pointColors[index * 3 + 2] = color.b;
    });
    const nextGeometry = new THREE.BufferGeometry();
    nextGeometry.setAttribute("position", new THREE.BufferAttribute(positions, 3));
    nextGeometry.setAttribute("color", new THREE.BufferAttribute(pointColors, 3));
    points.geometry.dispose();
    points.geometry = nextGeometry;
    pointGeometry = nextGeometry;
  }

  function resize() {
    const width = canvasHost.clientWidth;
    const height = Math.max(520, Math.min(760, Math.round(width * 0.62)));
    renderer.setSize(width, height, false);
    camera.aspect = width / height;
    camera.updateProjectionMatrix();
    updateZoomSensitiveSizes();
  }

  function updateZoomSensitiveSizes() {
    const height = Math.max(1, renderer.domElement.clientHeight || canvasHost.clientHeight);
    const distance = camera.position.length();
    const visibleWorldHeight = 2 * distance * Math.tan(THREE.MathUtils.degToRad(camera.fov / 2));
    const worldUnitsPerPixel = visibleWorldHeight / height;
    const cursorRadius = Math.max(0.14, Math.min(0.95, worldUnitsPerPixel * cursorRadiusPixels));
    raycaster.params.Points.threshold = cursorRadius;
    highlight.scale.setScalar(cursorRadius / highlightBaseRadius);
  }

  function panMap(dx, dy) {
    const height = Math.max(1, renderer.domElement.clientHeight || canvasHost.clientHeight);
    const distance = camera.position.length();
    const visibleWorldHeight = 2 * distance * Math.tan(THREE.MathUtils.degToRad(camera.fov / 2));
    const worldUnitsPerPixel = visibleWorldHeight / height;
    const right = new THREE.Vector3();
    const up = new THREE.Vector3();
    camera.matrixWorld.extractBasis(right, up, new THREE.Vector3());
    group.position.addScaledVector(right, dx * worldUnitsPerPixel);
    group.position.addScaledVector(up, -dy * worldUnitsPerPixel);
  }

  function updatePointer(event) {
    const rect = renderer.domElement.getBoundingClientRect();
    pointer.x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
    pointer.y = -((event.clientY - rect.top) / rect.height) * 2 + 1;
  }

  function setHover(index, event, options = {}) {
    if (pinnedIndex >= 0 && !options.force) return;
    clearTooltipHideTimer();
    hoveredIndex = index;
    if (index < 0) {
      highlight.visible = false;
      tooltip.hidden = true;
      tooltip.classList.remove("is-pinned");
      yearReadout.textContent = "Hover a point";
      return;
    }
    renderCard(index, event, false);
  }

  function scheduleHoverClear() {
    if (pinnedIndex >= 0) return;
    clearTooltipHideTimer();
    hideTooltipTimer = window.setTimeout(() => {
      if (!tooltipHasPointer && pinnedIndex < 0) {
        setHover(-1, { clientX: 0, clientY: 0 }, { force: true });
      }
    }, 180);
  }

  function clearTooltipHideTimer() {
    if (!hideTooltipTimer) return;
    window.clearTimeout(hideTooltipTimer);
    hideTooltipTimer = null;
  }

  function renderCard(index, event, pinned) {
    hoveredIndex = index;
    const record = visibleRecords[index];
    if (!record) return;
    highlight.position.set(record.x, record.y, record.z);
    highlight.visible = true;
    tooltip.hidden = false;
    tooltip.classList.toggle("is-pinned", pinned);
    const sourceLink = sourceAnchor(record);
    tooltip.innerHTML = `
      <strong>${escapeHtml(record.title)}</strong>
      <span>${record.year || "No year"} · ${escapeHtml(record.source)} · ${escapeHtml(record.form)}</span>
      ${creditLine("Dedicated to", record.dedicatedTo)}
      ${creditLine("Director", record.director)}
      ${creditLine("Author", record.author)}
      <small><b>Description:</b> ${escapeHtml(record.description || record.subjectDescription || "No short description available in the source metadata.")}</small>
      ${sourceLink}
    `;
    const rect = container.getBoundingClientRect();
    tooltip.style.transform = `translate(${event.clientX - rect.left + 14}px, ${event.clientY - rect.top + 14}px)`;
    yearReadout.textContent = record.year ? `${record.year}` : "No year";
  }

  function creditLine(label, value) {
    const text = String(value || "").trim();
    return text ? `<span>${escapeHtml(label)}: ${escapeHtml(text)}</span>` : "";
  }

  function togglePinnedCard(index, event) {
    if (index < 0) {
      clearPinnedCard();
      setHover(-1, event, { force: true });
      return;
    }
    if (pinnedIndex === index) {
      clearPinnedCard();
      setHover(-1, event, { force: true });
      return;
    }
    pinnedIndex = index;
    pinnedPosition = { clientX: event.clientX, clientY: event.clientY };
    renderCard(index, pinnedPosition, true);
  }

  function clearPinnedCard() {
    pinnedIndex = -1;
    pinnedPosition = null;
    tooltip.classList.remove("is-pinned");
  }

  function sourceAnchor(record) {
    const url = String(record.url || "").trim();
    if (!/^https?:\/\//i.test(url)) return "";
    const label = record.source ? `Open ${record.source} source` : "Open source";
    return `<a href="${escapeHtml(url)}" target="_blank" rel="noopener noreferrer" data-source-link>${escapeHtml(label)}</a>`;
  }

  function escapeHtml(value) {
    return String(value || "").replace(/[&<>"']/g, (char) => ({
      "&": "&amp;",
      "<": "&lt;",
      ">": "&gt;",
      '"': "&quot;",
      "'": "&#039;",
    }[char]));
  }

  renderer.domElement.addEventListener("pointermove", (event) => {
    if (isDragging) {
      const dx = event.clientX - previous.x;
      const dy = event.clientY - previous.y;
      if (pointerDown && Math.hypot(event.clientX - pointerDown.x, event.clientY - pointerDown.y) > 4) {
        pointerDown.dragged = true;
      }
      if (dragMode === "pan") {
        panMap(dx, dy);
      } else {
        group.rotation.z += dx * 0.006;
        group.rotation.x += dy * 0.004;
        rotationVelocity = { x: dy * 0.0003, y: dx * 0.0004 };
      }
      previous = { x: event.clientX, y: event.clientY };
      return;
    }
    updatePointer(event);
    raycaster.setFromCamera(pointer, camera);
    const intersections = raycaster.intersectObject(points);
    setHover(intersections.length ? intersections[0].index : -1, event);
  });

  renderer.domElement.addEventListener("pointerdown", (event) => {
    isDragging = true;
    dragMode = event.shiftKey || event.button === 1 || event.button === 2 ? "pan" : "rotate";
    pointerDown = { x: event.clientX, y: event.clientY, dragged: false, mode: dragMode };
    previous = { x: event.clientX, y: event.clientY };
    renderer.domElement.setPointerCapture(event.pointerId);
  });

  renderer.domElement.addEventListener("pointerup", (event) => {
    const wasClick = pointerDown && !pointerDown.dragged;
    const wasRotateClick = wasClick && pointerDown.mode === "rotate";
    isDragging = false;
    if (renderer.domElement.hasPointerCapture(event.pointerId)) {
      renderer.domElement.releasePointerCapture(event.pointerId);
    }
    if (wasRotateClick) {
      updatePointer(event);
      raycaster.setFromCamera(pointer, camera);
      const intersections = raycaster.intersectObject(points);
      togglePinnedCard(intersections.length ? intersections[0].index : -1, event);
    }
    pointerDown = null;
  });

  renderer.domElement.addEventListener("pointerleave", () => {
    isDragging = false;
    pointerDown = null;
    scheduleHoverClear();
  });

  renderer.domElement.addEventListener("contextmenu", (event) => {
    event.preventDefault();
  });

  tooltip.addEventListener("pointerenter", () => {
    tooltipHasPointer = true;
    clearTooltipHideTimer();
  });

  tooltip.addEventListener("pointerleave", () => {
    tooltipHasPointer = false;
    scheduleHoverClear();
  });

  tooltip.addEventListener("pointerdown", (event) => {
    if (event.target.closest("[data-source-link]")) {
      event.stopPropagation();
    }
  });

  tooltip.addEventListener("click", (event) => {
    if (event.target.closest("[data-source-link]")) {
      event.stopPropagation();
    }
  });

  renderer.domElement.addEventListener("wheel", (event) => {
    event.preventDefault();
    const delta = Math.sign(event.deltaY) * 4;
    camera.position.multiplyScalar(1 + delta * 0.01);
    camera.position.clampLength(42, 140);
    camera.lookAt(0, 0, 0);
    updateZoomSensitiveSizes();
  }, { passive: false });

  resetViewButton.addEventListener("click", () => {
    group.rotation.set(0, 0, 0);
    group.position.set(0, 0, 0);
    camera.position.copy(initialCamera);
    camera.lookAt(0, 0, 0);
    updateZoomSensitiveSizes();
    rotationVelocity = { x: 0.0015, y: 0.002 };
  });

  const hoverObserver = new MutationObserver(() => {
    const index = Number(container.dataset.hoverIndex ?? -1);
    const rect = container.getBoundingClientRect();
    clearPinnedCard();
    setHover(Number.isFinite(index) ? index : -1, {
      clientX: rect.left + rect.width * 0.55,
      clientY: rect.top + 180,
    }, { force: true });
  });
  hoverObserver.observe(container, { attributes: true, attributeFilter: ["data-hover-index"] });

  function animate() {
    requestAnimationFrame(animate);
    if (!isDragging && hoveredIndex < 0) {
      group.rotation.x += rotationVelocity.x;
      group.rotation.z += rotationVelocity.y;
      rotationVelocity.x *= 0.985;
      rotationVelocity.y *= 0.985;
    }
    renderer.render(scene, camera);
  }

  resize();
  window.addEventListener("resize", resize);
  container.dataset.mapReady = "true";
  window.semanticMap3DDebug = {
    records,
    scene,
    camera,
    renderer,
    group,
    points,
    highlight,
    applyFilters,
    resetFilters,
    setHover,
    hoverObserver,
    get visibleRecords() {
      return visibleRecords;
    },
  };
  animate();
})();
