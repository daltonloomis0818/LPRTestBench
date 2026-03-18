"""
Compositor — Perspective-warps a rendered plate image onto a vehicle image
using the 4 mapped corner points. Uses OpenCV for the transform.
"""

import numpy as np
import cv2
from PIL import Image


class Compositor:
    def composite(self, vehicle_image: Image.Image, plate_image: Image.Image,
                  corners: list[list[float]]) -> Image.Image:
        """
        Warp plate_image onto vehicle_image at the given corner positions.

        Args:
            vehicle_image: Base vehicle photo (PIL RGBA).
            plate_image: Rendered plate image (PIL RGBA, 880x440).
            corners: List of 4 [x, y] pairs normalized 0.0-1.0,
                     order: top-left, top-right, bottom-right, bottom-left.

        Returns:
            Composited PIL Image with plate warped into position.
        """
        vw, vh = vehicle_image.size
        pw, ph = plate_image.size

        # Denormalize corners to actual pixel coordinates
        dst_pts = np.array(
            [[c[0] * vw, c[1] * vh] for c in corners],
            dtype=np.float32,
        )

        # Source corners of the plate image (full rectangle)
        src_pts = np.array(
            [[0, 0], [pw, 0], [pw, ph], [0, ph]],
            dtype=np.float32,
        )

        # Compute perspective transform
        matrix = cv2.getPerspectiveTransform(src_pts, dst_pts)

        # Convert plate to numpy BGRA for OpenCV
        plate_np = np.array(plate_image.convert('RGBA'))
        plate_bgra = cv2.cvtColor(plate_np, cv2.COLOR_RGBA2BGRA)

        # Warp the plate onto a blank canvas the size of the vehicle image
        warped = cv2.warpPerspective(
            plate_bgra, matrix, (vw, vh),
            flags=cv2.INTER_LINEAR,
            borderMode=cv2.BORDER_CONSTANT,
            borderValue=(0, 0, 0, 0),
        )

        # Convert warped back to PIL RGBA
        warped_rgba = cv2.cvtColor(warped, cv2.COLOR_BGRA2RGBA)
        warped_pil = Image.fromarray(warped_rgba, 'RGBA')

        # Extract the alpha channel as the paste mask
        mask = warped_pil.split()[3]

        # Composite: paste warped plate onto a copy of the vehicle image
        result = vehicle_image.convert('RGBA').copy()
        result.paste(warped_pil, (0, 0), mask)

        return result
