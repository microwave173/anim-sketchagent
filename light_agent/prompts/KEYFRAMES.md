# Keyframe batch drawer — V2 draft

Draw all requested keyframes in ONE response. You receive the ordered story, notes, beat table, exact requested frame indices, shared animation guide, and dimension-specific path protocol.

These are sparse samples from one continuous animation, not independent illustrations. Establish the cast and stable IDs in the first key, then preserve their identities, proportions, attachments, fixed scenery, and camera throughout the batch. Show the specified event state at each requested frame. New objects may appear only at their enabling event; disappeared objects need not retain visible strokes.

Consider all key poses together. Make their progression and contact states causally compatible, with clear silhouettes. When an actor travels on foot, choose key poses with visible alternating leg leads and distinct support/pass phases, not the same frozen limb shape merely shifted across the canvas. Keep enough room for the complete motion arc and final pose. Include the decisive information that the gap drawer will need: approach before contact, contact before release, water reaching flames before the flames disappear. A key is a sampled pose, not an automatic stop. The following gaps will supply the motion between these accepted endpoints.

Return only the requested sparse frame indices in ascending order, exactly once each. Do not generate intermediate frames or additional prose. Each returned frame contains full visible geometry:

```json
{"frames":[{"i":1,"strokes":[{"id":"actor_head","d":"M ... Z","description":"circular head"}]}]}
```

The example illustrates the 2D envelope only. For 2D use the `d` field with standard SVG path data; for 3D use the `path` field required by the supplied 3D protocol. Use the actual requested frame indices and scene content. Every stroke needs a stable semantic `id` and an accurate `description`; never output per-stroke style fields.
