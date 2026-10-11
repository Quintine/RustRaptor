# lightning_shield artwork and sound provenance

The transparent equipment master was created with the built-in imagegen tool and the imagegen skill. No original game pixels or external reference artwork were used. `prepare_art.rs` fits the master onto transparent 16×16 SD and 64×64 HD canvases. Collision and targeting dimensions are independent of image resolution. Actual connecting lightning is drawn through the public `arc` command rather than projectile sprites.

Final prompt:

Use case: stylized-concept. Asset type: transparent inventory equipment sprite for a top-down 1994-inspired arcade aircraft shooter, supplied as a square master image for a 16x16 logical icon and 64x64 HD icon. Primary request: a Lightning Shield proximity zap weapon module. Single compact circular industrial coil unit viewed directly from above, a vivid cyan ring enclosing a dark central steel capacitor, four small copper electrode terminals evenly spaced, tiny white-blue lightning arcs contained inside the ring. Dark navy and brushed steel housing. Hand-painted retro game sprite with strong readable silhouette, simple broad material planes and restrained crisp highlights. Center the entire object with a little transparent padding. Genuinely transparent background and no ground shadow. No text, letters, numbers, frame, UI, watermark, spaceship, or surrounding scene. The circular emitter occupies most of the canvas and should still read at tiny size.

The master, SD/HD images and sound WAVs are included in the package. SHA-256 hashes are recorded in `art-provenance.json`. `generate_audio.py` reproduces deterministic PCM16 mono sounds at 22,050 Hz. Palette conversion occurs in the runtime loader.
