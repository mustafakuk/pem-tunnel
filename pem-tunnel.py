import paramiko
import time
import socket
import threading
import sys

key_path = r"..\tunnel.pem"
username = sys.argv[1]
hostname = sys.argv[2]
port = int(sys.argv[3])

remote_bind_address = ('127.0.0.1', int(sys.argv[4]))
local_bind_address = (sys.argv[5], int(sys.argv[6]))

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

key = paramiko.RSAKey(filename=key_path)

print("connection ok")
try:
    client.connect(hostname=hostname, port=port, username=username, pkey=key)
    print("SSH conn OK")
except paramiko.AuthenticationException:
    print("Auth fail")
    exit(1)
except paramiko.SSHException as sshException:
    print(f"SSH connection error: {sshException}")
    exit(1)
except Exception as e:
    print(f"Connection error: {e}")
    exit(1)

transport = client.get_transport()

transport.set_keepalive(30)

def reverse_forward_tunnel(server_port, remote_host, remote_port, transport):
    class SubHandler(threading.Thread):
        def __init__(self, chan):
            super(SubHandler, self).__init__()
            self.chan = chan
            self.daemon = True

        def run(self):
            try:
                sock = socket.socket()
                sock.connect((remote_host, remote_port))
                while True:
                    from select import select
                    r, w, x = select([self.chan, sock], [], [])
                    if self.chan in r:
                        data = self.chan.recv(1024)
                        if len(data) == 0:
                            break
                        sock.sendall(data)
                    if sock in r:
                        data = sock.recv(1024)
                        if len(data) == 0:
                            break
                        self.chan.sendall(data)
            except Exception as e:
                print(f"Error hand Conn {e}")
            finally:
                self.chan.close()
                sock.close()
                print("Conn. Closed")

    try:
        transport.request_port_forward('', server_port)
        print(f"Port: {server_port} -> {remote_host}:{remote_port}")
    except Exception as e:
        print(f"Port: {e}")
        return

    while True:
        try:
            chan = transport.accept(1000)
            if chan is None:
                print("No connection, waiting...")
                continue
            print("Acc Conn")
            SubHandler(chan).start()
        except Exception as e:
            print(f"Error acc. conn.: {e}")
            break

print("SSH tunnel sett")
try:
    reverse_forward_tunnel(remote_bind_address[1], local_bind_address[0], local_bind_address[1], transport)
    print(f"Reverse SSH tunnel established: {hostname}:{remote_bind_address[1]} -> localhost:{local_bind_address[1]}")
except Exception as e:
    print(f"Reverse SSH tunnel Error: {e}")
    client.close()
    exit(1)

try:
    while True:
        time.sleep(60)
except KeyboardInterrupt:
    print("Tunel close..")

transport.cancel_port_forward(remote_bind_address[0], remote_bind_address[1])
client.close()
print("Tunnel closed.")
