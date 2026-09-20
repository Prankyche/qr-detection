"""
Aerothon 2026 - QR Detection Integration with DroneKit
This shows how to integrate QR detection into your autonomous flight loop.
"""

import cv2
import time
from qr_detection_AEROTHON_FINAL import QRDetectionPipeline_Pi_Optimized, camera_frame_generator
from dronekit import connect, VehicleMode
from pymavlink.dialects.v10 import mavutil

# ============================================
# CONFIGURATION
# ============================================

DRONE_CONNECTION = '/dev/ttyUSB0'  # Serial port on Pi (or 'udp:127.0.0.1:14550' for SITL)
BAUD_RATE = 921600  # For Pixhawk Cube Orange+
LOITER_ALTITUDE = 10  # Meters (scanning altitude)
DROP_ALTITUDE = 5    # Meters (payload drop altitude)
QR_TIMEOUT = 60      # Seconds to scan for QR before RTL
CAMERA_ID = 0        # USB camera index
RESIZE_WIDTH = 640   # Processed frame width

# ============================================
# QR DATA PARSER (Adjust to your QR format)
# ============================================

def parse_qr_location(qr_string: str) -> tuple:
    """
    Parse QR code to extract drop zone coordinates.
    
    Example format: "LAT:-37.8731,LON:144.9898,ALT:5"
    Adjust this function to match your team's QR format.
    """
    try:
        parts = qr_string.split(',')
        data = {}
        for part in parts:
            if ':' in part:
                key, value = part.split(':')
                data[key.strip()] = float(value.strip())
        
        if 'LAT' in data and 'LON' in data:
            return (data['LAT'], data['LON'])
        else:
            print(f"ERROR: Invalid QR format. Expected LAT/LON in: {qr_string}")
            return None
    except Exception as e:
        print(f"ERROR parsing QR: {e}")
        return None


# ============================================
# DRONE FLIGHT CONTROLLER
# ============================================

