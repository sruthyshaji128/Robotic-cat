import cv2
import time
import threading
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class Camera:
    def __init__(self, source=0, width=640, height=480):
        self.source = source
        self.width = width
        self.height = height
        self.cap = None
        self.frame = None
        self.running = False
        self.lock = threading.Lock()
        self.thread = None
        
        self._initialize_capture()

    def _initialize_capture(self):
        """Attempts to open the camera with multiple backends."""
        backends = [cv2.CAP_DSHOW, cv2.CAP_MSMF, cv2.CAP_ANY]
        
        for backend in backends:
            logger.info(f"Attempting camera initialization with backend: {backend}")
            if self.cap is not None:
                self.cap.release()
            
            self.cap = cv2.VideoCapture(self.source, backend)
            if self.cap.isOpened():
                # Mandatory settings for real-time streaming
                self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
                self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
                
                # Test if we can actually get a frame
                ret, frame = self.cap.read()
                if ret:
                    logger.info(f"Successfully initialized camera with backend {backend}")
                    self.frame = frame
                    return
                else:
                    logger.warning(f"Opened but failed to read from backend {backend}")
        
        logger.error("All camera backends failed. Please check if another app is using the webcam.")

    def start(self):
        if self.running:
            return
        
        if self.cap is None or not self.cap.isOpened():
            self._initialize_capture()

        if self.cap and self.cap.isOpened():
            self.running = True
            self.thread = threading.Thread(target=self._capture_loop, name="CameraThread")
            self.thread.daemon = True
            self.thread.start()
            logger.info("Camera capture loop started")
        else:
            logger.error("Cannot start: Camera is not opened")

    def stop(self):
        self.running = False
        if self.thread:
            self.thread.join(timeout=1.0)
        if self.cap and self.cap.isOpened():
            self.cap.release()
        logger.info("Camera capture loop stopped and released")

    def _capture_loop(self):
        """
        Continuous capture loop.
        Uses grab() and retrieve() to be more resilient to buffer lag.
        """
        while self.running:
            try:
                # grab() move internal pointer to latest frame in hardware buffer
                if not self.cap.grab():
                    logger.warning("Camera grab() failed, possible disconnect")
                    time.sleep(1.0)
                    continue

                # retrieve() decodes the frame grabbed above
                ret, frame = self.cap.retrieve()
                if ret:
                    with self.lock:
                        self.frame = frame
                
                # Minor throttling to match camera FPS (~30fps) if needed,
                # but read/grab is usually blocking on camera clock.
                time.sleep(0.01)
            except Exception as e:
                logger.error(f"Error in capture loop: {e}")
                time.sleep(1.0)

    def get_frame(self):
        """Returns the most recent frame."""
        with self.lock:
            if self.frame is not None:
                return self.frame.copy()
            return None

    def __del__(self):
        self.stop()
