#!/usr/bin/env python3

import sys
import os
from pathlib import Path
from qr_detection_AEROTHON_FINAL import (
    QRDetectionPipeline_Pi_Optimized, 
    video_frame_generator
)


def test_video_file(video_path, resize_width=640, max_frames=None):
    if not os.path.exists(video_path):
        print(f"❌ ERROR: Video file not found: {video_path}")
        return None
    
    file_size = os.path.getsize(video_path) / (1024*1024)
    print(f"\n{'='*70}")
    print(f"QR DETECTION TEST - LAPTOP")
    print(f"{'='*70}")
    print(f"Video: {video_path}")
    print(f"Size: {file_size:.1f} MB")
    print(f"Processing resolution: {resize_width}px width")
    print(f"Max frames: {max_frames if max_frames else 'all'}")
    print(f"{'='*70}\n")
    
    pipeline = QRDetectionPipeline_Pi_Optimized()
    
    stats = {
        "total_frames": 0,
        "detected_frames": 0,
        "attempt1_success": 0,
        "attempt2_success": 0,
        "unique_qrs": {},
        "detections": [],
        "last_fps": 0,
        "processing_time": 0
    }
    
    import time
    start_time = time.time()
    
    def on_detect(frame_num, result):
        stats["detected_frames"] += 1
        
        if result["attempt"] == 1:
            stats["attempt1_success"] += 1
            attempt_str = "Direct (fast)"
        else:
            stats["attempt2_success"] += 1
            attempt_str = "Enhanced (CLAHE)"
        
        qr_data = result["data"]
        
        if qr_data not in stats["unique_qrs"]:
            stats["unique_qrs"][qr_data] = []
        stats["unique_qrs"][qr_data].append(frame_num)
        
        stats["detections"].append({
            "frame": frame_num,
            "data": qr_data,
            "attempt": result["attempt"],
            "method": attempt_str
        })
        
        print(f"  ✓ Frame {frame_num}: '{qr_data}' ({attempt_str})")
    
    try:
        print("Processing frames...")
        frame_gen = video_frame_generator(video_path, resize_width=resize_width, skip_frames=1)
        
        for frame_num, result, fps in pipeline.process_frame_stream(
            frame_gen,
            max_frames=max_frames,
            callback_on_detect=on_detect
        ):
            stats["total_frames"] = frame_num
            stats["last_fps"] = fps
            
            if frame_num % 60 == 0:
                percent = ""
                status = "scanning..." if not result else "✓ DETECTED!"
                print(f"Frame {frame_num}: {status} | FPS: {fps:.1f} | Consecutive misses: {pipeline.consecutive_misses}")
        
        stats["processing_time"] = time.time() - start_time
        
    except KeyboardInterrupt:
        print("\n⚠ Processing interrupted by user")
        stats["processing_time"] = time.time() - start_time
    
    except Exception as e:
        print(f"\n❌ ERROR during processing: {e}")
        import traceback
        traceback.print_exc()
        return None
    
    print_results(stats)
    
    return stats


def print_results(stats):
    """Print formatted results summary"""
    print(f"\n{'='*70}")
    print(f"RESULTS")
    print(f"{'='*70}")
    
    if stats["total_frames"] == 0:
        print("No frames processed")
        return
    
    # Summary stats
    print(f"\nProcessing:")
    print(f"  Total frames: {stats['total_frames']}")
    print(f"  Processing time: {stats['processing_time']:.2f} seconds")
    print(f"  Average FPS: {stats['total_frames']/stats['processing_time']:.1f}")
    
    # Detection stats
    detection_rate = 100 * stats["detected_frames"] / stats["total_frames"]
    print(f"\nDetection:")
    print(f"  Frames with QR: {stats['detected_frames']} ({detection_rate:.1f}%)")
    print(f"  Stage 1 (Direct): {stats['attempt1_success']} frames")
    print(f"  Stage 2 (Enhanced): {stats['attempt2_success']} frames")
    
    # Unique QRs detected
    if stats["unique_qrs"]:
        print(f"\nUnique QR Codes ({len(stats['unique_qrs'])}):")
        for qr_str, frame_list in sorted(stats["unique_qrs"].items()):
            first_frame = frame_list[0]
            count = len(frame_list)
            print(f"  • '{qr_str}'")
            print(f"    └─ Found {count} times (first at frame {first_frame})")
    else:
        print(f"\n No QR codes detected in video")
    
    if stats["detections"]:
        print(f"\nDetailed Detection Log:")
        for det in stats["detections"][:10]:  # Show first 10
            print(f"  Frame {det['frame']:4d}: {det['data']:20s} ({det['method']})")
        if len(stats["detections"]) > 10:
            print(f"  ... and {len(stats['detections'])-10} more")
    
    print(f"\n{'='*70}\n")


