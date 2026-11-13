# Digital Content Generation (DCG) & Game Feel — Standard

Guidelines, architectural rules, and verification patterns for generating, rigging, animating, and finishing 3D digital assets and game audio programmatically.

Derived from the transition of games and perceptual web applications from procedural mathematical CSG shapes to rigged skeletal 3D GLTF models, zero-bandwidth Web Audio synthesis, and dynamic combat juice.

The companion standards are `agent-graphics.md` (the twelve practices and three-layer separation) and `verification.md` (perceptual sensors and traps). The skills that operate this standard are `/render:dcg`, `/render:frames`, `/render:tune`, `/render:trap`, and `/render:render-init`.

---

## 1. The Core Architectural Philosophy

### A. Code-Driven Digital Content Generation (DCG)
Modern agentic software engineering should not rely on unversioned binary asset drops or manual 3D modeling tools (Blender, Maya) for core prototypes and indie games. Instead:
- **3D assets are generated via deterministic TypeScript/Node scripts** using Three.js and `GLTFExporter`.
- **Skeletons, skinning, and animations are authored as code**: bone armatures, parent-child hierarchies, and keyframe tracks are version-controlled in git.
- **Meshopt binary compression (`gltfpack -cc`)** runs automatically in the pipeline, reducing rigged humanoid characters with multiple animation clips down to **under 25 KB** each.

### B. The Game Feel Triad
Game "juice" and tactile weight are not visual afterthoughts; they are essential feedback loops that make gameplay readable and visceral:
1. **Hitstop Time Dilation:** A momentary freeze-frame (40ms for light hits, 80ms for heavy hits, 100ms for parries/breaks) applied to the game simulation on physical impact.
2. **Rotational Camera Trauma:** A Trauma^2 roll and pitch impulse model that decays quadratically, creating sharp screen shake on impacts without causing motion sickness.
3. **Procedural Web Audio:** Zero-bandwidth Web Audio API synthesizers that generate move-specific sound effects (slashes, sub-bass earthquakes, resonant temple bell clangs, impacts) without downloading megabytes of audio files.
4. **Post-Processing Finishing:** `EffectComposer` pipeline with `UnrealBloomPass` and `OutputPass` on GPU contexts, giving supernatural bloom to glowing weapons, eyes, and energy slashes.

---

## 2. The Eight DCG Practices

### 1. Standardized Humanoid Armature
Always structure humanoid bone hierarchies using standard semantic bone names:
```
Hips (Root)
 ├── Spine
 │    └── Chest
 │         ├── Neck
 │         │    └── Head
 │         ├── UpperArm_L ── Forearm_L ── Hand_L
 │         └── UpperArm_R ── Forearm_R ── Hand_R
 ├── UpperLeg_L ── LowerLeg_L ── Foot_L
 └── UpperLeg_R ── LowerLeg_R ── Foot_R
```
This enables predictable attachment points (e.g. blades on `Hand_R`, hats/masks on `Head`, scabbards on `Hips`) and makes animation clips reusable across rigs.

### 2. Keyframes as Quaternion & Vector Tracks
Never animate bones by hand-setting Euler angles in the per-frame render loop.
- Use `THREE.QuaternionKeyframeTrack` for rotational joint poses.
- Use `THREE.VectorKeyframeTrack` for root motion and translation offsets.
- Package related tracks into named `THREE.AnimationClip` objects (e.g., `Idle`, `Run`, `Slash`, `Thrust`, `Dodge`, `Stagger`).

### 3. Mandatory Meshopt Compression
Raw GLTF/GLB files exported from Three.js contain uncompressed float buffers. Always pipe raw GLB binaries through `gltfpack -cc`:
```bash
gltfpack -i raw.glb -o compressed.glb -cc
```
- `-cc`: Meshopt compression for vertices, indices, and keyframe tracks.
- Yields **85–95% file size reductions** with zero visible loss.
- Enables Three.js `GLTFLoader` with `MeshoptDecoder` to parse assets in under 5ms.

### 4. AnimationMixer State Machine with Cross-Fading
Decouple the simulation state from the 3D rendering:
- Use `THREE.AnimationMixer` to control playback.
- Non-looping attack/dodge clips must be set to `THREE.LoopOnce` with `clampWhenFinished = true`.
- Implement smooth cross-fading (`nextAction.crossFadeFrom(currentAction, duration, true)`) to eliminate abrupt popping between animations.

### 5. Always Provide a Procedural or Stub Fallback
WebGL assets load asynchronously. The game engine must:
- Mount an immediate procedural rig or bounding geometry on frame 0.
- Seamlessly transition to the loaded rigged GLB model once `loadAnimatedModel` resolves.
- Allow offline and test environments (JSDOM, headless CI) to run without failing when external file fetches are disabled.

### 6. Zero-Asset Procedural Audio Architecture
Do not bundle static WAV/MP3 files for sound effects. Use the Web Audio API:
- **Katana Swing:** Exponential frequency sweep with bandpass white noise filter.
- **Ground Slam / Earthquake:** 110Hz -> 22Hz sub-bass sine drop with distortion and rumble.
- **Parry Bell Clang:** High-frequency resonant sine harmonics (e.g. 1480Hz fundamental + 2960Hz harmonic) with exponential decay.
- **Hit Thump:** Low-pass noise burst with pitch drop.
- Ensure audio context resumption on first user gesture (`pointerdown`, `keydown`).

### 7. Perceptual Assertions in Headless CI
Test game feel through deterministic proxy assertions in unit tests:
```typescript
it('combat hit delivers complete audiovisual juice', () => {
  const game = createArenaGame(shippedPack, { audio: true });
  game.step(0.1);
  expect(soundEngine.getRecentEvents()).toContainEqual({ type: 'parry_clang' });
  expect(game.isHitstopActive()).toBe(true);
});
```

### 8. Strict Byte and Draw-Call Budgets
Every digital asset must be checked against strict budget limits in CI:
- Character `.glb` files: <= 100 KB (typically < 25 KB).
- Environment `.glb` files: <= 6 MB.
- First load payload: <= 15 MB gzipped.
Exceeding any budget immediately fails `npm run budgets`.
