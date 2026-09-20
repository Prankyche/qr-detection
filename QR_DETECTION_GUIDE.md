# QR Detection Pipeline

## How to Use

### For Live Camera (Onboard Pi)
```python
from qr_detection_AEROTHON_FINAL import QRDetectionPipeline_Pi_Optimized, camera_frame_generator

pipeline = QRDetectionPipeline_Pi_Optimized()
frame_gen = camera_frame_generator(camera_id=0, resize_width=640)

for frame_num, result, fps in pipeline.process_frame_stream(frame_gen):
    if result:
        print(f"QR FOUND: {result['data']}")
        # TRIGGER PAYLOAD DROP HERE
        break
```

### For Testing on Video
```python
from qr_detection_AEROTHON_FINAL import QRDetectionPipeline_Pi_Optimized, video_frame_generator

pipeline = QRDetectionPipeline_Pi_Optimized()
frame_gen = video_frame_generator("drone_footage_10m.mp4", resize_width=640)

for frame_num, result, fps in pipeline.process_frame_stream(
    frame_gen, 
    callback_on_detect=lambda n, r: print(f"Frame {n}: {r['data']}")
):
    pass
```

---

## Key Features Explained

### 1. **Direct Decode (Stage 1)**
Tries to read the QR code directly from the raw frame. This works ~80% of the time at 10m altitude.

```python
results = decode(image)  # That's it. Fast.
```

**Why it's fast:** pyzbar is a compiled C library. No ML, no loops, just FFT-based scanning.

---

### 2. **Enhanced Decode (Stage 2)**
When direct fails after 5 frames, kicks in CLAHE (Contrast Limited Adaptive Histogram Equalization).

```python
# CLAHE boosts local contrast without over-amplifying noise
clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
enhanced = clahe.apply(gray)  # Fixes low-light, hazy QR codes

# Light sharpening to restore lost edges
kernel = np.array([[-1, -1, -1], [-1,  9, -1], [-1, -1, -1]])
sharpened = cv2.filter2D(enhanced, -1, kernel)

results = decode(sharpened)  # Try again on enhanced frame
```

**Why CLAHE works at 10m:**
- Fixes atmospheric haze (light rays scatter)
- Recovers QR edges lost in motion blur
- Local processing = handles uneven lighting
- Fast (~50ms on Pi 5)

---

### 3. **Adaptive Confidence**
Tracks consecutive misses. Upgrades strategy automatically.

```python
self.consecutive_misses += 1
if self.consecutive_misses >= 5:  # After 5 fails
    # Try expensive preprocessing
    result = self.enhanced_decode(image)
```

**Why it matters:**
- Drone is hovering but QR might be at angle initially → direct fails 2-3x
- Then QR centers → enhancement kicks in
- No wasted YOLO on every frame
- Adapts to real flight conditions

---

### 4. **Frame Stream Processing**
Generator-based pipeline. No buffering, no blocking.

```python
for frame_num, result, fps in pipeline.process_frame_stream(frame_gen):
    if result:  # Non-blocking
        # Do something
```

**Why generators:**
- Memory efficient (process 1 frame at a time)
- Doesn't block camera I/O
- Easy to parallelize with separate threads
- FPS calculated in real-time

---

## Installation & Dependencies

```bash
pip install opencv-python pyzbar numpy

# Optionally (for older Pi versions):
pip install --break-system-packages opencv-python  # If using system Python
```

---

## Usage: Real Flight Mission

### Onboard Raspberry Pi 5 (During Flight)

```python
#!/usr/bin/env python3
from qr_detection_AEROTHON_FINAL import QRDetectionPipeline_Pi_Optimized, camera_frame_generator
import time

pipeline = QRDetectionPipeline_Pi_Optimized()
qr_data = None
detected_time = None

def on_qr_found(frame_num, result):
    global qr_data, detected_time
    qr_data = result['data']
    detected_time = result['timestamp']
    print(f"[QR FOUND] {qr_data} at frame {frame_num}, attempt {result['attempt']}")

# Main mission loop
def autonomous_mission():
    global qr_data
    
    print("1. Taking off to 10m...")
    # drone.takeoff(10)
    
    print("2. Scanning for QR code...")
    frame_gen = camera_frame_generator(camera_id=0, resize_width=640)
    
    for frame_num, result, fps in pipeline.process_frame_stream(
        frame_gen,
        callback_on_detect=on_qr_found
    ):
        if frame_num % 30 == 0:
            print(f"  Frame {frame_num}: FPS={fps:.1f}")
        
        if qr_data:
            print(f"3. QR detected: {qr_data}")
            print(f"   Navigating to coordinates...")
            coords = parse_qr_data(qr_data)
            
            print(f"4. Descending to 5m for payload drop...")
            
            print(f"5. Dropping payload...")
            
            print(f"6. Returning to launch...")
            
            break
    else:
        print("ERROR: QR not detected in mission time. RTL.")
        # drone.return_to_launch()

if __name__ == "__main__":
    autonomous_mission()
```

---

## Debugging: Print Frame Stats

Add this to see what's happening:

```python
for frame_num, result, fps in pipeline.process_frame_stream(frame_gen):
    if result:
        print(f"✓ Frame {frame_num}: {result['data']} ({result['attempt']} attempt)")
    else:
        print(f"✗ Frame {frame_num}: no decode | Misses: {pipeline.consecutive_misses}")
    
    if frame_num > 500:
        break
```

This tells you:
- How many frames before detection?
- What's the attempt rate (direct vs enhanced)?
- Is it bouncing between stages?

---

## Common Issues & Fixes

### Issue: "Very slow FPS (< 2 FPS)"
**Cause:** Using too high resize_width or YOLO is somehow running.
**Fix:**
```python
# Check 1: Is YOLO loaded?
import sys
print("YOLO loaded?" in str(sys.modules))  # Should be False

# Check 2: Reduce resize
frame_gen = camera_frame_generator(resize_width=480)

# Check 3: Profile
import cProfile
cProfile.run('pipeline.detect_and_decode(frame)')
```

### Issue: "QR detected wrong (false positives)"
**Cause:** CLAHE too aggressive or noise in frame.
**Fix:**
```python
# Weaken CLAHE
clahe = cv2.createCLAHE(clipLimit=1.5, tileGridSize=(8, 8))

# Add validation layer
if result and len(result['data']) > 20:  # QR should be <20 chars
    print(f"WARNING: Suspicious QR length {len(result['data'])}")
```

### Issue: "Detection works on PC, not on Pi"
**Cause:** Pi is slower; needs more frames to reach adaptive threshold.
**Fix:**
```python
pipeline.max_misses_before_preprocess = 3  # Lower threshold for Pi

# Or, pre-warm the camera
for _ in range(30):
    cap.read()  # Skip first 30 frames (camera warmup)
```

---
