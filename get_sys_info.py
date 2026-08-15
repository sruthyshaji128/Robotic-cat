import paramiko

client = paramiko.SSHClient()
client.load_system_host_keys()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('weedfinder.local', 22, 'rpi', 'rpi')

out = ""
stdin, stdout, stderr = client.exec_command('lsusb')
out += "--- lsusb ---\n" + stdout.read().decode('utf-8', errors='replace') + stderr.read().decode('utf-8', errors='replace') + "\n"

stdin, stdout, stderr = client.exec_command('ls -l /dev/video*')
out += "--- video devices ---\n" + stdout.read().decode('utf-8', errors='replace') + stderr.read().decode('utf-8', errors='replace') + "\n"

stdin, stdout, stderr = client.exec_command('sudo journalctl -u weed-robot -n 100 --no-pager')
out += "--- logs ---\n" + stdout.read().decode('utf-8', errors='replace') + stderr.read().decode('utf-8', errors='replace') + "\n"

with open('sys_info.txt', 'w', encoding='utf-8') as f:
    f.write(out)

client.close()
