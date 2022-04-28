import paramiko
from io import BytesIO


def sftp_put_file_object(
    host: str,
    username: str,
    password: str,
    local_file: BytesIO,
    remote_file: str,
    port: int = 22,
):
    transport = paramiko.Transport((host, port))
    transport.connect(username=username, password=password)
    sftp = paramiko.SFTPClient.from_transport(transport)
    sftp.putfo(local_file, remote_file)
    transport.close()
