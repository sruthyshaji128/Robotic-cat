import os
import paramiko
from scp import SCPClient

RPI_IP = "weedfinder.local"
RPI_USER = "rpi"
RPI_PASS = "rpi"
REMOTE_DIR = "/home/rpi/weed-robot"

def create_ssh_client(server, port, user, password):
    client = paramiko.SSHClient()
    client.load_system_host_keys()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(server, port, user, password)
    return client

if __name__ == "__main__":
    print(f"Connecting to {RPI_USER}@{RPI_IP}...")
    ssh = create_ssh_client(RPI_IP, 22, RPI_USER, RPI_PASS)
    
    print("Creating remote directory...")
    ssh.exec_command(f"mkdir -p {REMOTE_DIR}/logs")
    
    print("Copying files...")
    scp = SCPClient(ssh.get_transport())
    
    files_to_copy = [
        "config.py", "main.py", "requirements.txt", "requirements_rpi.txt",
        "modules", "dashboard", "models", "tests", "scripts"
    ]
    
    for item in files_to_copy:
        if os.path.exists(item):
            print(f"  -> {item}")
            scp.put(item, recursive=True, remote_path=REMOTE_DIR)
            
    scp.close()
    print("Files copied successfully.")
    
    print("\nRunning installation script on the Raspberry Pi...")
    # Run the install script (this might take a while, so we read stdout)
    stdin, stdout, stderr = ssh.exec_command(f"cd {REMOTE_DIR} && bash scripts/install_rpi.sh")
    
    for line in iter(stdout.readline, ""):
        print(line, end="")
        
    for line in iter(stderr.readline, ""):
        print(f"ERR: {line}", end="")
        
    print("\nInstallation complete. Starting the Robot...")
    # Start it in the background using nohup or systemd
    ssh.exec_command("sudo systemctl restart weed-robot")
    
    print(f"\nDashboard should be available at: http://{RPI_IP}:5000")
    ssh.close()
