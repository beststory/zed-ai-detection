#!/usr/bin/env python3
import sys
import os
sys.path.insert(0, '/usr/local/lib/python3.12/dist-packages')

# Enable verbose logging
os.environ['ZED_VERBOSE'] = '1'

try:
    import pyzed.sl as sl
    
    print("="*60)
    print("ZED Camera Detection with Verbose Logging")
    print("="*60)
    
    # Create Camera object
    zed = sl.Camera()
    
    # Get available cameras
    devices = sl.Camera.get_device_list()
    print(f"\nsl.Camera.get_device_list() returned {len(devices)} devices")
    
    for idx, device in enumerate(devices):
        print(f"\n--- Device {idx} ---")
        print(f"Serial Number: {device.serial_number}")
        print(f"Camera Model: {device.camera_model}")
        print(f"Camera State: {device.camera_state}")
        print(f"Path: {device.path}")
    
    if len(devices) == 0:
        print("\n❌ No ZED cameras detected by SDK!")
        print("\nDiagnostics:")
        
        # Try to list USB devices
        import subprocess
        result = subprocess.run(['lsusb'], capture_output=True, text=True)
        zed_devices = [line for line in result.stdout.split('\n') if 'ZED' in line or '2b03' in line]
        
        if zed_devices:
            print(f"\nFound {len(zed_devices)} ZED USB device(s):")
            for device in zed_devices:
                print(f"  {device}")
            print("\n⚠️  Camera is connected via USB but SDK cannot detect it.")
            print("This usually means:")
            print("  1. Camera firmware needs updating")
            print("  2. Camera is in wrong USB mode")
            print("  3. SDK initialization issue")
        else:
            print("\n❌ No ZED devices found in lsusb either!")
        
        sys.exit(1)
    
    print("\n" + "="*60)
    print("Attempting to open first camera...")
    print("="*60)
    
    init_params = sl.InitParameters()
    init_params.camera_resolution = sl.RESOLUTION.HD720
    init_params.camera_fps = 30
    init_params.depth_mode = sl.DEPTH_MODE.ULTRA
    init_params.sdk_verbose = 1
    
    err = zed.open(init_params)
    
    if err != sl.ERROR_CODE.SUCCESS:
        print(f"\n❌ Failed to open camera: {err}")
        sys.exit(1)
    else:
        print("\n✅ Camera opened successfully!")
        cam_info = zed.get_camera_information()
        print(f"Serial Number: {cam_info.serial_number}")
        print(f"Firmware Version: {cam_info.camera_firmware_version}")
        zed.close()

except ImportError as e:
    print(f"❌ Error importing pyzed: {e}")
    sys.exit(1)
except Exception as e:
    print(f"❌ Unexpected error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
