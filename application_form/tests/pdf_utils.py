import re
import subprocess
from typing import List

import pytest


def get_cleaned_pdf_texts(pdf: bytes) -> List[str]:
    result = []
    for text_line in get_pdf_text_lines(pdf):
        cleaned = re.sub(r"\s+", " ", text_line).strip()
        if cleaned:
            result.append(cleaned)
    return result


def get_pdf_text_lines(pdf: bytes) -> List[str]:
    pdftotext = "pdftotext"
    try:
        retcode = subprocess.call([pdftotext, "-v"], stdout=subprocess.DEVNULL)
    except FileNotFoundError:
        return pytest.skip("pdftotext is not available")
    if retcode != 0:
        return pytest.skip("pdftotext not functioning")

    process = subprocess.Popen(
        [pdftotext, "-layout", "-", "-"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    (stdout, stderr) = process.communicate(input=pdf)
    if process.returncode != 0:
        msg = f"pdftotext failed with code {process.returncode}: {stderr}"
        raise RuntimeError(msg)
    return stdout.decode("utf-8", errors="replace").splitlines()


def remove_pdf_id(pdf: bytes) -> bytes:
    """
    Remove the /ID entry from the PDF file.
    """
    return re.sub(rb"/ID\s+\[<[^]]+>\]", b"", pdf)
