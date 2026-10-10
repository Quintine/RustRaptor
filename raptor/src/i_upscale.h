//
// Copyright(C) 1993-1996 Id Software, Inc.
// Copyright(C) 2005-2014 Simon Howard
//
// This program is free software; you can redistribute it and/or
// modify it under the terms of the GNU General Public License
// as published by the Free Software Foundation; either version 2
// of the License, or (at your option) any later version.
//
// This program is distributed in the hope that it will be useful,
// but WITHOUT ANY WARRANTY; without even the implied warranty of
// MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
// GNU General Public License for more details.
//
// DESCRIPTION:
//	Presentation-level pixel-art upscaler (AdvMAME scale2x/scale3x).
//

#pragma once

#include <stdint.h>

// Upscale a w x h 32-bit RGBA frame by factor (2, 3 or 4) into dst, which
// must be w*factor x h*factor pixels. Pitches are in pixels, not bytes;
// the caller converts surface pitches. No SDL dependency, no global state.

void I_UpscaleFrame(const uint32_t *src, int srcpitch_px, int w, int h,
                    uint32_t *dst, int dstpitch_px, int factor);
