import asyncio
import os
import subprocess

from fastapi import HTTPException, UploadFile

from core import Plugin


def is_zip(binary: bytes):
    flag_zip = b'PK\x03\x04'
    return binary.startswith(flag_zip)


def is_pseudo_encryption(binary: bytes):
    """
    Check if the zip file is pseudo encrypted
    :param binary:  Zip file in bytes
    :return:        1 if pseudo encrypted, 0 if true encrypted, -1 if not encrypted
    """
    flag_pseudo_base = b'PK\x01\x02'
    flag_true = b'\t\x00'
    flag_none = b'\x00\x00'

    flag_index = binary.find(flag_pseudo_base)
    if binary[6:8] == flag_none and binary[flag_index + 8:flag_index + 10] == flag_none:
        result = -1
    elif binary[6:8] == flag_true and binary[flag_index + 8:flag_index + 10] == flag_none:
        result = -1
    elif binary[6:8] == flag_none and binary[flag_index + 8:flag_index + 10] == flag_true:
        result = 1
    elif binary[6:8] == flag_true and binary[flag_index + 8:flag_index + 10] == flag_true:
        result = 0
    else:
        result = -2
    return result, [
        [int(i) for i in binary[3:11]],
        [int(i) for i in binary[flag_index + 5:flag_index + 13]],
    ]


class Ziputil(Plugin):

    def load(self):
        pass

    def unload(self):
        pass

    def activate(self):
        super().activate()

    @staticmethod
    async def pseudo_check(params):
        file: UploadFile = params.get('file', None)
        if not file:
            raise HTTPException(400, detail='No file provided')
        file_content = await file.read()
        if not is_zip(file_content):
            raise HTTPException(400, detail='Not a zip file')
        result, characteristics = is_pseudo_encryption(file_content)
        return {
            'assert': result,
            'characteristics': characteristics,
        }
