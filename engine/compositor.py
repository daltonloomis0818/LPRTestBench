"""
Compositor — Perspective-warps a rendered plate image onto a vehicle image
using the 4 mapped corner points. Uses OpenCV with supersampled anti-aliasing
and feathered edge blending for realistic results.
"""

import numpy as np
import cv2
from PIL import Image

SUPERSAMPLE = 2  # render warp at Nx resolution for anti-aliasing


class Compositor:
    def composite(self, vehicle_image: Image.Image, plate_image: Image.Image,
                  corners: list[list[float]]) -> Image.Image:
        """
        Warp plate_image onto vehicle_image at the given corner positions.

        Args:
            vehicle_image: Base vehicle photo (PIL RGBA).
            plate_image: Rendered plate image (PIL RGBA).
            corners: List of 4 [x, y] pairs normalized 0.0-1.0,
                     order: top-left, top-right, bottom-right, bottom-left.

        Returns:
            Composited PIL Image with plate warped into position.
        """
        vw, vh = vehicle_image.size
        pw, ph = plate_image.size
        S = SUPERSAMPLE

        # Work at supersampled resolution
        vw_up, vh_up = vw * S, vh * S

        # Denormalize corners to supersampled pixel coordinates
        dst_pts = np.array(
            [[c[0] * vw_up, c[1] * vh_up] for c in corners],
            dtype=np.float32,
        )

        # Upscale plate for high-quality warp input
        plate_np = np.array(plate_image.convert('RGBA'))
        plate_up = cv2.resize(plate_np, (pw * S, ph * S),
                              interpolation=cv2.INTER_LANCZOS4)
        ph_up, pw_up = plate_up.shape[:2]

        # Source corners of the upscaled plate
        src_pts = np.array(
            [[0, 0], [pw_up, 0], [pw_up, ph_up], [0, ph_up]],
            dtype=np.float32,
        )

        # Perspective transform
        matrix = cv2.getPerspectiveTransform(src_pts, dst_pts)

        # Convert to BGRA for OpenCV
        plate_bgra = cv2.cvtColor(plate_up, cv2.COLOR_RGBA2BGRA)

        # Warp at supersampled resolution with best interpolation
        warped = cv2.warpPerspective(
            plate_bgra, matrix, (vw_up, vh_up),
            flags=cv2.INTER_LANCZOS4,
            borderMode=cv2.BORDER_CONSTANT,
            borderValue=(0, 0, 0, 0),
        )

        # Create feathered mask for smooth edge blending
        # Start with a white rectangle slightly inset from plate edges
        inset = max(3, S * 2)
        mask_src = np.zeros((ph_up, pw_up), dtype=np.uint8)
        mask_src[inset:-inset, inset:-inset] = 255
        # Blur edges for feathering
        mask_src = cv2.GaussianBlur(mask_src, (0, 0), sigmaX=S * 2.0)

        # Warp the mask with the same transform
        warped_mask = cv2.warpPerspective(
            mask_src, matrix, (vw_up, vh_up),
            flags=cv2.INTER_LANCZOS4,
            borderMode=cv2.BORDER_CONSTANT,
            borderValue=0,
        )

        # Upscale vehicle image to match
        vehicle_np = np.array(vehicle_image.convert('RGBA'))
        vehicle_up = cv2.resize(vehicle_np, (vw_up, vh_up),
                                interpolation=cv2.INTER_LANCZOS4)
        vehicle_bgra = cv2.cvtColor(vehicle_up, cv2.COLOR_RGBA2BGRA)

        # Float blend using feathered mask
        mask_f = warped_mask.astype(np.float32) / 255.0
        mask_4ch = np.stack([mask_f] * 4, axis=-1)

        blended = (warped.astype(np.float32) * mask_4ch +
                   vehicle_bgra.astype(np.float32) * (1.0 - mask_4ch))
        blended = np.clip(blended, 0, 255).astype(np.uint8)

        # Downsample to original resolution with INTER_AREA (best for downscaling)
        result_bgra = cv2.resize(blended, (vw, vh), interpolation=cv2.INTER_AREA)

        # Convert back to PIL RGBA
        result_rgba = cv2.cvtColor(result_bgra, cv2.COLOR_BGRA2RGBA)
        return Image.fromarray(result_rgba, 'RGBA')
