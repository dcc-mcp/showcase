"""Offline plate analysis only; optical flow is not a Nuke tracker or 3D solve."""
from pathlib import Path
import hashlib
import json
import cv2
import numpy as np


def main():
    root = Path(__file__).resolve().parent
    path = root / "assets/plate-8s.mp4"
    cv2.setNumThreads(1)
    capture = cv2.VideoCapture(str(path))
    ok, first = capture.read()
    if not ok:
        raise SystemExit("No first video frame")
    base = cv2.cvtColor(first, cv2.COLOR_BGR2GRAY)
    mask = np.zeros_like(base)
    mask[310:690, 40:1240] = 255
    points = cv2.goodFeaturesToTrack(base, maxCorners=600, qualityLevel=0.02, minDistance=12, mask=mask)
    if points is None or len(points) < 30:
        raise SystemExit("Insufficient ground features")
    frames = [{"frame": 1, "dx_px": 0.0, "dy_px": 0.0, "scale": 1.0, "rotation_deg": 0.0, "median_error_px": 0.0, "tracks": len(points)}]
    hashes = {hashlib.sha256(first.tobytes()).hexdigest()}
    while True:
        ok, current = capture.read()
        if not ok:
            break
        hashes.add(hashlib.sha256(current.tobytes()).hexdigest())
        gray = cv2.cvtColor(current, cv2.COLOR_BGR2GRAY)
        tracked, valid, _ = cv2.calcOpticalFlowPyrLK(base, gray, points, None, winSize=(31, 31), maxLevel=4)
        keep = valid[:, 0] == 1
        p = points[keep, 0, :]
        q = tracked[keep, 0, :]
        affine, inliers = cv2.estimateAffinePartial2D(p, q, method=cv2.RANSAC, ransacReprojThreshold=1.5)
        if affine is None or inliers is None or int(inliers.sum()) < 30:
            raise SystemExit("Motion fit has insufficient inliers at frame %d" % (len(frames) + 1))
        keep = inliers[:, 0] == 1
        predicted = p @ affine[:, :2].T + affine[:, 2]
        error = np.linalg.norm(predicted[keep] - q[keep], axis=1)
        scale = float(np.hypot(affine[0, 0], affine[1, 0]))
        frames.append({"frame": len(frames) + 1, "dx_px": float(affine[0, 2]), "dy_px": float(affine[1, 2]),
                       "scale": scale, "rotation_deg": float(np.degrees(np.arctan2(affine[1, 0], affine[0, 0]))),
                       "median_error_px": float(np.median(error)), "tracks": int(keep.sum())})
    capture.release()
    result = {
        "scope": "Offline ground-feature partial-affine fit from each decoded frame to the first. Not Nuke Tracker4, lens calibration, camera solve, or final matchmove acceptance.",
        "plate_sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "opencv_version": cv2.__version__,
        "frames_decoded": len(frames), "unique_decoded_frames": len(hashes), "feature_roi_xyxy_px": [40, 310, 1240, 690],
        "max_translation_px": max(float(np.hypot(f["dx_px"], f["dy_px"])) for f in frames),
        "max_scale_delta": max(abs(f["scale"] - 1) for f in frames),
        "max_rotation_deg": max(abs(f["rotation_deg"]) for f in frames),
        "max_median_fit_error_px": max(f["median_error_px"] for f in frames),
        "minimum_inlier_tracks": min(f["tracks"] for f in frames), "frames": frames,
    }
    (root / "motion-analysis.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in result.items() if k != "frames"}, indent=2))


if __name__ == "__main__":
    main()
