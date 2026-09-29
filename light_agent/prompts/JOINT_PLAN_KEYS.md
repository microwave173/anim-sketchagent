# Joint storyboard and sparse-key drawer

Plan the animation storyboard and draw all of its sparse keyframes in this single response. The storyboard and keys are one joint decision: while constructing a key pose, revise the storyboard whenever you discover an unclear action, spatial conflict, awkward contact, or transition that cannot fit the available frames. Submit only the final mutually consistent result.

Preserve the user's required subjects, actions, causal arc and style. Every action required by the user must occur visibly inside the beat table; do not move a required setup, attempt, contact or payoff before frame 1, mention it only in `action`, or leave it as assumed backstory. Fit the amount of story to the actual playback duration. Add only visible actions that improve the requested story. Use one continuous shot for a short scene unless a cut is necessary or requested. Keep notes brief and limited to identity, qualitative layout, camera and unusual visual requirements. Storyboard fields must not contain coordinates, path commands, force calculations, pivot calculations or other drawing implementation details.

Choose a small number of meaningful beats. Their integer ranges must cover every supplied frame exactly once without gaps or overlap. If one beat ends at frame E, the next beat must start at frame E+1: for example `1-9`, `10-18`, `19-26`. Never repeat a boundary frame in two beat ranges. Frame 1 is a key showing the state immediately before the earliest required visible action, not a state after the setup has already happened. Every beat end is a later key showing that beat's exit state. The `frames` array must contain exactly frame 1 and all distinct beat-end indices in ascending order. Spend most frames on visible movement and change; avoid assigning a long interval to staring, waiting or an almost static hold when required actions remain.

Treat every adjacent pair of keys as boundary conditions for a later gap request. They must be connectable by a simple continuous action within the intervening frame count. Do not hide a teleport, side switch, unexplained reversal, major restaging, or unshown mechanical operation between sparse keys. If a proposed key pair is difficult to connect, simplify or revise the beat and key poses together before answering.

Use simple readable cartoon mechanics. Contacts must be visually clear, but do not calculate or explain forces, torques, exact intersections or collision proofs. Prefer the first simple staging that communicates the event. Do not output reasoning, alternatives, Markdown or prose outside the JSON.

Return exactly one JSON object:

```json
{
  "storyboard": {
    "action": "One concise paragraph describing the final story in temporal order.",
    "notes": ["Brief fixed identity, layout, camera or visual requirement."],
    "beats": [
      {
        "start": 1,
        "end": 8,
        "event": "The visible event during this range.",
        "exit": "The state and ongoing motion shown by the key at frame 8."
      }
    ]
  },
  "frames": [
    {
      "i": 1,
      "strokes": [
        {"id": "semantic_part", "d": "M ...", "description": "visible part"}
      ]
    }
  ]
}
```

The example shows the 2D stroke field. Follow the supplied dimension-specific path protocol: use `d` for 2D and `path` for 3D. Every key contains complete visible geometry, not deltas. Keep continuing semantic IDs, character proportions, fixed scenery and camera consistent across all keys. A key is a sampled motion state rather than an automatic pause.
