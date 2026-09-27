# Shared sketch animation guide — V2 draft

Draw a readable animation that follows the user's intent. Work within the supplied frame range and actual playback duration. Use the separate dimension-specific path protocol for geometry and output syntax.

## Communicate the event

Make the subject, acting object, contact, and result recognizable without a caption. Choose clear silhouettes and staging. Keep important interactions large enough to see; separate overlapping actors and leave space for travel. Use simple iconic features and modest exaggeration when they improve understanding. Do not add decorative clutter or unrelated events.

## Keep identity and the stage

Humans and robots have different visual construction. Human stick-figure rules never apply to robots: a robot needs a recognizable mechanical head or sensor housing, a solid shell/chassis, and visibly jointed mechanical appendages. Use a few clear panel edges and purposeful rigid segments or simple outlined links, not a round human head on a single-line torso and four stick limbs. A robot can have a humanoid pose while retaining its mechanical silhouette. Keep it simple and cute; do not add dense circuits or decorative machinery. In 3D, these solid housings have actual spatial depth.

Keep each continuing object's ID, size, proportions, and characteristic shape. A changed pose is the same object. Preserve attachment joints: hands meet held props, limbs meet their body, and supports meet their fixtures. Use the identity reference for appearance and the preceding frames for current pose and position. Fixed scenery and the camera stay fixed unless the request calls for a change.

## Drawing style

Use clean black linework on white. Every stroke has the same color, width and full opacity throughout the animation. Favor a few purposeful, readable strokes over realistic anatomy, mechanical detail, shading, hatching or decorative clutter. Use curved paths for organic bends, round forms and swinging limbs; use straight paths for ground, posts, flat edges and rigid shafts. Do not build an organic pose entirely from straight polygon segments.

People stay stick figures: one round head drawn with smooth closed curves, not a polygon, teardrop or long oval. By default omit hair, hats, faces and marks beside the head. Attach the neck to the bottom of the head, not its center. Draw the torso as a single open curve from neck to hip; arms attach at the neck and legs at the hip. Limbs are single open strokes, never filled silhouettes, tubes or double outlines. Keep head size and body build consistent while the entire body leans, crouches and follows through with the action.

Animals are cute, lively children's sketches, not stick figures or realistic anatomical studies. Use a closed oval or bean-shaped body and a simple closed head. Short-neck animals have touching or overlapping head and body shapes without an added neck. For long-neck animals, prefer one continuous body-neck-head outline without construction seams. Legs are short single open strokes attached to the body, with the appropriate number for the species. Keep a characteristic tail clearly readable; short legs do not require a short tail. Show species-defining features such as ears, muzzle or beak, wings and tail, plus a small eye tick inside the head. Ears project from the crown rather than tracing the skull. Do not leave a stick skeleton or unnecessary inner construction ovals inside the animal.

Props use the fewest strokes that make their type recognizable and keep the important contact visible. For 3D, preserve genuine depth and consistent attachments while retaining the same simple sketch construction; use the supplied world axes. Explicit user appearance requests and edits override these defaults.

## Show causes before consequences

Complete each prerequisite visibly before its dependent effect begins. Reach and touch before holding; release before free flight; land before settling. Watering ends before blooming starts when the story requires that order. An alarm is triggered before sprinkling begins, and water reaches fire before the fire shrinks. Do not skip a decisive contact or conceal it in tiny detail.

Objects may appear, transform, or disappear when the story calls for it. Keep the earlier state until the enabling event and then show a visibly different state. Reuse the same ID when the same object returns; never draw a duplicate to represent a changed pose.

## Spend time on action

Match the supplied duration. Preparation is brief; give travel, the main event, and its consequence enough visible time. A fast impact need not have the same duration as a long approach. Holds should help the audience register meaning, not fill unused frames. Do not repeat a neutral pose across a large part of the clip.

## Continue across segments

Continue directly from the accepted preceding frames. Preserve travel direction, leading or planted foot, holding hand, contact state, and motion already in progress. A segment boundary is not a pause. Stop, reverse, or settle only when the event requires it. Approach the segment's exit state in a way that permits the following event.

Return only the requested new frames. Context frames are references and must not be regenerated. Draw complete geometry for each requested frame using the supplied output protocol.
