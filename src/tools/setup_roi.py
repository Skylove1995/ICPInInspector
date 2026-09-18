import cv2
import sys
import os
import numpy as np

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
from src.utils.config_manager import ConfigManager

def cv2_imread_unicode(file_path):
    """ Read image from path with unicode characters """
    try:
        raw_data = np.fromfile(file_path, dtype=np.uint8)
        return cv2.imdecode(raw_data, cv2.IMREAD_COLOR)
    except Exception:
        return None

def setup_roi(image_path, num_rois=4):
    img = cv2_imread_unicode(image_path)
    if img is None:
        print(f"Error: Could not read image at {image_path}")
        return

    # Resize for display if too large
    display_img = img.copy()
    scale = 1.0
    if display_img.shape[1] > 1200:
        scale = 1200.0 / display_img.shape[1]
        display_img = cv2.resize(display_img, None, fx=scale, fy=scale)

    print("--- ROI Setup ---")
    print(f"Select ROI box for each of the {num_rois} ICs on the map.")
    print("\nControls:\n  - Mouse Drag: Select region\n  - SPACE/ENTER: Confirm selection\n  - c: Cancel selection")

    final_rois = []
    
    for i in range(num_rois):
        print(f"\n>>> [IC #{i+1}/{num_rois}] Select ROI area on map...")
        while True:
            r = cv2.selectROI(f"Select ROI for IC #{i+1}/{num_rois}", display_img, fromCenter=False, showCrosshair=True)
            cv2.destroyWindow(f"Select ROI for IC #{i+1}/{num_rois}")
            
            if r[2] == 0 or r[3] == 0:
                print("Selection cancelled or invalid. Please select again.")
                cmd = input("Type 'q' to quit or ENTER to retry: ")
                if cmd.lower() == 'q': return
                continue
            break
            
        # Map coords back to original image
        abs_x, abs_y, abs_w, abs_h = [int(v / scale) for v in r]
        
        # Ensure within bounds
        abs_y = max(0, abs_y); abs_x = max(0, abs_x)
        abs_h = min(img.shape[0] - abs_y, abs_h)
        abs_w = min(img.shape[1] - abs_x, abs_w)
        
        final_rois.append([abs_x, abs_y, abs_w, abs_h])
        print(f"Recorded IC #{i+1}: {final_rois[-1]}")

    cv2.destroyAllWindows()

    if len(final_rois) == 0:
        print("No ROIs selected.")
        return

    config_mgr = ConfigManager()
    cfg = config_mgr.load_config()
    cfg["num_rois"] = num_rois
    cfg["rois"] = final_rois
    config_mgr.save_config(cfg)
    print(f"Selected {len(final_rois)} ROIs.")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Setup ROIs for IC Inspection")
    parser.add_argument("input_path", type=str, nargs="?", help="Path to image file or directory")
    args = parser.parse_args()

    sample_path = args.input_path
    
    if not sample_path:
        # Check if stdin is interactive
        if sys.stdin.isatty():
            sample_path = input("Enter path to sample full-map image: ").strip()
        else:
            print("Please provide input path as argument.")
            sys.exit(1)

    if sample_path and os.path.isdir(sample_path):
        # Pick first image in directory
        valid_exts = (".jpg", ".jpeg", ".png", ".bmp")
        try:
            files = [f for f in os.listdir(sample_path) if f.lower().endswith(valid_exts)]
        except Exception as e:
            print(f"Error reading directory: {e}")
            sys.exit(1)

        if not files:
            print("No images found in directory.")
            sys.exit(1)
        sample_path = os.path.join(sample_path, files[0])
        print(f"Directory provided. Using first image: {sample_path}")
        
    if not sample_path or not os.path.exists(sample_path):
        print(f"Please provide a valid image path. Got: {sample_path}")
    else:
        setup_roi(sample_path)
