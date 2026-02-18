
from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import cv2
import base64
import json
import asyncio
from config import config
from camera import Camera
from detector import Detector
from robot_logic import RobotLogic

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

camera = Camera(source=config.WEBCAM_INDEX)
detector = Detector(demo_mode=config.DEMO_MODE)
robot = RobotLogic()

@app.on_event("startup")
async def startup_event():
    print("Starting Robot System...")
    camera.start()

@app.on_event("shutdown")
async def shutdown_event():
    print("Shutting down Robot System...")
    camera.stop()

@app.get("/health")
def health_check():
    return {"status": "ok", "mode": "DEMO" if config.DEMO_MODE else "LIVE"}

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            # Handle incoming commands (if any)
            try:
                # Use non-blocking wait for data
                raw_data = await asyncio.wait_for(websocket.receive_text(), timeout=0.01)
                command_data = json.loads(raw_data)
                cmd = command_data.get("command")
                if cmd == "START":
                    robot.start()
                elif cmd == "STOP":
                    robot.stop()
                elif cmd == "SET_THRESHOLD":
                    config.CONFIDENCE_THRESHOLD = float(command_data.get("value", 50)) / 100.0
            except asyncio.TimeoutError:
                pass
            except Exception as e:
                print(f"Command error: {e}")

            frame = camera.get_frame()
            if frame is not None:
                active_detections = []
                # 1. Detect only if robot is active
                if robot.is_active:
                    detections = detector.detect(frame)
                    # Filter by confidence threshold
                    active_detections = [d for d in detections if d['confidence'] >= config.CONFIDENCE_THRESHOLD * 100]

                # 2. Update Robot Logic (active_detections will be empty if inactive)
                robot.update(active_detections)
                status = robot.get_status()
                status["confidence_threshold"] = int(config.CONFIDENCE_THRESHOLD * 100)

                # 3. Draw UI overlays
                frame = detector.draw_boxes(frame, active_detections)
                
                # Encode frame to base64
                _, buffer = cv2.imencode('.jpg', frame)
                frame_b64 = base64.b64encode(buffer).decode('utf-8')

                # Send data
                payload = {
                    "frame": frame_b64,
                    "status": status,
                    "detections": active_detections
                }
                
                # Log stats to confirm updates
                print(f"[WS] State: {status['state']} | Detections: {len(active_detections)} | Total: {status['stats']['total_detections']}")
                
                await websocket.send_json(payload)
            
            await asyncio.sleep(0.05) # Lowered frequency slightly for better stability
    except Exception as e:
        print(f"WebSocket client disconnected: {e}")
    finally:
        await websocket.close()

if __name__ == "__main__":
    uvicorn.run(app, host=config.API_HOST, port=config.API_PORT)
