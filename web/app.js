import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';

// Die Zuglogik liegt in Python (rubik/cube.py). Hier wird nur dargestellt und animiert;
// nach jeder Animation werden die Steine zurückgesetzt und neu aus dem Zustand gefärbt.

const HEX = { W: '#f2f2f2', Y: '#ffd500', R: '#c41e3a', O: '#ff6a00', B: '#0051ba', G: '#009e60' };
const DARK_TEXT = new Set(['W', 'Y', 'O']);
const arrowColor = getComputedStyle(document.documentElement).getPropertyValue('--arrow').trim();
const NET_POS = { U: [2, 1], L: [1, 2], F: [2, 2], R: [3, 2], B: [4, 2], D: [2, 3] };

const $ = (id) => document.getElementById(id);

async function api(path, body) {
  const res = await fetch(path, body === undefined ? undefined : {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data.detail || res.statusText);
  return data;
}

const meta = await api('/api/meta');
let state = meta.solved;
const history = [];
let busy = false;
let brush = 'W';
let hover = -1;
let showLabels = true;
let unsure = new Set(); // von der Erkennung als unsicher gemeldete Felder

// ---------- 3D-Szene ----------

const container = $('scene');
const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
renderer.setPixelRatio(window.devicePixelRatio);
container.appendChild(renderer.domElement);

const scene = new THREE.Scene();
const camera = new THREE.PerspectiveCamera(35, 1, 0.1, 100);
const HOME = new THREE.Vector3(5.2, 4.4, 7.2); // Blick auf U, F und R
camera.position.copy(HOME);

const controls = new OrbitControls(camera, renderer.domElement);
controls.enableDamping = true;
controls.enablePan = false;
controls.minDistance = 5;
controls.maxDistance = 20;

scene.add(new THREE.AmbientLight(0xffffff, 1.4));
const key = new THREE.DirectionalLight(0xffffff, 1.8);
key.position.set(4, 8, 6);
scene.add(key);
const fill = new THREE.DirectionalLight(0xffffff, 0.7);
fill.position.set(-5, -3, -6);
scene.add(fill);

const cubeGroup = new THREE.Group();
scene.add(cubeGroup);

const cubies = new Map();
const bodyGeo = new THREE.BoxGeometry(0.96, 0.96, 0.96);
const bodyMat = new THREE.MeshStandardMaterial({ color: 0x111111, roughness: 0.6 });
for (let x = -1; x <= 1; x++) for (let y = -1; y <= 1; y++) for (let z = -1; z <= 1; z++) {
  if (!x && !y && !z) continue;
  const mesh = new THREE.Mesh(bodyGeo, bodyMat);
  mesh.position.set(x, y, z);
  mesh.userData.home = [x, y, z];
  cubeGroup.add(mesh);
  cubies.set(`${x},${y},${z}`, mesh);
}

const stickerGeo = new THREE.PlaneGeometry(0.84, 0.84);
const stickers = meta.facelets.map((f, i) => {
  const ax = meta.axes[f.face];
  const canvas = document.createElement('canvas');
  canvas.width = canvas.height = 128;
  const tex = new THREE.CanvasTexture(canvas);
  tex.colorSpace = THREE.SRGBColorSpace;
  const mesh = new THREE.Mesh(stickerGeo, new THREE.MeshStandardMaterial({ map: tex, roughness: 0.35 }));
  const n = new THREE.Vector3(...f.normal);
  const right = new THREE.Vector3(...ax.right);
  const up = new THREE.Vector3(...ax.down).negate();
  mesh.position.copy(n).multiplyScalar(0.485);
  mesh.quaternion.setFromRotationMatrix(new THREE.Matrix4().makeBasis(right, up, n));
  mesh.userData.index = i;
  cubies.get(f.pos.join(',')).add(mesh);
  return { mesh, canvas, tex, name: f.name };
});

function drawSticker(i) {
  const s = stickers[i];
  const c = state[i];
  const g = s.canvas.getContext('2d');
  g.fillStyle = HEX[c] || '#555';
  g.fillRect(0, 0, 128, 128);
  if (showLabels) {
    g.fillStyle = DARK_TEXT.has(c) ? 'rgba(0,0,0,.72)' : 'rgba(255,255,255,.9)';
    g.textAlign = 'center';
    g.textBaseline = 'middle';
    g.font = '600 36px system-ui, sans-serif';
    g.fillText(s.name, 64, 50);
    g.font = '500 26px system-ui, sans-serif';
    g.fillText(c, 64, 90);
  }
  if (unsure.has(i)) {
    g.strokeStyle = arrowColor;
    g.lineWidth = 12;
    g.setLineDash([18, 10]);
    g.strokeRect(6, 6, 116, 116);
    g.setLineDash([]);
  }
  s.tex.needsUpdate = true;
  s.mesh.material.emissive.set(hover === i ? 0x3a6fd8 : 0x000000);
}

function resize() {
  const { clientWidth: w, clientHeight: h } = container;
  renderer.setSize(w, h);
  camera.aspect = w / h;
  camera.updateProjectionMatrix();
}
new ResizeObserver(resize).observe(container);

renderer.setAnimationLoop(() => {
  controls.update();
  renderer.render(scene, camera);
});

function animateMove(move, ms) {
  return new Promise((resolve) => {
    const axis = new THREE.Vector3(...meta.axes[move[0]].normal);
    const turns = move.endsWith('2') ? 2 : move.endsWith("'") ? -1 : 1;
    const target = -Math.PI / 2 * turns; // im Uhrzeigersinn, von außen auf die Seite gesehen
    const pivot = new THREE.Group();
    cubeGroup.add(pivot);
    const layer = [...cubies.values()].filter((c) => c.position.dot(axis) > 0.5);
    layer.forEach((c) => pivot.attach(c));
    const duration = ms * (turns === 2 ? 1.5 : 1);
    let t0 = null;
    function step(now) {
      t0 ??= now; // Zeitstempel von requestAnimationFrame, nicht performance.now()
      const t = Math.min(1, Math.max(0, (now - t0) / duration));
      const eased = t < 0.5 ? 2 * t * t : 1 - (-2 * t + 2) ** 2 / 2;
      pivot.setRotationFromAxisAngle(axis, target * eased);
      if (t < 1) return requestAnimationFrame(step);
      layer.forEach((c) => {
        cubeGroup.attach(c);
        c.position.set(...c.userData.home);
        c.rotation.set(0, 0, 0);
      });
      cubeGroup.remove(pivot);
      resolve();
    }
    requestAnimationFrame(step);
  });
}

// ---------- Pfeil für den nächsten Zug ----------
// Liegt auf der sichtbaren Vorderseite (bei B auf der Oberseite) und zeigt, wohin die
// Felder der Schicht wandern. F bekommt einen Bogen. Werte gelten im Uhrzeigersinn.

const ARROW_SPECS = {
  R: { n: [0, 0, 1], c: [1, 0, 1.5], d: [0, 1, 0] },
  L: { n: [0, 0, 1], c: [-1, 0, 1.5], d: [0, -1, 0] },
  U: { n: [0, 0, 1], c: [0, 1, 1.5], d: [-1, 0, 0] },
  D: { n: [0, 0, 1], c: [0, -1, 1.5], d: [1, 0, 0] },
  B: { n: [0, 1, 0], c: [0, 1.5, -1], d: [-1, 0, 0] },
  F: { n: [0, 0, 1], c: [0, 0, 1.5], d: [1, 0, 0] },
};

const arrowMat = new THREE.MeshBasicMaterial({
  color: arrowColor,
  side: THREE.DoubleSide,
  transparent: true,
  opacity: 0.92,
  depthTest: false,
});
const arrowGroup = new THREE.Group();
arrowGroup.renderOrder = 10;
scene.add(arrowGroup);

function straightArrowShape(len = 2.6, w = 0.09, hl = 0.5, hw = 0.3) {
  const a = -len / 2, b = len / 2;
  return new THREE.Shape([
    [a, -w], [b - hl, -w], [b - hl, -hw], [b, 0], [b - hl, hw], [b - hl, w], [a, w],
  ].map(([x, y]) => new THREE.Vector2(x, y)));
}

// Bogen um den Mittelpunkt; sweep < 0 = im Uhrzeigersinn
function arcArrowShape(sweep, r = 1.0, w = 0.09, hw = 0.3, from = Math.PI * 0.9) {
  const head = 0.5 / r * Math.sign(sweep);
  const end = from + sweep;
  const base = end - head;
  const at = (ang, rad) => new THREE.Vector2(Math.cos(ang) * rad, Math.sin(ang) * rad);
  const pts = [];
  const N = 40;
  for (let i = 0; i <= N; i++) pts.push(at(from + (base - from) * i / N, r + w));
  pts.push(at(base, r + hw), at(end, r), at(base, r - hw));
  for (let i = N; i >= 0; i--) pts.push(at(from + (base - from) * i / N, r - w));
  return new THREE.Shape(pts);
}

function textSprite(text) {
  const canvas = document.createElement('canvas');
  canvas.width = canvas.height = 128;
  const g = canvas.getContext('2d');
  g.fillStyle = arrowMat.color.getStyle();
  g.beginPath();
  g.arc(64, 64, 60, 0, Math.PI * 2);
  g.fill();
  g.fillStyle = '#fff';
  g.font = '700 58px system-ui, sans-serif';
  g.textAlign = 'center';
  g.textBaseline = 'middle';
  g.fillText(text, 64, 68);
  const tex = new THREE.CanvasTexture(canvas);
  tex.colorSpace = THREE.SRGBColorSpace;
  const sprite = new THREE.Sprite(new THREE.SpriteMaterial({ map: tex, depthTest: false }));
  sprite.scale.set(0.55, 0.55, 1);
  sprite.renderOrder = 11;
  return sprite;
}

function showArrow(move) {
  hideArrow();
  const spec = ARROW_SPECS[move[0]];
  const prime = move.endsWith("'");
  const n = new THREE.Vector3(...spec.n);
  let d = new THREE.Vector3(...spec.d);
  if (prime) d.negate();
  const side = new THREE.Vector3().crossVectors(n, d);
  const center = new THREE.Vector3(...spec.c).addScaledVector(n, 0.03);

  const shape = move[0] === 'F'
    ? arcArrowShape((prime ? 1 : -1) * Math.PI * 1.3)
    : straightArrowShape();
  const mesh = new THREE.Mesh(new THREE.ShapeGeometry(shape), arrowMat);
  if (move[0] === 'F') d = new THREE.Vector3(1, 0, 0); // Bogen ist bereits gerichtet
  mesh.quaternion.setFromRotationMatrix(
    new THREE.Matrix4().makeBasis(d, new THREE.Vector3().crossVectors(n, d), n));
  mesh.position.copy(center);
  mesh.renderOrder = 10;
  arrowGroup.add(mesh);

  if (move.endsWith('2')) {
    const label = textSprite('2×');
    label.position.copy(center).addScaledVector(n, 0.3);
    if (move[0] !== 'F') label.position.addScaledVector(side, 0.55);
    arrowGroup.add(label);
  }
}

function hideArrow() {
  for (const obj of [...arrowGroup.children]) {
    obj.geometry?.dispose();
    obj.material?.map?.dispose();
    if (obj.material !== arrowMat) obj.material?.dispose();
    arrowGroup.remove(obj);
  }
}

// 3D-Feld unter dem Mauszeiger auch im Netz markieren
const raycaster = new THREE.Raycaster();
const pointer = new THREE.Vector2();
renderer.domElement.addEventListener('pointermove', (e) => {
  const r = renderer.domElement.getBoundingClientRect();
  pointer.set(((e.clientX - r.left) / r.width) * 2 - 1, -((e.clientY - r.top) / r.height) * 2 + 1);
  raycaster.setFromCamera(pointer, camera);
  const hit = raycaster.intersectObjects(stickers.map((s) => s.mesh))[0];
  setHover(hit ? hit.object.userData.index : -1);
});
renderer.domElement.addEventListener('pointerleave', () => setHover(-1));

// ---------- Netz ----------

const cells = [];
const faceEls = {};
for (const face of meta.faces) {
  const el = document.createElement('div');
  el.className = 'face';
  const [col, row] = NET_POS[face];
  el.style.gridColumn = col;
  el.style.gridRow = row;
  faceEls[face] = el;
  $('net').appendChild(el);
}
meta.facelets.forEach((f, i) => {
  const cell = document.createElement('div');
  cell.className = 'cell' + (i % 9 === 4 ? ' center' : '');
  cell.innerHTML = `<span class="name">${f.name}</span><span class="letter"></span>`;
  cell.title = i % 9 === 4 ? `${f.name} – Mittelfeld, fest` : f.name;
  cell.addEventListener('click', () => paint(i));
  cell.addEventListener('mouseenter', () => setHover(i));
  cell.addEventListener('mouseleave', () => setHover(-1));
  faceEls[f.face].appendChild(cell);
  cells.push(cell);
});

for (const c of 'WYROBG') {
  const sw = document.createElement('div');
  sw.className = 'swatch' + (c === brush ? ' active' : '');
  sw.style.background = HEX[c];
  sw.style.color = DARK_TEXT.has(c) ? '#000' : '#fff';
  sw.textContent = c;
  sw.title = meta.colorNames[c];
  sw.addEventListener('click', () => {
    brush = c;
    document.querySelectorAll('.swatch').forEach((s) => s.classList.toggle('active', s === sw));
  });
  $('palette').appendChild(sw);
}

function drawCell(i) {
  const c = state[i];
  const cell = cells[i];
  cell.style.background = HEX[c] || '#555';
  cell.style.color = DARK_TEXT.has(c) ? '#000' : '#fff';
  cell.querySelector('.letter').textContent = c;
  cell.classList.toggle('hl', hover === i);
  cell.classList.toggle('unsure', unsure.has(i));
}

function setHover(i) {
  if (i === hover) return;
  const prev = hover;
  hover = i;
  for (const k of [prev, i]) if (k >= 0) { drawSticker(k); drawCell(k); }
}

function paint(i) {
  if (busy || i % 9 === 4 || state[i] === brush) return;
  const keep = new Set(unsure);
  beginEdit();
  keep.delete(i); // wer ein Feld von Hand setzt, hat es geprüft
  unsure = keep;
  state = state.slice(0, i) + brush + state.slice(i + 1);
  render();
}

// ---------- Ablauf ----------

function render() {
  for (let i = 0; i < 54; i++) { drawSticker(i); drawCell(i); }
  $('stateInput').value = state;
  if (busy) {
    $('status').className = 'status';
    $('status').textContent = '…';
  } else {
    updateStatus();
  }
}

async function updateStatus() {
  const el = $('status');
  try {
    const { problems } = await api('/api/check', { state });
    if (!problems.length) {
      el.className = 'status ok';
      el.textContent = state === meta.solved ? '✓ Gelöst' : '✓ Farbverteilung stimmt';
    } else {
      el.className = 'status bad';
      el.innerHTML = 'Prüfung:<ul>' + problems.map((p) => `<li>${p}</li>`).join('') + '</ul>';
    }
  } catch (e) {
    showError(e);
  }
}

function showError(e) {
  $('lastMoves').innerHTML = `<span style="color:var(--danger)">${e.message}</span>`;
}

// Jede Änderung von Hand macht eine berechnete Lösung ungültig
function beginEdit() {
  clearSolution();
  unsure = new Set();
  history.push(state);
  if (history.length > 500) history.shift();
}

function setBusy(b) {
  busy = b;
  // Abspielen bleibt bedienbar, damit man jederzeit anhalten kann
  document.querySelectorAll('.panel button:not(#play)').forEach((btn) => { btn.disabled = b; });
}

const speed = () => Number($('speed').value);

async function runMoves(text, ms = speed()) {
  if (busy) return;
  let result;
  try {
    result = await api('/api/apply', { state, moves: text });
  } catch (e) {
    return showError(e);
  }
  const { moves, states } = result;
  if (!moves.length) return;
  beginEdit();
  setBusy(true);
  $('lastMoves').textContent = moves.join(' ');
  for (let k = 0; k < moves.length; k++) {
    await animateMove(moves[k], ms);
    state = states[k];
    render();
  }
  setBusy(false);
  updateStatus();
}

for (const face of 'URFDLB') {
  for (const suffix of ['', "'", '2']) {
    const btn = document.createElement('button');
    btn.textContent = face + suffix;
    btn.addEventListener('click', () => runMoves(face + suffix));
    $('moveButtons').appendChild(btn);
  }
}
// Spaltenweise sortieren: oben die Drehungen im Uhrzeigersinn, darunter ' und 2
{
  const grid = $('moveButtons');
  const btns = [...grid.children];
  grid.replaceChildren(...[0, 1, 2].flatMap((s) => btns.filter((_, k) => k % 3 === s)));
}

$('seqForm').addEventListener('submit', (e) => {
  e.preventDefault();
  runMoves($('seqInput').value);
});

$('scramble').addEventListener('click', async () => {
  try {
    const { moves } = await api('/api/scramble?length=20');
    $('seqInput').value = moves.join(' ');
    runMoves(moves.join(' '), Math.max(60, speed() / 2));
  } catch (e) {
    showError(e);
  }
});

$('undo').addEventListener('click', undo);
function undo() {
  if (busy || !history.length) return;
  clearSolution();
  state = history.pop();
  $('lastMoves').textContent = '';
  render();
}

$('reset').addEventListener('click', () => {
  if (busy || state === meta.solved) return;
  beginEdit();
  state = meta.solved;
  $('lastMoves').textContent = '';
  render();
});

$('stateForm').addEventListener('submit', (e) => {
  e.preventDefault();
  const s = $('stateInput').value.replace(/\s+/g, '').toUpperCase();
  if (!/^[WYROBG]{54}$/.test(s)) {
    return showError(new Error('Zustand braucht genau 54 Buchstaben aus W Y R O B G'));
  }
  beginEdit();
  state = s;
  render();
});

$('labels3d').addEventListener('change', (e) => {
  showLabels = e.target.checked;
  render();
});

$('speedVal').textContent = `${speed()} ms`;
$('speed').addEventListener('input', () => { $('speedVal').textContent = `${speed()} ms`; });

$('resetView').addEventListener('click', () => {
  camera.position.copy(HOME);
  controls.target.set(0, 0, 0);
});

document.addEventListener('keydown', (e) => {
  if (e.target.closest('input, textarea') || e.altKey || e.metaKey) return;
  if (e.ctrlKey && e.key.toLowerCase() === 'z') { e.preventDefault(); return undo(); }
  if (e.ctrlKey) return;
  if (view === 'cam') {
    if (e.key === ' ') { e.preventDefault(); capture(); }
    return;
  }
  if (sol && (e.key === ' ' || e.key === 'ArrowRight')) { e.preventDefault(); return stepSolution(1); }
  if (sol && (e.key === 'ArrowLeft' || e.key === 'Backspace')) { e.preventDefault(); return stepSolution(-1); }
  const face = e.key.toUpperCase();
  if ('URFDLB'.includes(face) && face.length === 1) runMoves(face + (e.shiftKey ? "'" : ''));
});

// ---------- Lösung ----------

let sol = null; // { start, steps: [{move, text}], states, pos }
let playing = false;
let playToken = 0;

const stateAt = (k) => (k === 0 ? sol.start : sol.states[k - 1]);
const inverse = (m) => m[0] + { '': "'", "'": '', 2: '2' }[m.slice(1)];
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

function clearSolution() {
  playing = false;
  sol = null;
  $('solveMsg').textContent = '';
  renderSolution();
}

function renderSolution() {
  const box = $('stepBox');
  $('solution').hidden = !sol;
  box.hidden = !sol;
  if (!sol) return hideArrow();
  const n = sol.steps.length;
  $('chips').replaceChildren(...sol.steps.map((s, k) => {
    const chip = document.createElement('span');
    chip.className = 'chip' + (k < sol.pos ? ' done' : k === sol.pos ? ' current' : '');
    chip.textContent = s.move;
    chip.title = s.text;
    chip.addEventListener('click', () => jump(k));
    return chip;
  }));
  $('prev').disabled = busy || sol.pos === 0;
  $('next').disabled = busy || sol.pos === n;
  $('play').textContent = playing ? '❚❚ Pause' : '▶ Abspielen';
  $('play').disabled = !playing && sol.pos === n;
  box.classList.toggle('done', sol.pos === n);
  if (sol.pos < n) {
    const step = sol.steps[sol.pos];
    $('stepCount').textContent = sol.pos === 0
      ? `Zug 1 von ${n} · Würfel halten: Weiß oben, Grün vorn`
      : `Zug ${sol.pos + 1} von ${n}`;
    $('stepMove').textContent = step.move;
    $('stepText').textContent = step.text;
    if (busy) hideArrow(); else showArrow(step.move);
  } else {
    $('stepCount').textContent = `${n} Züge`;
    $('stepMove').textContent = '✓ Gelöst';
    $('stepText').textContent = '';
    hideArrow();
  }
}

async function stepSolution(dir) {
  if (!sol || busy) return;
  if (dir > 0 ? sol.pos >= sol.steps.length : sol.pos <= 0) return;
  const move = dir > 0 ? sol.steps[sol.pos].move : inverse(sol.steps[sol.pos - 1].move);
  setBusy(true);
  renderSolution();
  await animateMove(move, speed());
  sol.pos += dir;
  state = stateAt(sol.pos);
  setBusy(false);
  render();
  renderSolution();
}

function jump(k) {
  if (busy || playing || !sol) return;
  sol.pos = k;
  state = stateAt(k);
  render();
  renderSolution();
}

async function togglePlay() {
  if (!sol) return;
  if (playing) {
    playing = false;
    return renderSolution();
  }
  const token = ++playToken;
  playing = true;
  renderSolution();
  while (playing && token === playToken && sol && sol.pos < sol.steps.length) {
    await sleep(speed() * 1.5); // Pfeil vor jedem Zug kurz stehen lassen
    if (!playing || token !== playToken) return;
    await stepSolution(1);
  }
  if (token === playToken) {
    playing = false;
    renderSolution();
  }
}

$('prev').addEventListener('click', () => stepSolution(-1));
$('next').addEventListener('click', () => stepSolution(1));
$('play').addEventListener('click', togglePlay);

$('solve').addEventListener('click', async () => {
  if (busy) return;
  const shorter = $('shorter').checked;
  clearSolution();
  setBusy(true);
  $('solveMsg').textContent = shorter ? 'Suche kürzere Lösung (5 s) …' : 'Rechne …';
  try {
    const res = await api('/api/solve', { state, seconds: shorter ? 5 : 0 });
    if (res.steps.length) {
      sol = { start: state, steps: res.steps, states: res.states, pos: 0 };
      $('solveMsg').textContent = `${res.steps.length} Züge`;
    } else {
      $('solveMsg').textContent = 'Der Würfel ist schon gelöst.';
    }
  } catch (e) {
    $('solveMsg').innerHTML = `<span style="color:var(--danger)">${e.message}</span>`;
  }
  setBusy(false);
  renderSolution();
});

// ---------- Kamera und Aufnahme ----------

// Reihenfolge und Haltung: „oben“ ist die Seite, die im Bild oben liegen muss, damit
// die 9 Felder in Kociemba-Lesereihenfolge ankommen.
const CAPTURE_STEPS = [
  { face: 'F', top: 'U', hint: 'Grün zur Kamera, Weiß oben' },
  { face: 'R', top: 'U', hint: 'Würfel eine Vierteldrehung nach links: Rot zur Kamera, Weiß bleibt oben' },
  { face: 'B', top: 'U', hint: 'Noch eine Vierteldrehung nach links: Blau zur Kamera, Weiß oben' },
  { face: 'L', top: 'U', hint: 'Noch eine Vierteldrehung nach links: Orange zur Kamera, Weiß oben' },
  { face: 'U', top: 'B', hint: 'Wieder Grün vorn, dann nach vorn kippen (Oberseite zu dir): Weiß zur Kamera, Blau oben' },
  { face: 'D', top: 'F', hint: 'Wieder Grün vorn, dann nach hinten kippen: Gelb zur Kamera, Grün oben' },
];

let view = '3d';
let camInfo = null;
let camStep = 0;
let captures = {}; // Seite -> { cells: 9×RGB, image, rot }
let session = newSession();
let peekTimer = null;
let capturing = false;

function newSession() {
  return new Date().toISOString().replace(/[:.]/g, '-').slice(0, 19);
}

const faceColor = (face) => meta.faceColors[face];
const colorChip = (c) =>
  `<span class="chip-color" style="background:${HEX[c]};color:${DARK_TEXT.has(c) ? '#000' : '#fff'}">${meta.colorNames[c]}</span>`;
const rgbCss = ([r, g, b]) => `rgb(${r},${g},${b})`;

// Felder um 90° im Uhrzeigersinn drehen (zeilenweise 3×3)
const rotateCells = (cells) => [0, 1, 2, 3, 4, 5, 6, 7, 8].map((i) => cells[(2 - (i % 3)) * 3 + Math.floor(i / 3)]);

for (let i = 0; i < 9; i++) {
  const d = document.createElement('div');
  d.className = 'cell-guide' + (i === 4 ? ' center' : '');
  $('camBox').appendChild(d);
}
for (let i = 0; i < 9; i++) $('liveCells').appendChild(document.createElement('span'));

document.querySelectorAll('.tab').forEach((tab) => {
  tab.addEventListener('click', () => setView(tab.dataset.view));
});

function setView(v) {
  if (v === view) return;
  view = v;
  document.querySelectorAll('.tab').forEach((t) => t.classList.toggle('active', t.dataset.view === v));
  $('view3d').hidden = v !== '3d';
  $('viewCam').hidden = v !== 'cam';
  $('captureCard').hidden = v !== 'cam';
  if (v === 'cam') {
    startCamera();
  } else {
    stopCamera();
    resize();
  }
}

async function startCamera() {
  renderCapture();
  camMessage('');
  try {
    camInfo = await api('/api/camera/info');
  } catch (e) {
    return camMessage(`Kamera nicht verfügbar: ${e.message}`);
  }
  const [x, y, s] = camInfo.box;
  Object.assign($('camBox').style, {
    left: `${(x / camInfo.width) * 100}%`,
    top: `${(y / camInfo.height) * 100}%`,
    width: `${(s / camInfo.width) * 100}%`,
    height: `${(s / camInfo.height) * 100}%`,
  });
  layoutCam();
  $('camImg').src = `/api/camera/stream?t=${Date.now()}`;
  clearInterval(peekTimer);
  peekTimer = setInterval(peek, 400);
}

function stopCamera() {
  clearInterval(peekTimer);
  peekTimer = null;
  $('camImg').removeAttribute('src'); // beendet den Strom; der Server gibt die Kamera nach 20 s frei
}

// Bild samt Schablone so groß wie möglich ins Feld einpassen, ohne Verzerrung
function layoutCam() {
  if (!camInfo) return;
  const stage = $('camStage');
  const k = Math.min(stage.clientWidth / camInfo.width, stage.clientHeight / camInfo.height);
  $('camFrame').style.width = `${camInfo.width * k}px`;
  $('camFrame').style.height = `${camInfo.height * k}px`;
}
new ResizeObserver(layoutCam).observe($('camStage'));

function camMessage(text) {
  $('camMsg').hidden = !text;
  $('camMsg').textContent = text;
}

async function peek() {
  if (capturing || view !== 'cam' || camStep < 0) return;
  try {
    const step = CAPTURE_STEPS[camStep];
    const { cells, center } = await api(`/api/camera/peek?face=${step.face}`);
    [...$('liveCells').children].forEach((el, i) => { el.style.background = rgbCss(cells[i]); });
    const expected = faceColor(step.face);
    const ok = center === expected;
    $('liveCheck').className = 'live-check ' + (ok ? 'ok' : 'bad');
    $('liveCheck').innerHTML = ok
      ? `Mitte erkannt: ${colorChip(center)} ✓`
      : `Mitte erkannt: ${center === '?' ? '?' : colorChip(center)} ✗ – gesucht ist die Seite mit ${colorChip(expected)} in der Mitte`;
  } catch {
    // Vorschau-Messung ist nur ein Hinweis; Fehler zeigt der Strom bzw. die Aufnahme
  }
}

async function capture() {
  if (capturing || !camInfo || camStep < 0) return;
  const step = CAPTURE_STEPS[camStep];
  capturing = true;
  $('captureBtn').disabled = true;
  $('captureBtn').textContent = 'Halten …';
  try {
    const res = await api('/api/camera/capture', { face: step.face, session });
    const wrongCenter = res.center !== faceColor(step.face) ? res.center : null;
    captures[step.face] = { cells: res.cells, image: res.image, rot: 0, wrongCenter };
    camMessage(wrongCenter
      ? `Die Mitte sieht nach ${meta.colorNames[wrongCenter] ?? '?'} aus, gesucht war ${meta.colorNames[faceColor(step.face)]}. Bitte die richtige Seite zeigen und neu aufnehmen.`
      : '');
    // weiter zur nächsten noch fehlenden Seite – nicht, wenn die Mitte nicht passt
    const next = wrongCenter ? camStep : [1, 2, 3, 4, 5, 6].map((d) => (camStep + d) % 6).find((k) => !captures[CAPTURE_STEPS[k].face]);
    camStep = next ?? -1; // -1: alle Seiten sind da, keine ausgewählt
  } catch (e) {
    camMessage(`Aufnahme fehlgeschlagen: ${e.message}`);
  }
  capturing = false;
  $('captureBtn').textContent = 'Aufnehmen';
  renderCapture();
}

function renderCapture() {
  const allDone = camStep < 0;
  $('captureBtn').disabled = allDone;
  $('camTop').hidden = allDone;
  $('recognize').classList.toggle('pulse', allDone);
  if (allDone) {
    $('camTitle').textContent = 'Alle 6 Seiten aufgenommen – jetzt rechts „Farben erkennen“ klicken';
    $('camHint').textContent = 'Zum Wiederholen einer Seite ihre Kachel anklicken.';
    $('liveCheck').textContent = '';
    $('camBox').style.setProperty('--expect', 'transparent');
  } else {
    const step = CAPTURE_STEPS[camStep];
    const center = faceColor(step.face);
    $('camTitle').innerHTML = `${camStep + 1}/6 · Seite mit ${colorChip(center)} in der Mitte zeigen, ${colorChip(faceColor(step.top))} zeigt nach oben`;
    $('camHint').textContent = step.hint;
    $('camTop').innerHTML = `▲ ${colorChip(faceColor(step.top))}`;
    $('camBox').style.setProperty('--expect', HEX[center]);
  }

  $('faceTiles').replaceChildren(...CAPTURE_STEPS.map((s, k) => {
    const cap = captures[s.face];
    const tile = document.createElement('div');
    tile.className = 'tile' + (k === camStep ? ' current' : '') + (cap?.wrongCenter ? ' wrong' : '');
    const c = faceColor(s.face);
    tile.innerHTML = `
      <div class="tile-head"><span>${k + 1} · ${colorChip(c)}</span><span>${cap ? (cap.wrongCenter ? '✗ falsche Seite?' : '✓') : ''}</span></div>
      <div class="tile-body">${cap
        ? `<div class="mini">${cap.cells.map((v) => `<span style="background:${rgbCss(v)}"></span>`).join('')}</div>
           <img src="${cap.image}" style="transform:rotate(${cap.rot}deg)" alt="">
           <button class="ghost rot" title="Um 90° drehen, falls falsch herum aufgenommen">⟳</button>`
        : '<span class="empty">noch nicht aufgenommen</span>'}</div>`;
    tile.addEventListener('click', () => { camStep = k; renderCapture(); });
    tile.querySelector('.rot')?.addEventListener('click', (e) => {
      e.stopPropagation();
      cap.cells = rotateCells(cap.cells);
      cap.rot = (cap.rot + 90) % 360;
      renderCapture();
    });
    return tile;
  }));
  const done = CAPTURE_STEPS.every((s) => captures[s.face]);
  const wrong = CAPTURE_STEPS.filter((s) => captures[s.face]?.wrongCenter).map((s) => meta.colorNames[faceColor(s.face)]);
  $('recognize').disabled = !done;
  $('recMsg').innerHTML = wrong.length
    ? `<span style="color:var(--danger)">Mitte passt nicht bei: ${wrong.join(', ')} – Kachel anklicken und neu aufnehmen.</span>`
    : done ? '' : `${Object.keys(captures).length} von 6 Seiten aufgenommen`;
}

$('captureBtn').addEventListener('click', capture);

$('discard').addEventListener('click', () => {
  captures = {};
  camStep = 0;
  session = newSession();
  renderCapture();
});

$('recognize').addEventListener('click', async () => {
  const faces = Object.fromEntries(CAPTURE_STEPS.map((s) => [s.face, captures[s.face].cells]));
  try {
    const res = await api('/api/recognize', { faces, session });
    beginEdit();
    state = res.state;
    unsure = new Set(res.unsure);
    setView('3d');
    render();
    $('lastMoves').textContent = '';
    $('solveMsg').textContent = unsure.size
      ? `Erkannt. ${unsure.size} unsichere Felder sind markiert (gestrichelt, „?“) – bitte mit dem Würfel vergleichen und im Netz korrigieren.`
      : 'Erkannt. Bitte kurz mit dem Würfel vergleichen, dann „Lösung berechnen“.';
  } catch (e) {
    $('recMsg').innerHTML = `<span style="color:var(--danger)">${e.message}</span>`;
  }
});

resize();
render();

// Testlinks: ?moves=R U R' führt Züge aus, &solve rechnet danach die Lösung,
// &step=3 springt zum Zug, &speed=100 setzt das Tempo
const params = new URLSearchParams(location.search);
if (params.get('view') === 'cam') setView('cam');
if (params.has('speed')) {
  $('speed').value = params.get('speed');
  $('speedVal').textContent = `${speed()} ms`;
}
if (params.get('moves')) {
  $('seqInput').value = params.get('moves');
  await runMoves(params.get('moves'));
}
if (params.has('solve')) {
  $('solve').click();
  if (params.has('step')) {
    for (let i = 0; !sol && i < 200; i++) await sleep(50);
    jump(Number(params.get('step')));
  }
}
