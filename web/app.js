import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';

// Die Zuglogik liegt in Python (rubik/cube.py). Hier wird nur dargestellt und animiert;
// nach jeder Animation werden die Steine zurückgesetzt und neu aus dem Zustand gefärbt.

const HEX = { W: '#f2f2f2', Y: '#ffd500', R: '#c41e3a', O: '#ff6a00', B: '#0051ba', G: '#009e60' };
const DARK_TEXT = new Set(['W', 'Y', 'O']);
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
}

function setHover(i) {
  if (i === hover) return;
  const prev = hover;
  hover = i;
  for (const k of [prev, i]) if (k >= 0) { drawSticker(k); drawCell(k); }
}

function paint(i) {
  if (busy || i % 9 === 4 || state[i] === brush) return;
  pushHistory();
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

function pushHistory() {
  history.push(state);
  if (history.length > 500) history.shift();
}

function setBusy(b) {
  busy = b;
  document.querySelectorAll('.panel button').forEach((btn) => { btn.disabled = b; });
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
  pushHistory();
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
  state = history.pop();
  $('lastMoves').textContent = '';
  render();
}

$('reset').addEventListener('click', () => {
  if (busy || state === meta.solved) return;
  pushHistory();
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
  pushHistory();
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
  const face = e.key.toUpperCase();
  if ('URFDLB'.includes(face) && face.length === 1) runMoves(face + (e.shiftKey ? "'" : ''));
});

resize();
render();

// Link wie ?moves=R U R' führt die Züge nach dem Laden aus
const startMoves = new URLSearchParams(location.search).get('moves');
if (startMoves) {
  $('seqInput').value = startMoves;
  runMoves(startMoves);
}
