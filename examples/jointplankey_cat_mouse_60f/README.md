# JointPlanKey cat-and-mouse example

This 60-frame 2D regression uses the v2.1.0 JointPlanKey flow:

1. One request jointly produces the storyboard and eight sparse keyframes.
2. Seven key intervals are generated concurrently from local beat text and FROM/TO keys.
3. The validated timeline is exported as a black-line GIF and standard SVG paths.

The prompt asks for a silent slapstick story in which a natural quadruped cat sets a trap, a natural quadruped mouse outsmarts it, and the trap backfires. The final storyboard visibly includes setup, anticipation, bait removal, pounce, impact and payoff.

Files:

- `clip.gif`: final 60-frame animation.
- `contact_sheet.jpg`: all rendered frames.
- `storyboard.md`: human-readable joint storyboard.
- `joint_plan_keys.json`: structured storyboard and sparse key geometry.

Raw provider reasoning, API responses and credentials are intentionally excluded from the repository.
