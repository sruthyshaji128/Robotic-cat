import cv2
import sys
import os

# Add parent directory to path to import Camera
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from camera import Camera

def verify():
    print("Starting Camera verification...")
    cam = Camera(source=0)
    
    # Check if backend is DSHOW
    backend_info = cam.cap.getBackendName()
    print(f"DirectShow backend check: {backend_info}")
    
    # Check buffer size property
    buffer_size = cam.cap.get(cv2.CAP_PROP_BUFFERSIZE)
    print(f"Buffer size: {buffer_size}")
    
    # Attempt to start the loop briefly
    cam.start()
    import time
    time.sleep(1)
    
    frame = cam.get_frame()
    if frame is not None:
        print("Successfully captured a frame!")
        print(f"Frame shape: {frame.shape}")
    else:
        print("No frame captured yet (this is expected if no camera is attached).")
    
    cam.stop()
    print("Verification complete.")

if __name__ == "__main__":
    verify()
