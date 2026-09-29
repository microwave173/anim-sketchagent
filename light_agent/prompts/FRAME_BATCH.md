# Continuous animation frame batch

Produce every requested new animation frame in one response. Return only one JSON object using the supplied path protocol. Its `frames` array must contain exactly the requested frame indices in ascending order, with complete visible geometry in every frame. Do not return a plan, references, deltas, or explanatory prose.

Think through the action and timing internally before drawing. Treat the requested frames as coherent samples from one continuous full clip, whether the requested indices are consecutive or sparse. Let causes visibly precede their effects; include the needed contact and release moments. Use stable semantic part IDs across the requested frames, keep fixed scenery and camera unchanged, and maintain each object's shape and identity. Introduce, hide, or add a semantic part only when the story and visible pose require it. Move connected parts coherently rather than translating a frozen pose.

The user message states the request for this frame batch, its playback timing, and assigned frame indices. It may also supply planning guidance or accepted boundary/reference frames. When references are supplied, use them for identity, entry state, exit state, and motion direction; do not regenerate reference frames. Continue through a boundary key without treating it as an automatic pause. When no references are supplied, the assigned interval is the whole animation and must establish its own initial and final states.

Make this JSON response valid and complete. There is no continuation inside the assigned frame batch.
