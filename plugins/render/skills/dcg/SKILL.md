---
name: dcg
description: Generate, rig, animate, or optimize digital content assets (3D GLTF models, bone armatures, animation clips, and procedural Web Audio synthesizers) for game engines with zero-bandwidth overhead. Does not trigger for visual-difference regression testing (use frames instead), does not trigger for tuning theme values (use tune instead), and does not trigger for initial scaffold setup (use render-init instead).
---

**Usage:** `/render:dcg {target}` — e.g. `/render:dcg models` to generate/regenerate 3D character armatures, `/render:dcg audio` to tune procedural SFX, or `/render:dcg {character-name}` to scaffold a new rigged 3D model.

Digital Content Generation (DCG) builds game-ready 3D models and audio assets entirely in code, applying Meshopt compression and Web Audio synthesis for maximal visual and tactile quality with minimal byte budgets.

See `${CLAUDE_PLUGIN_ROOT}/standards/digital-content-generation.md` and `${CLAUDE_PLUGIN_ROOT}/standards/agent-graphics.md` for architecture and rules.

---

## Step 1: Model Specification & Armature Architecture

When creating or modifying a 3D character or prop:
1. Define the bone hierarchy using standard humanoid conventions (`Hips`, `Spine`, `Chest`, `Neck`, `Head`, `UpperArm_L/R`, `Forearm_L/R`, `Hand_L/R`, `UpperLeg_L/R`, `LowerLeg_L/R`, `Foot_L/R`).
2. Attach meshes (e.g. clothing, hats, weapons, heads) to specific bones.
3. Define keyframe animation tracks using `THREE.QuaternionKeyframeTrack` (rotations) and `THREE.VectorKeyframeTrack` (positions).
4. Package keyframe tracks into named `THREE.AnimationClip` objects (`Idle`, `Run`, `Attack`, `Hurt`, etc.).

Reference script: `scripts/make-character-models.ts` or the project model generator.

---

## Step 2: Binary Generation & Meshopt Compression

Export raw Three.js scenes to binary GLTF (`.glb`) and compress with `gltfpack -cc`:

```bash
# Generate raw and compressed models
npm run models:generate
```

Verification check:
```bash
# Check that asset sizes remain well within the 6 MB per-file and 15 MB first-load budgets
npm run budgets
```

Target benchmarks:
- Characters: < 30 KB compressed.
- Props/Objects: < 100 KB compressed.

---

## Step 3: Runtime Integration with AnimationMixer

Load the generated model using `loadAnimatedModel` in `src/render/model.ts` (or the project model loader):
```typescript
import { loadAnimatedModel, type AnimatedModel } from '../render/model';

const model = await loadAnimatedModel('/assets/models/character.glb');
scene.add(model.root);

// Drive animations via state machine
model.play('Idle', 0.2); // Smooth cross-fade
model.play('Slash', 0.05); // Fast attack transition

// In update loop
model.mixer.update(dt);
```

Always maintain an immediate procedural/box fallback on frame 0 so the application renders with zero latency while the GLTF asset loads.

---

## Step 4: Procedural Web Audio Synthesis

For sound effects, avoid bundled audio files. Implement procedural synthesis in `src/arena/audio/sfx.ts` (or the project audio engine):
- Oscillators (`sine`, `sawtooth`, `triangle`) for tones and sweeps.
- Bandpass/lowpass filtered white noise for whooshes, slashes, and impacts.
- Biquad filters and custom gain envelopes (`exponentialRampToValueAtTime`) for decay.

---

## Step 5: Verification & Perceptual Testing

1. **Unit Tests:** Verify that `.glb` files parse with `GLTFLoader`, all required clips exist, and actions can play without errors (see `src/render/model.test.ts`).
2. **Audio Tests:** Verify audio events dispatch without throwing in mock environments.
3. **End-to-End Tests:** Run `npm run e2e` to ensure animations and interactions run smoothly across all target browsers.
