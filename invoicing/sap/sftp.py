import paramiko
from typing import BinaryIO


def sftp_put_file_object(
    host: str,
    username: str,
    password: str,
    local_file: BinaryIO,
    remote_file: str,
    port: int = 22,
):
    transport = paramiko.Transport((host, port))
    transport.connect(username=username, password=password)
    sftp = paramiko.SFTPClient.from_transport(transport)
    sftp.putfo(local_file, remote_file)
    transport.close()
