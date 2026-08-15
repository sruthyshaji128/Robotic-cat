# Weed Detection & Removal Robot 🌿⚡

A Raspberry Pi 4-based agricultural robot that uses **YOLOv8 computer vision** to detect weed plants in real-time and triggers a **linear actuator (plough arm)** to uproot them automatically.

![System Architecture](docs/architecture.png)

---

## How It Works

1. **USB Camera** captures live ground footage
2. **YOLOv8** detects weed plants in each frame
3. **Strike Zone** logic checks if a weed centroid falls within the arm's reach area
4. **Linear Actuator (plough)** is triggered to extend and uproot the weed
5. **Web Dashboard** streams live annotated video + real-time stats at `http://localhost:5000`

---

## Project Structure

```
weed-robot/
├── config.py                  ← ⚙️  All settings (tune this first!)
├── main.py                    ← 🚀 Main control loop
├── requirements.txt           ← PC/VM dependencies
├── requirements_rpi.txt       ← Raspberry Pi dependencies
│
├── modules/
│   ├── camera_module.py       ← USB camera / simulation
│   ├── weed_detector.py       ← YOLOv8 inference
│   ├── arm_controller.py      ← GPIO / Serial / Simulate
│   └── strike_zone.py         ← Zone geometry & triggers
│
├── dashboard/
│   ├── app.py                 ← Flask server
│   └── templates/index.html   ← Live monitoring UI
│
├── train/
│   ├── dataset_prep.py        ← Download & prepare dataset
│   └── train.py               ← Fine-tune YOLOv8
│
├── models/
│   └── download_model.py      ← Get starter weights
│
├── scripts/
│   ├── deploy_to_rpi.sh       ← rsync to RPi
│   └── install_rpi.sh         ← RPi setup script
│
└── tests/                     ← Pytest unit tests
```

---

## Quick Start (PC / VM)

### 1. Install dependencies
```bash
cd weed-robot
pip install -r requirements.txt
```

### 2. Download base model
```bash
python models/download_model.py
```

### 3. Run in simulation mode
```bash
python main.py --simulate --dashboard
```

Open your browser → [http://localhost:5000](http://localhost:5000)

### 4. Run tests
```bash
pytest tests/ -v
```

---

## Configuration

Edit **`config.py`** to tune the robot:

| Setting | Description |
|---------|------------|
| `SIMULATE` | `True` = PC mode (no hardware), `False` = RPi |
| `CAMERA_INDEX` | USB camera index (usually `0`) |
| `STRIKE_ZONE` | Rectangle (fractions of frame) where arm can reach |
| `DETECTION_CONFIDENCE` | Min confidence to count a weed (0–1) |
| `ARM_GPIO_EXTEND_PIN` | BCM GPIO pin to extend linear actuator |
| `ARM_GPIO_RETRACT_PIN` | BCM GPIO pin to retract linear actuator |
| `ARM_COOLDOWN` | Seconds between consecutive strikes |
| `DEMO_MODE` | `True` = any object counts as weed (for testing) |

---

## Training a Custom Weed Model

```bash
# 1. Prepare dataset (DeepWeeds)
python train/dataset_prep.py --out train/data --max-images 2000

# 2. Train YOLOv8n (CPU, ~2-4 hours)
python train/train.py --data train/data/data.yaml --epochs 50 --batch 8

# 3. Model saved to models/best.pt
```

Set `DEMO_MODE = False` in `config.py` after training!

---

## Deploying to Raspberry Pi 4

### From PC:
```bash
bash scripts/deploy_to_rpi.sh weedfinder.local rpi
```

### On the Raspberry Pi:
```bash
ssh rpi@weedfinder.local
  cd ~/weed-robot
  bash scripts/install_rpi.sh
  sudo systemctl start weed-robot
```

Access the dashboard at `http://weedfinder.local:5000`

---

## Hardware Wiring (GPIO Mode)

| Component | RPi BCM Pin | Notes |
|-----------|-------------|-------|
| Actuator EXTEND | GPIO 17 | Via motor driver (L298N IN1) |
| Actuator RETRACT | GPIO 27 | Via motor driver (L298N IN2) |
| Motor Driver VCC | 5V | External power supply |
| Motor Driver GND | GND | Common ground |

> ⚠️ **Never connect the actuator motor directly to GPIO!** Always use a motor driver board or relay.

---

## Command Line Options

```bash
python main.py --help

Options:
  --simulate       Force simulation mode (no hardware)
  --no-dashboard   Disable web dashboard
  --duration N     Run for N seconds then exit
  --show-window    Show OpenCV preview window
```

---

## License
MIT
