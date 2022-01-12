"""
Lottery exception classes.
"""


class ApplicationTimeNotFinishedException(Exception):
    """
    Raises when the project's application time is not finished.
    """

    def __init__(
        self, msg="Project's application time is not finished.", *args, **kwargs
    ):
        super().__init__(msg, *args, **kwargs)
