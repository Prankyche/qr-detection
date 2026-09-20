QUICK START
============================================================

STEP 1: Install dependencies
    $ pip install opencv-python pyzbar numpy

STEP 2: Test on video
    from qr_detection_AEROTHON_FINAL import QRDetectionPipeline_Pi_Optimized, video_frame_generator
    
    pipeline = QRDetectionPipeline_Pi_Optimized()
    frame_gen = video_frame_generator("your_drone_footage.mp4", resize_width=640)
    
    for frame_num, result, fps in pipeline.process_frame_stream(frame_gen):
        if result:
            print(f"✓ QR FOUND: {result['data']}")

STEP 3: Integrate with mission
    from qr_integration_example import AerothonAutonomousMission
    mission = AerothonAutonomousMission('/dev/ttyUSB0')
    mission.run_mission()


DEBUGGING
============================================================

"FPS too slow (< 2 FPS)"
    → Check: Is YOLO somehow loaded? (it shouldn't be)
    → Fix: Reduce resize_width to 480
    → Profile: cProfile your frame processing

"QR not detected"
    → Check: Does it work on PC? (if not, QR might be damaged)
    → Fix: Print frame stats to see if adaptation kicks in
    → Adjust: Lower max_misses_before_preprocess to 3

"Runs on PC, slow on Pi"
    → Expected: Pi is 2-3x slower than modern CPU
    → Fix: Warm up camera first 30 frames, use resize_width=480


MISSION INTEGRATION:
============================================================

See qr_integration_example.py for full code. Quick flow:

    1. Arm & takeoff(10m)
    2. Loiter & scan for QR
    3. Once QR detected:
       - Parse location from QR string
       - Navigate to drop zone
       - Descend to 5m
       - Release payload
       - RTL

Everything is wired with DroneKit, all telemetry logged.
