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
//	AdvMAME scale2x/scale3x filters by Andrea Mazzoleni, reimplemented
//	in-repo (GPLv2+, same license as the project). Each source pixel E
//	with its neighbors
//
//	    A B C
//	    D E F
//	    G H I
//
//	expands to a 2x2 (scale2x) or 3x3 (scale3x) block of output pixels.
//	Factor 4 is scale2x applied twice, the reference composition.
//

#include <stdlib.h>

#include "common.h"
#include "i_upscale.h"

// Exact per-byte average of two packed RGBA pixels: the common bits plus
// half the differing bits. The mask keeps the halving inside each byte
// lane, so no carry crosses channels and no unpacking is needed.

static uint32_t pixel_blend(uint32_t x, uint32_t y)
{
    return (x & y) + (((x ^ y) >> 1) & 0x7f7f7f7f);
}

static void scale2x_pass(const uint32_t *src, int spitch, int w, int h,
                         uint32_t *dst, int dpitch)
{
    int x, y;

    for (y = 0; y < h; ++y)
    {
        const uint32_t *row  = src + y * spitch;
        const uint32_t *above = y > 0     ? row - spitch : row;
        const uint32_t *below = y < h - 1 ? row + spitch : row;
        uint32_t *out0 = dst + (y * 2)     * dpitch;
        uint32_t *out1 = dst + (y * 2 + 1) * dpitch;

        for (x = 0; x < w; ++x)
        {
            // Out-of-bounds neighbors are treated as E (edges of the
            // above/below row aliases and of the x clamp do exactly that).

            uint32_t E = row[x];
            uint32_t B = above[x];
            uint32_t H = below[x];
            uint32_t D = x > 0     ? row[x - 1] : E;
            uint32_t F = x < w - 1 ? row[x + 1] : E;
            uint32_t a, b, c, d;

            a = (D == B && D != H && B != F) ? D : E;
            b = (B == F && B != D && F != H) ? B : E;
            c = (D == H && D != B && H != F) ? D : E;
            d = (H == F && H != D && F != B) ? F : E;

            out0[x * 2]     = a;
            out0[x * 2 + 1] = b;
            out1[x * 2]     = c;
            out1[x * 2 + 1] = d;
        }
    }
}

static void scale3x_pass(const uint32_t *src, int spitch, int w, int h,
                         uint32_t *dst, int dpitch)
{
    int x, y;

    for (y = 0; y < h; ++y)
    {
        const uint32_t *row  = src + y * spitch;
        const uint32_t *above = y > 0     ? row - spitch : row;
        const uint32_t *below = y < h - 1 ? row + spitch : row;
        uint32_t *out0 = dst + (y * 3)     * dpitch;
        uint32_t *out1 = dst + (y * 3 + 1) * dpitch;
        uint32_t *out2 = dst + (y * 3 + 2) * dpitch;

        for (x = 0; x < w; ++x)
        {
            uint32_t E = row[x];
            uint32_t B = above[x];
            uint32_t H = below[x];
            uint32_t D = x > 0     ? row[x - 1] : E;
            uint32_t F = x < w - 1 ? row[x + 1] : E;
            uint32_t a0, a1, a2, a3, a4, a5, a6, a7, a8;

            a4 = E;
            a1 = (B == D) ? D : E;
            a5 = (B == F) ? F : E;
            a7 = (H == F) ? F : E;
            a3 = (H == D) ? D : E;

            a0 = (B == D && B != F && D != H) ? D
               : ((D == B && D == H && F != H && B != F) ? pixel_blend(D, B) : E);
            a2 = (B == F && B != D && F != H) ? F
               : ((B == F && H == F && D != H && B != D) ? pixel_blend(B, F) : E);
            a6 = (D == H && D != B && H != F) ? D
               : ((D == H && H == F && B != F && D != B) ? pixel_blend(D, H) : E);
            a8 = (H == F && H != D && F != B) ? F
               : ((H == F && F == B && D != B && H != D) ? pixel_blend(H, F) : E);

            out0[x * 3]     = a0;
            out0[x * 3 + 1] = a1;
            out0[x * 3 + 2] = a2;
            out1[x * 3]     = a3;
            out1[x * 3 + 1] = a4;
            out1[x * 3 + 2] = a5;
            out2[x * 3]     = a6;
            out2[x * 3 + 1] = a7;
            out2[x * 3 + 2] = a8;
        }
    }
}

void I_UpscaleFrame(const uint32_t *src, int srcpitch_px, int w, int h,
                    uint32_t *dst, int dstpitch_px, int factor)
{
    if (factor == 2)
    {
        scale2x_pass(src, srcpitch_px, w, h, dst, dstpitch_px);
    }
    else if (factor == 3)
    {
        scale3x_pass(src, srcpitch_px, w, h, dst, dstpitch_px);
    }
    else if (factor == 4)
    {
        // scale2x applied twice (640x400x4 = 1 MB temporary).

        uint32_t *tmp = (uint32_t *) malloc(sizeof(uint32_t)
                                            * w * 2 * h * 2);

        if (tmp == NULL)
        {
            EXIT_Error("I_UpscaleFrame: memory");
        }

        scale2x_pass(src, srcpitch_px, w, h, tmp, w * 2);
        scale2x_pass(tmp, w * 2, w * 2, h * 2, dst, dstpitch_px);
        free(tmp);
    }
    else
    {
        EXIT_Error("I_UpscaleFrame: bad factor %d", factor);
    }
}
