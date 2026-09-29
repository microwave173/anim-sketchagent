# Single-response animation

Produce the entire requested animation in one response. Return only one JSON object using the supplied path protocol. Its `frames` array must contain every frame from 1 through N, in ascending order, with complete visible geometry in each frame. Do not return a plan, key frames, references, deltas, or explanatory prose.

Think through the action and timing internally before drawing. The first frame shows the state before the first event. Let causes visibly precede their effects; include the contact and release moments. Use stable semantic part IDs across all frames, keep fixed scenery and camera unchanged, and maintain each object's shape and identity. Introduce or hide objects only when the story requires it. Move connected parts coherently rather than translating a frozen pose. Use the complete frame budget for meaningful progression, including a clear final state.

The JSON response is the only generation call for this clip. Make it valid and complete; there is no later continuation or repair step.
