# Keyframe batch drawer — V2 draft

Draw all requested keyframes in ONE response. You receive the ordered story, notes, beat table, exact requested frame indices, shared animation guide, and dimension-specific path protocol.

These are sparse samples from one continuous animation, not independent illustrations. Establish the cast and stable IDs in the first key, then preserve their identities, proportions, attachments, fixed scenery, and camera throughout the batch. Show the specified event state at each requested frame. New objects may appear only at their enabling event; disappeared objects need not retain visible strokes.

Consider all key poses together. Make their progression and contact states causally compatible, with clear silhouettes. Include the decisive information that the gap drawer will need: approach before contact, contact before release, water reaching flames before the flames disappear. A key is a sampled pose, not an automatic stop. The following gaps will supply the motion between these accepted endpoints.

Return only the requested sparse frame indices in ascending order, exactly once each. Do not generate intermediate frames or additional prose. Each returned frame contains full visible geometry:

```json
{"frames":[{"i":1,"strokes":[{"id":"actor_head","path":"M ...","description":"round head"}]}]}
```

The example illustrates the envelope only. Use valid paths from the supplied dimension protocol, and use the actual requested frame indices and scene content.
