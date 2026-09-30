"""Trace the flat logo artwork into polygon outlines for 3D extrusion.

Writes assets/logos.json: {name: [{"outer": [[x, y], ...], "holes": [[[x, y], ...]]}]}
with coordinates normalised so the logo's height is 1 and it is centred on the origin
(y points up, matching three.js).
"""

import json
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parent.parent / "assets"


def trace(path: Path, epsilon: float = 0.9) -> list[dict]:
    img = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
    img = cv2.resize(img, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
    img = cv2.GaussianBlur(img, (5, 5), 0)
    _, mask = cv2.threshold(img, 128, 255, cv2.THRESH_BINARY_INV)
    contours, hierarchy = cv2.findContours(mask, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_NONE)
    hierarchy = hierarchy[0]
    pts = np.concatenate([c.reshape(-1, 2) for c in contours]).astype(float)
    x0, y0 = pts.min(axis=0)
    x1, y1 = pts.max(axis=0)
    cx, cy, scale = (x0 + x1) / 2, (y0 + y1) / 2, y1 - y0

    def norm(c):
        c = cv2.approxPolyDP(c, epsilon, True).reshape(-1, 2).astype(float)
        return [[round((x - cx) / scale, 5), round(-(y - cy) / scale, 5)] for x, y in c]

    shapes = []
    for i, c in enumerate(contours):
        if hierarchy[i][3] != -1 or cv2.contourArea(c) < 400:
            continue
        holes = []
        child = hierarchy[i][2]
        while child != -1:
            if cv2.contourArea(contours[child]) > 400:
                holes.append(norm(contours[child]))
            child = hierarchy[child][0]
        shapes.append({"outer": norm(c), "holes": holes})
    return shapes


def main() -> None:
    out = {
        "br": trace(ROOT / "br-logo.png"),
        "pera": trace(ROOT / "pera-logo.jpg"),
    }
    (ROOT / "logos.json").write_text(json.dumps(out))
    for name, shapes in out.items():
        print(name, [(len(s["outer"]), len(s["holes"])) for s in shapes])


if __name__ == "__main__":
    main()
