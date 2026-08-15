import paramiko

client = paramiko.SSHClient()
client.load_system_host_keys()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('weedfinder.local', 22, 'rpi', 'rpi')

stdin, stdout, stderr = client.exec_command('sudo journalctl -u weed-robot -n 50 --no-pager')
out = stdout.read().decode()

with open('rpi_logs.txt', 'w') as f:
    f.write(out)

client.close()