class AerothonAutonomousMission:
    """Manages autonomous flight with QR detection and payload drop."""
    
    def __init__(self, connection_string, baud=921600):
        print(f"[INIT] Connecting to drone at {connection_string}...")
        self.vehicle = connect(connection_string, baud=baud, wait_ready=True)
        print(f"[INIT] Connected! Vehicle: {self.vehicle.system_status.state}")
        
        # Mission state
        self.mission_phase = "PREFLIGHT"  # PREFLIGHT -> TAKEOFF -> SCAN -> NAVIGATE -> DROP -> RTL
        self.qr_detected = None
        self.qr_location = None
        self.frame_count = 0
        
        # QR pipeline
        self.qr_pipeline = QRDetectionPipeline_Pi_Optimized()
        self.scan_start_time = None
    
    def arm_and_takeoff(self, altitude):
        """Arm and takeoff to target altitude."""
        print(f"\n[TAKEOFF] Arming and taking off to {altitude}m...")
        
        self.vehicle.mode = VehicleMode("GUIDED")
        self.vehicle.armed = True
        
        # Wait for arming
        while not self.vehicle.armed:
            print("  Waiting for arm...")
            time.sleep(0.5)
        
        # Takeoff
        self.vehicle.simple_takeoff(altitude)
        
        while True:
            alt = self.vehicle.location.global_relative_frame.alt
            print(f"  Altitude: {alt:.1f}m")
            
            if alt >= altitude * 0.95:  # Within 5% of target
                print(f"[TAKEOFF] Reached {altitude}m ✓")
                break
            
            time.sleep(1)
    
    def scan_for_qr(self, timeout_sec=60):
        """
        Hover at current altitude and scan for QR code.
        Returns QR data or None if timeout.
        """
        print(f"\n[SCAN] Starting QR scan (timeout: {timeout_sec}s)...")
        print(f"  Altitude: {self.vehicle.location.global_relative_frame.alt:.1f}m")
        
        self.scan_start_time = time.time()
        self.vehicle.mode = VehicleMode("LOITER")  # Hover
        
        frame_gen = camera_frame_generator(camera_id=CAMERA_ID, resize_width=RESIZE_WIDTH)
        
        def on_qr_detect(frame_num, result):
            print(f"\n{'='*60}")
            print(f"✓✓✓ QR CODE DETECTED ✓✓✓")
            print(f"{'='*60}")
            print(f"  Data: {result['data']}")
            print(f"  Frame: {frame_num} | Attempt: {result['attempt']}")
            print(f"  Confidence: Stage {result['attempt']} (1=fast, 2=enhanced)")
            print(f"{'='*60}\n")
            
            self.qr_detected = result['data']
        
        # Scan loop
        for frame_num, result, fps in self.qr_pipeline.process_frame_stream(
            frame_gen,
            callback_on_detect=on_qr_detect
        ):
            self.frame_count = frame_num
            
            # Display status every 30 frames
            if frame_num % 30 == 0:
                alt = self.vehicle.location.global_relative_frame.alt
                elapsed = time.time() - self.scan_start_time
                status = "✓ DETECTED!" if self.qr_detected else "Scanning..."
                print(f"[{frame_num}] {status} | Alt: {alt:.1f}m | FPS: {fps:.1f} | Elapsed: {elapsed:.1f}s")
            
            # Timeout check
            if time.time() - self.scan_start_time > timeout_sec:
                print(f"\n[SCAN] TIMEOUT after {timeout_sec}s")
                return None
            
            # Success: QR detected
            if self.qr_detected:
                return self.qr_detected
        
        return None
    
    def navigate_to_drop_zone(self, lat, lon):
        """Navigate drone to target coordinates."""
        print(f"\n[NAVIGATE] Moving to drop zone: ({lat}, {lon})...")
        
        self.vehicle.mode = VehicleMode("GUIDED")
        
        from dronekit import LocationGlobalRelative
        target = LocationGlobalRelative(lat, lon, DROP_ALTITUDE)
        
        self.vehicle.simple_goto(target)
        
        # Monitor distance to target
        while True:
            current = self.vehicle.location.global_frame
            
            # Calculate distance (rough approximation)
            dlat = current.lat - lat
            dlon = current.lon - lon
            distance = (dlat**2 + dlon**2) ** 0.5 * 111000  # Rough m/degree
            
            alt = self.vehicle.location.global_relative_frame.alt
            
            print(f"  Distance: {distance:.1f}m | Altitude: {alt:.1f}m")
            
            if distance < 5:  # Within 5m
                print(f"[NAVIGATE] Reached drop zone ✓")
                break
            
            time.sleep(1)
        
        # Descend to drop altitude
        print(f"[NAVIGATE] Descending to {DROP_ALTITUDE}m...")
        while alt > DROP_ALTITUDE * 1.05:
            alt = self.vehicle.location.global_relative_frame.alt
            print(f"  Altitude: {alt:.1f}m")
            time.sleep(1)
        
        print(f"[NAVIGATE] At drop zone ✓")
    
    def drop_payload(self):
        """Trigger payload release (via servo, GPIO, or MAVLink command)."""
        print(f"\n[DROP] Releasing payload...")
        
        # Option 1: GPIO (if using Pi GPIO for servo)
        # import RPi.GPIO as GPIO
        # GPIO.output(SERVO_PIN, GPIO.HIGH)
        # time.sleep(1)
        # GPIO.output(SERVO_PIN, GPIO.LOW)
        
        # Option 2: MAVLink do_set_servo command (for Pixhawk aux channel)
        msg = self.vehicle.message_factory.command_long_encode(
            0, 0,  # target_system, target_component
            mavutil.mavlink.MAV_CMD_DO_SET_SERVO,  # command
            0,     # confirmation
            9,     # param1: servo channel (9 for Pixhawk AUX1)
            1900,  # param2: PWM value (1900 = release)
            0, 0, 0, 0, 0
        )
        
        self.vehicle.send_mavlink(msg)
        print(f"[DROP] Payload released ✓")
        
        time.sleep(2)
    
    def return_to_launch(self):
        """Return to takeoff location and land."""
        print(f"\n[RTL] Initiating return to launch...")
        
        self.vehicle.mode = VehicleMode("RTL")
        
        print(f"[RTL] Waiting for landing...")
        while self.vehicle.mode.name == "RTL":
            alt = self.vehicle.location.global_relative_frame.alt
            print(f"  Altitude: {alt:.1f}m")
            
            if alt < 0.5:
                print(f"[RTL] Landed ✓")
                break
            
            time.sleep(2)
        
        # Disarm
        self.vehicle.armed = False
        print(f"[RTL] Mission complete ✓")
    
    def emergency_rtl(self, reason):
        """Emergency return to launch."""
        print(f"\n[EMERGENCY] {reason}")
        self.vehicle.mode = VehicleMode("RTL")
        print(f"[EMERGENCY] RTL initiated")
    
    def run_mission(self):
        """Execute full autonomous mission."""
        try:
            # Phase 1: Takeoff
            self.mission_phase = "TAKEOFF"
            self.arm_and_takeoff(LOITER_ALTITUDE)
            time.sleep(2)
            
            # Phase 2: Scan for QR
            self.mission_phase = "SCAN"
            qr_data = self.scan_for_qr(timeout_sec=QR_TIMEOUT)
            
            if not qr_data:
                self.emergency_rtl("QR not detected within timeout")
                return False
            
            # Phase 3: Parse QR and navigate
            self.mission_phase = "NAVIGATE"
            self.qr_location = parse_qr_location(qr_data)
            
            if not self.qr_location:
                self.emergency_rtl("Failed to parse QR location")
                return False
            
            lat, lon = self.qr_location
            self.navigate_to_drop_zone(lat, lon)
            time.sleep(1)
            
            # Phase 4: Drop payload
            self.mission_phase = "DROP"
            self.drop_payload()
            time.sleep(2)
            
            # Phase 5: Return to launch
            self.mission_phase = "RTL"
            self.return_to_launch()
            
            print(f"\n{'='*60}")
            print(f"MISSION SUCCESS ✓")
            print(f"{'='*60}")
            print(f"Frames processed: {self.frame_count}")
            print(f"QR detected: {self.qr_detected}")
            print(f"Drop zone: {self.qr_location}")
            
            return True
        
        except KeyboardInterrupt:
            print(f"\nMission interrupted by user")
            self.emergency_rtl("User interrupt")
            return False
        
        except Exception as e:
            print(f"\nMission error: {e}")
            self.emergency_rtl(f"Error: {e}")
            return False
        
        finally:
            if self.vehicle:
                self.vehicle.close()


# ============================================
# MAIN: Run the mission
# ============================================

if __name__ == "__main__":
    print("\n" + "="*60)
    print("AEROTHON 2026 - AUTONOMOUS QR DELIVERY MISSION")
    print("="*60)
    
    # Test mode (SITL on localhost)
    connection_string = 'udp:127.0.0.1:14550'
    # Real mode (actual Pixhawk)
    # connection_string = '/dev/ttyUSB0'
    
    mission = AerothonAutonomousMission(connection_string)
    success = mission.run_mission()
    
    exit(0 if success else 1)