def test_multiple_videos(video_dir, pattern="*.mp4"):
    video_dir = Path(video_dir)
    
    if not video_dir.exists():
        print(f"Directory not found: {video_dir}")
        return
    
    videos = list(video_dir.glob(pattern))
    if not videos:
        print(f"No videos matching '{pattern}' in {video_dir}")
        return
    
    print(f"\nFound {len(videos)} video(s) to test\n")
    
    all_results = {}
    for video_path in sorted(videos):
        print(f"\n{'─'*70}")
        result = test_video_file(str(video_path), resize_width=640)
        if result:
            all_results[video_path.name] = result
    
    print(f"\n{'='*70}")
    print(f"BATCH SUMMARY")
    print(f"{'='*70}")
    for video_name, stats in all_results.items():
        detection_rate = 100 * stats["detected_frames"] / stats["total_frames"] if stats["total_frames"] > 0 else 0
        print(f"{video_name:30s}: {stats['detected_frames']:3d}/{stats['total_frames']:4d} frames ({detection_rate:5.1f}%)")


def interactive_test():
    print(f"\n{'='*70}")
    print(f"INTERACTIVE QR DETECTION TEST")
    print(f"{'='*70}\n")
    
    while True:
        video_path = input("Enter video path (or 'quit' to exit, 'dir' for directory): ").strip()
        
        if video_path.lower() == 'quit':
            print("Goodbye!")
            break
        
        if video_path.lower() == 'dir':
            dir_path = input("Enter directory path: ").strip()
            pattern = input("File pattern (default *.mp4): ").strip() or "*.mp4"
            test_multiple_videos(dir_path, pattern)
            continue
        
        if not video_path:
            print(" Please enter a path")
            continue
        
        # Get processing options
        resize = input("Resize width (default 640): ").strip()
        resize_width = int(resize) if resize else 640
        
        max_f = input("Max frames to process (default all): ").strip()
        max_frames = int(max_f) if max_f else None
        
        # Run test
        test_video_file(video_path, resize_width=resize_width, max_frames=max_frames)
        
        again = input("\nTest another video? (y/n): ").strip().lower()
        if again != 'y':
            break


if __name__ == "__main__":

    try:
        from qr_detection_AEROTHON_FINAL import QRDetectionPipeline_Pi_Optimized
    except ImportError:
        print(" ERROR: qr_detection_AEROTHON_FINAL.py not found in current directory")
        print("   Make sure both files are in the same folder:")
        print("   - qr_detection_AEROTHON_FINAL.py")
        print("   - test_qr_on_laptop.py")
        sys.exit(1)
    
    print("\n" + "="*70)
    print("AEROTHON 2026 - QR DETECTION LAPTOP TEST")
    print("="*70)
    print("\nUsage options:")
    print("  1. Interactive: python test_qr_on_laptop.py")
    print("  2. Single video: python test_qr_on_laptop.py /path/to/video.mp4")
    print("  3. Batch test: python test_qr_on_laptop.py /path/to/videos/ --pattern '*.mp4'")
    print()
    
    if len(sys.argv) == 1:
        interactive_test()
    
    elif len(sys.argv) == 2:
        video_path = sys.argv[1]
        test_video_file(video_path)
    
    elif len(sys.argv) >= 3 and sys.argv[2] == "--pattern":
        dir_path = sys.argv[1]
        pattern = sys.argv[3] if len(sys.argv) > 3 else "*.mp4"
        test_multiple_videos(dir_path, pattern)
    
    else:
        print("Invalid arguments")
        sys.exit(1)
