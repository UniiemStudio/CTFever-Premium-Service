import asyncio
import os
import re
import subprocess
import time

from fastapi import HTTPException, UploadFile
from starlette.responses import FileResponse

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
    tag_content_block = b'\x50\x4B\x01\x02'
    tag_file_header = b'\x50\x4B\x03\x04'
    tag_file_footer = b'\x50\x4B\x05\x06'
    flag_true = b'\x09\x00'
    flag_none = b'\x00\x00'

    print([m.start() for m in re.finditer(tag_file_header, binary)])
    print([m.start() for m in re.finditer(tag_content_block, binary)])

    flag_index = binary.find(tag_content_block)
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


# 将传入的 zip 文件 bytes 转为伪加密文件
def convert2pseudo(binary: bytes, save_path: str):
    flag_index = binary.find(b'\x50\x4B\x01\x02')
    binary = binary[:6] + b'\x09\x00' + binary[8:flag_index + 8] + b'\x09\x00' + binary[flag_index + 10:]
    with open(os.path.join(save_path, f'{int(time.time())}.zip'), 'wb') as fs:
        fs.write(binary)
    return os.path.join(save_path, f'{int(time.time())}.zip')


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

    async def convert_to_pseudo(self, params):
        file: UploadFile = params.get('file', None)
        if not file:
            raise HTTPException(400, detail='No file provided')
        file_content = await file.read()
        if not is_zip(file_content):
            raise HTTPException(400, detail='Not a zip file')
        path = convert2pseudo(file_content, self._temp_dir)
        return FileResponse(
            filename=os.path.basename(path),
            path=path,
        )
