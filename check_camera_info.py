#!/usr/bin/env python3
import sys
sys.path.insert(0, '/usr/local/lib/python3.12/dist-packages')

try:
    import pyzed.sl as sl

    print("="*60)
    print("ZED Camera Detection & Information")
    print("="*60)

    # Create Camera object
    zed = sl.Camera()

    # Get available cameras
    devices = sl.Camera.get_device_list()
    print(f"\nFound {len(devices)} ZED camera(s):")

    for idx, device in enumerate(devices):
        print(f"\n--- Camera {idx} ---")
        print(f"Serial Number: {device.serial_number}")
        print(f"Camera Model: {device.camera_model}")
        print(f"Camera State: {device.camera_state}")
        print(f"Path: {device.path}")

    if len(devices) == 0:
        print("\n❌ No ZED cameras detected!")
        print("\nTroubleshooting:")
        print("1. Check USB connection (requires USB 3.0)")
        print("2. Check udev rules: /etc/udev/rules.d/99-zed.rules")
        print("3. Check user permissions: groups command should show 'video'")
        sys.exit(1)

    # Try to open the first camera with minimal configuration
    print("\n" + "="*60)
    print("Attempting to open camera with USB 2.0 compatible settings...")
    print("="*60)

    init_params = sl.InitParameters()
    init_params.camera_resolution = sl.RESOLUTION.VGA  # Lowest resolution
    init_params.camera_fps = 15  # Lower FPS
    init_params.depth_mode = sl.DEPTH_MODE.NONE  # Disable depth to reduce bandwidth
    init_params.sdk_verbose = 1  # Enable verbose logging

    err = zed.open(init_params)

    if err != sl.ERROR_CODE.SUCCESS:
        print(f"\n❌ Failed to open camera: {err}")
        print("\nPossible causes:")
        print("1. Camera connected to USB 2.0 (requires USB 3.0 for full functionality)")
        print("2. Bandwidth limitation")
        print("3. Firmware issue")
        print("\nTry:")
        print("- Move camera to a blue USB 3.0 port")
        print("- Check 'lsusb -t' - camera should show 5000M or 20000M, not 480M")
    else:
        print("\n✅ Camera opened successfully!")

        # Get camera information
        cam_info = zed.get_camera_information()
        print(f"\nCamera Information:")
        print(f"Serial Number: {cam_info.serial_number}")
        print(f"Firmware Version: {cam_info.camera_firmware_version}")
        print(f"Sensors Firmware Version: {cam_info.sensors_firmware_version}")
        print(f"Camera Model: {cam_info.camera_model}")
        print(f"Resolution: {cam_info.camera_configuration.resolution}")
        print(f"FPS: {cam_info.camera_configuration.fps}")

        # Close camera
        zed.close()
        print("\n✅ Camera test complete!")

except ImportError as e:
    print(f"❌ Error importing pyzed: {e}")
    print("\nMake sure ZED SDK is installed correctly:")
    print("- Check /usr/local/lib/python3.12/dist-packages/pyzed")
    sys.exit(1)
except Exception as e:
    print(f"❌ Unexpected error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
