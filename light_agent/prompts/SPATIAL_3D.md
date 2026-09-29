# Genuine spatial sketch construction — 3D only

Simple linework describes real spatial objects, not a flat illustration placed in XYZ coordinates. Use +x right, +y depth, +z up. A solid object's contours must occupy its actual depth as well as width and height. Depth elsewhere in the scene does not make a flat prop three-dimensional. Do not draw solid objects as planar billboards or merely give them different constant y offsets. Do not add arbitrary y jitter to fake volume.

Choose a few coherent wireframe contours that reveal the intended shape in perspective and remain meaningful when viewed from the front, side and top. For a solid sphere, use intersecting great-circle contours in different planes. For a box or slab, connect corresponding front and back edges to show its thickness. For an upright bucket, basket or cylinder, put its opening around a horizontal x-y plane, with z approximately constant along the rim; give the lower contour real depth and connect corresponding sides down the z axis. A vertical ellipse in an x-z plane is not an upright container opening.

Planar objects such as a wheel, sheet or sign may remain planar where appropriate; give them thickness only when needed. Stick limbs stay simple spatial centerlines, without unnecessary tubes. Keep the linework clean: depict volume through a few structural curves, not dense mesh detail. Preserve each continuing object's dimensions, spatial construction and attachments across keys and gaps. Motion may occur in one plane without flattening the solid objects themselves.

In planning, mention only essential spatial staging in the existing Notes section; do not add parts, a new schema or coordinates. In drawing, construct these spatial contours with the supplied path protocol. Never rely on the display camera alone to create apparent volume.

## Match the 2D motion presentation

Design for the supplied low-resolution native canvas and its perspective camera. When travel is important, a standing actor should usually occupy only about 20-35% of the projected frame height. Keep moving actors and props modest in the frame, with an open corridor through depth and screen space for the complete trajectory, large displacement and final pose. Contacts must remain readable at native resolution, so simplify minor wireframe detail instead of enlarging the whole scene. Do not auto-normalize each frame or let the subject grow to fill the canvas.

Use the same animation principles as 2D: articulate connected body parts, alternate leg leads and support phases during walking, counter-swing the arms, keep planted feet from sliding, and preserve attachments until release. A human head is a clean round spatial form with consistent proportions; use a sparse spherical construction that projects as round from the display camera, never a long oval, polygon or mechanical housing. Robots retain mechanical heads and chassis.

All rendered and projected strokes use one renderer-owned style: pure black, full opacity and one fixed width. Never output per-stroke color, opacity, fill or width.
