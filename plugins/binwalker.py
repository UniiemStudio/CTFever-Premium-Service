import asyncio
import hashlib
import os
import shutil
import subprocess
from typing import List

import binwalk
from fastapi import HTTPException, UploadFile
from starlette.background import BackgroundTasks
from starlette.responses import FileResponse

from core import Plugin


def random_string(size):
    import random
    import string
    return ''.join(random.choice(string.ascii_letters + string.digits) for _ in range(size))


class Binwalker(Plugin):

    def load(self):
        self.fetch_data_package(
            'https://file.i0x0i.ltd/api/v3/file/source/810/binwalk-2.3.2.zip'
            '?sign=iKwXgbeUxOL0EVzei5b4TwbIi7X_revgtNM1Up4g3cg%3D%3A0'
        )
        # setup_path = os.path.join(self.data_dir(), 'binwalk-2.3.2', 'setup.py')
        setup_path = os.path.join(self.data_dir(), 'binwalk-2.3.2')
        if not os.path.exists(setup_path):
            raise FileNotFoundError('setup.py not found')

        async def do_install():
            process = await asyncio.create_subprocess_exec(
                # 'python', setup_path, 'install',
                'pip', 'install', setup_path,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT
            )
            stdout, stderr = await process.communicate()
            return process.returncode, stdout, stderr

        code, std_out, std_err = asyncio.run(do_install())
        output = std_out.decode(
            encoding=('gbk' if os.name == 'nt' else 'utf-8'),
            errors='replace'
        )
        if code != 0:
            raise RuntimeError(f'Install binwalk failed: {output}')
        self.logger.info(f'binwalk has been installed successfully')

    def unload(self):
        pass

    def activate(self):
        super().activate()

    def __getmethods__(self, exclude: List[str] = None):
        return super().__getmethods__(['do_scan'])

    async def do_scan(self, path):
        artifact_id = hashlib.md5(path.encode('utf-8')).hexdigest()
        artifacts = []
        signature_list: list = []
        scan_result = await asyncio.to_thread(binwalk.scan, path, signature=True, extract=True, quiet=True)
        for module in scan_result:
            for result in module.results:
                result_for_resp = result
                result_for_resp.file.name = os.path.basename(result.file.name)
                signature_list.append(result_for_resp)
                self.logger.info("[BinWalk] [%s] at 0x%.8X\t%s" % (result.file.name.split('/')[-1],
                                                                   result.offset,
                                                                   result.description))
                if result.file.path in module.extractor.output:
                    origin_basename, origin_ext = os.path.splitext(os.path.basename(result.file.name))
                    # Carved
                    if result.offset in module.extractor.output[result.file.path].carved:
                        try:
                            carved_path = module.extractor.output[result.file.path].carved[result.offset]
                            os.path.exists(os.path.join(
                                self._temp_dir,
                                'artifacts',
                                # f'{origin_basename}{origin_ext}'
                                f'{artifact_id}'
                            )) or os.makedirs(os.path.join(
                                self._temp_dir,
                                'artifacts',
                                # f'{origin_basename}{origin_ext}'
                                f'{artifact_id}'
                            ))
                            carved_moved_dst, carved_moved_filename = os.path.split(shutil.move(
                                carved_path,
                                os.path.join(
                                    self._temp_dir,
                                    'artifacts',
                                    # f'{origin_basename}{origin_ext}',
                                    f'{artifact_id}',
                                    f'{os.path.basename(carved_path)}'
                                )
                            ))
                            artifacts.append(f'{carved_moved_filename}')
                            self.logger.info("[BinWalk] [%s] at 0x%.8X\t- CARVE >> '%s'" % (
                                result.file.name.split('/')[-1],
                                result.offset,
                                carved_path))
                        except Exception as e:
                            raise e
                    # Extracted
                    if result.offset in module.extractor.output[result.file.path].extracted:
                        try:
                            self.logger.info("[BinWalk] [%s] at 0x%.8X\t- EXTRACT %d files >> '%s'" % (
                                result.file.name.split('/')[-1],
                                result.offset,
                                len(module.extractor.output[result.file.path].extracted[result.offset].files),
                                module.extractor.output[result.file.path].extracted[result.offset].files[0]))
                            for extracted_file in module.extractor.output[
                                result.file.path
                            ].extracted[result.offset].files:
                                extracted_file_basename = os.path.basename(extracted_file)
                                artifacts.append(extracted_file_basename)
                                shutil.move(
                                    extracted_file,
                                    os.path.join(
                                        self._temp_dir,
                                        'artifacts',
                                        # f'{origin_basename}{origin_ext}',
                                        f'{artifact_id}',
                                        f'{extracted_file_basename}'
                                    )
                                )
                            shutil.rmtree(os.path.join(
                                self._temp_dir,
                                f'_{origin_basename}{origin_ext}.extracted'
                            ))
                            os.remove(os.path.join(
                                self._temp_dir,
                                f'{origin_basename}{origin_ext}'
                            ))
                        except Exception:
                            pass
        return {
            'available': True,
            'meta': {
                'filename': os.path.basename(signature_list[0].file.name),
                'size': signature_list[0].file.size
            },
            'signature': signature_list,
            'artifact_id': artifact_id,
            'artifacts': artifacts,
            # 'files': []
        } if len(signature_list) > 0 else {
            'available': False,
            'meta': {
                'filename': None,
                'size': None
            },
            'signature': [],
            'artifacts': None,
        }

    async def scan(self, params):
        file: UploadFile = params.get('file', None)
        if not file:
            raise HTTPException(status_code=400, detail='file is required')
        if file.filename == '':
            raise HTTPException(status_code=400, detail='file is required')
        save_path, save_dir = await self.save_upload_file_as_temporary(file)
        scan_result = await asyncio.create_task(self.do_scan(save_path))
        ret = []
        for result in scan_result['signature']:
            ret.append({
                'file': result.file.name.split('/')[-1],
                'offset': result.offset,
                'description': result.description
            })
        return {
            'available': scan_result['available'],
            'meta': scan_result['meta'] if scan_result['available'] else None,
            'signature': ret if scan_result['available'] else None,
            'downloads': {
                'artifact_id': scan_result['artifact_id'] if scan_result['available'] else None,
                'artifacts': scan_result['artifacts'] if scan_result['available'] else None,
            }
        }

    def del_file(self, path):
        self.logger.info(f'Delete file: {path}')
        if os.path.isfile(path):
            os.remove(path)

    def artifact(self, params):
        filename = params.get('filename', None)
        artifact_id = params.get('artifact_id', '')
        if not filename:
            raise HTTPException(status_code=400, detail='filename is required')
        if filename == '':
            raise HTTPException(status_code=400, detail='filename is required')
        filepath = os.path.join(self._temp_dir, 'artifacts', artifact_id, filename)
        if os.path.isfile(filepath):
            resp = FileResponse(
                path=filepath,
                filename=filename
            )
            task = BackgroundTasks()
            task.add_task(self.del_file, filepath)
            return resp
        else:
            raise HTTPException(403, detail='File you required does not exists.')
