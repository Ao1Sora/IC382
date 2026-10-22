# Team navigation map

This is the unchanged scene_map.pgm + scene_map.yaml exported from the running teacher
scene on 2026-10-21. It is the map previously supplied to the user, not the old SLAM my_map.

Grid: 1024 x 1096; resolution 0.25 original scene units; origin [-392, -80, 0].
The teacher scene is 10x scale. Equivalent physical resolution: 0.025 m.
Black pixels are projected obstacles within the selected robot-height slab; white pixels
mean no projected surface, not measured traversability. Robot geometry was excluded.

Original file SHA-256:
51c0383ed9356fc4ec5e2132ea86d79cb82164f1fa99e2dc24a9e87f147aa22b

The map is installed with ic382_navigation and selected by the default team launch.
Full multi-goal patrol and physical-robot acceptance remain unverified.
