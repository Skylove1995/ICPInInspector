import cv2
import numpy as np
from scipy.signal import find_peaks

class ICInspector:
    def __init__(self, config=None, deviation_threshold=5.0, pitch_threshold=6.0):
        self.deviation_threshold = deviation_threshold
        self.pitch_threshold = pitch_threshold
        self.config = config or {}
        self.prep_config = self.config.get("preprocessing", {
            "blur_kernel": 5,
            "threshold_block_size": 21,
            "threshold_c": 10,
            "morph_kernel": 3,
            "debug_mode": False
        })

    def preprocess(self, gray_img):
        k_blur = self.prep_config.get("blur_kernel", 5)
        if k_blur % 2 == 0: k_blur += 1
        blurred = cv2.GaussianBlur(gray_img, (k_blur, k_blur), 0)

        blk_size = self.prep_config.get("threshold_block_size", 21)
        if blk_size % 2 == 0: blk_size += 1
        c_val = self.prep_config.get("threshold_c", 10)
        
        thresh = cv2.adaptiveThreshold(blurred, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
                                        cv2.THRESH_BINARY, blk_size, -c_val)

        k_morph = self.prep_config.get("morph_kernel", 3)
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (k_morph, k_morph))
        opened = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, kernel)
            
        return opened

    def inspect(self, ic_img):
        gray = cv2.cvtColor(ic_img, cv2.COLOR_BGR2GRAY)
        opened_thresh = self.preprocess(gray)
        height, width = ic_img.shape[:2]
        debug_img = ic_img.copy()
        faulty_pins = []

        is_vertical_strip = height >= width

        if is_vertical_strip:
            # Pins extend horizontally along X, stacked vertically along Y axis
            projection = np.sum(opened_thresh, axis=1).astype(float) # row-wise sum along Y
            mx = np.max(projection)
            if mx > 0:
                norm_proj = projection / mx * 255.0
                calib_thresh = self.prep_config.get("threshold", 50)
                min_height = max(40, calib_thresh)
                
                peaks, _ = find_peaks(norm_proj, height=min_height, distance=8, prominence=20)
                peaks = peaks.tolist()

                # Pitch check along Y
                if len(peaks) > 2:
                    pitches = np.diff(peaks)
                    median_pitch = np.median(pitches)
                    pitch_thresh_ratio = 0.35
                    final_thresh = max(self.pitch_threshold, median_pitch * pitch_thresh_ratio)

                    for i, p_val in enumerate(pitches):
                        if abs(p_val - median_pitch) > final_thresh:
                            y1, y2 = peaks[i], peaks[i+1]
                            faulty_pt = (width // 2, (y1 + y2) // 2)
                            faulty_pins.append(faulty_pt)
                            cv2.rectangle(debug_img, (5, y1), (width - 5, y2), (0, 0, 255), 2)
                            cv2.putText(debug_img, "NG-PITCH", (10, (y1 + y2) // 2), 
                                        cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 0, 255), 1)

                # Brightness anomaly check across horizontal pin tips
                if len(peaks) >= 2:
                    med_p = np.median(np.diff(peaks)) if len(peaks) > 2 else 12
                    half_h = max(3, int(med_p // 3))
                    
                    pin_brightnesses = []
                    pin_boxes = []

                    # Pin tip region: rightmost 50% of width
                    tip_x1 = int(width * 0.45)
                    tip_x2 = width - 2

                    for i, y_p in enumerate(peaks):
                        y1 = max(0, y_p - half_h)
                        y2 = min(height, y_p + half_h)
                        
                        pin_crop = gray[y1:y2, tip_x1:tip_x2]
                        if pin_crop.size > 0:
                            b_val = float(np.mean(pin_crop))
                            pin_brightnesses.append(b_val)
                            pin_boxes.append((tip_x1, y1, tip_x2 - tip_x1, y2 - y1))

                    if pin_brightnesses:
                        med_b = float(np.median(pin_brightnesses))
                        bright_thresh_ratio = self.prep_config.get("brightness_thresh_ratio", 0.30)
                        bright_cutoff = self.prep_config.get("intensity_bright_cutoff", 175)

                        for idx, b_val in enumerate(pin_brightnesses):
                            is_anomalous_bright = (med_b > 15 and (b_val - med_b) / med_b > bright_thresh_ratio) or \
                                                  (b_val > bright_cutoff and b_val - med_b > 30)
                            if is_anomalous_bright:
                                bx, by, bw, bh = pin_boxes[idx]
                                faulty_pt = (bx + bw // 2, by + bh // 2)
                                if faulty_pt not in faulty_pins:
                                    faulty_pins.append(faulty_pt)
                                
                                # Draw horizontal bounding box around defective pin tip (like yellow box)
                                cv2.rectangle(debug_img, (bx, by), (bx + bw, by + bh), (0, 0, 255), 2)
                                cv2.putText(debug_img, "NG-BRIGHT", (max(2, bx - 60), by + bh // 2 + 4), 
                                            cv2.FONT_HERSHEY_SIMPLEX, 0.35, (0, 0, 255), 1)

        else:
            # Horizontal strip: Pins extend vertically along Y, stacked horizontally along X axis
            offset_ratio = 0.05
            scan_width_ratio = 0.15
            offset_px = int(height * offset_ratio)
            scan_h_px = int(height * scan_width_ratio)
            pitch_thresh_ratio = 0.35
            
            bands = [
                ("TOP", offset_px, offset_px + scan_h_px, True),
                ("BOTTOM", height - offset_px - scan_h_px, height - offset_px, False)
            ]

            for name, y_start, y_end, is_top in bands:
                roi_bin = opened_thresh[y_start:y_end, :]
                if roi_bin.shape[0] < 3 or roi_bin.shape[1] < 10: continue

                cv2.rectangle(debug_img, (0, y_start), (width, y_end), (255, 200, 0), 1)
                check_y = y_start + (scan_h_px // 2) if is_top else y_end - (scan_h_px // 2)
                
                projection = np.sum(roi_bin, axis=0).astype(float)
                mx = np.max(projection)
                if mx == 0: continue
                norm_proj = projection / mx * 255.0

                calib_thresh = self.prep_config.get("threshold", 50)
                min_height = max(50, calib_thresh)
                
                peaks, _ = find_peaks(norm_proj, height=min_height, distance=6, prominence=30)
                peaks = peaks.tolist()

                if len(peaks) > 2:
                    pitches = np.diff(peaks)
                    median_pitch = np.median(pitches)
                    pitch_thresh = self.pitch_threshold
                    dynamic_thresh = median_pitch * pitch_thresh_ratio
                    final_thresh = max(pitch_thresh, dynamic_thresh)

                    for i, p_val in enumerate(pitches):
                        if i != 0 and i != len(pitches) - 1: continue
                        if abs(p_val - median_pitch) > final_thresh:
                            x1, x2 = peaks[i], peaks[i+1]
                            faulty_pt = ((x1+x2)//2, check_y)
                            faulty_pins.append(faulty_pt)
                            cv2.line(debug_img, (x1, check_y), (x2, check_y), (0, 0, 255), 2)
                            cv2.putText(debug_img, "NG-PITCH", (faulty_pt[0]-5, faulty_pt[1]-5), 
                                        cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0,0,255), 1)

                if len(peaks) >= 2:
                    med_p = np.median(np.diff(peaks)) if len(peaks) > 2 else 10
                    half_w = max(3, int(med_p // 3))
                    pin_brightnesses = []
                    pin_boxes = []

                    for i, p in enumerate(peaks):
                        x1 = max(0, p - half_w)
                        x2 = min(width, p + half_w)
                        pin_crop = gray[y_start:y_end, x1:x2]
                        if pin_crop.size > 0:
                            b_val = float(np.mean(pin_crop))
                            pin_brightnesses.append(b_val)
                            pin_boxes.append((x1, y_start, x2 - x1, y_end - y_start))

                    if pin_brightnesses:
                        med_b = float(np.median(pin_brightnesses))
                        bright_thresh_ratio = self.prep_config.get("brightness_thresh_ratio", 0.35)
                        bright_cutoff = self.prep_config.get("intensity_bright_cutoff", 180)

                        for idx, b_val in enumerate(pin_brightnesses):
                            is_anomalous_bright = (med_b > 20 and (b_val - med_b) / med_b > bright_thresh_ratio) or \
                                                  (b_val > bright_cutoff and b_val - med_b > 35)
                            if is_anomalous_bright:
                                bx, by, bw, bh = pin_boxes[idx]
                                faulty_pt = (bx + bw // 2, by + bh // 2)
                                if faulty_pt not in faulty_pins:
                                    faulty_pins.append(faulty_pt)
                                cv2.rectangle(debug_img, (bx, by), (bx + bw, by + bh), (0, 0, 255), 2)
                                cv2.putText(debug_img, "NG-BRIGHT", (bx, max(10, by - 3)), 
                                            cv2.FONT_HERSHEY_SIMPLEX, 0.35, (0, 0, 255), 1)

        return debug_img, faulty_pins
