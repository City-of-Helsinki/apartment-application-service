from io import BytesIO
from typing import List, Optional

import paramiko

from apartment_application_service import settings


class SFTPConnection:
    def __init__(
        self,
        host: Optional[str] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
        port: Optional[int] = 22,
    ):
        self.host = host or settings.SAP_SFTP_HOST
        self.username = username or settings.SAP_SFTP_USERNAME
        self.password = password or settings.SAP_SFTP_PASSWORD
        self.port = port or settings.SAP_SFTP_PORT

    def __enter__(self):
        self.transport = paramiko.Transport((self.host, self.port))
        self.transport.connect(username=self.username, password=self.password)
        self.sftp = paramiko.SFTPClient.from_transport(self.transport)
        return self

    def __exit__(self, *args):
        self.transport.close()

    def get_filenames(self) -> List[str]:
        return self.sftp.listdir()

    def get_file(self, filename: str) -> str:
        local_file = BytesIO()
        self.sftp.getfo(filename, local_file)
        local_file.seek(0)
        return local_file.read().decode("utf-8")

    def rename_file(self, old_filename: str, new_filename: str) -> None:
        self.sftp.rename(old_filename, new_filename)
