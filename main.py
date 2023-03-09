import asyncio
import inspect
import logging
import os
import sys
import time
from time import sleep

import uvicorn
from fastapi import FastAPI, HTTPException, UploadFile, status
from fastapi import Form
from pydantic.fields import Union, Json

from core import PluginManager

app = FastAPI()

os.path.exists('log') or os.mkdir('log')
os.path.exists('data') or os.mkdir('data')

formatter = logging.Formatter(f'%(levelname)0.7s\t  %(asctime)0.19s\t  [%(name)s] %(message)s')
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setLevel(logging.INFO)
console_handler.setFormatter(formatter)
file_handler = logging.FileHandler('log/runtime.log', encoding='UTF-8')
file_handler.setLevel(logging.INFO)
file_handler.setFormatter(formatter)
logging.basicConfig(level=logging.INFO, handlers=[console_handler, file_handler], encoding='UTF-8')
logger = logging.getLogger('core')

logger.info(f'running on {sys.platform}[{os.name.upper()} Kernel](python {sys.version}, pid: {os.getpid()})')

logger.info('initializing plugin manager')
plugin_manager = PluginManager('plugins')


@app.get("/")
async def root():
    return {"message": "CTFever Backend Service"}


@app.get("/available-futures")
async def get_plugins():
    ret = []
    for plugin_name, plugin in plugin_manager.plugins.items():
        ret.append({
            'name': plugin_name,
            'methods': plugin.__getmethods__()
        })
    return {
        "plugins": ret
    }


@app.post("/call/{plugin_name}")
async def plugin_call(
        plugin_name: str,
        method: str,
        args: Union[Json, None] = Form(None),
        file: Union[UploadFile, None] = Form(None)
):
    if plugin_name not in plugin_manager.plugins:
        raise HTTPException(status.HTTP_404_NOT_FOUND, 'plugin not found')
    t1 = time.time()
    try:
        # logger.info(f'arg type: {type(args)}')
        if not args:
            args = {}
        if file:
            args['file'] = file
        validater = plugin_manager.plugins[plugin_name].params_validater
        if inspect.iscoroutinefunction(validater):
            validate = await validater(args)
        else:
            validate = validater(args)
        if validate is not False:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, f'params invalid: {validate}')
        ret = await plugin_manager.call_plugin_method(plugin_name, method, args)
    except HTTPException as e:
        raise e
    except Exception as e:
        # log thru plugin logger
        plugin_manager.get_plugin_logger(plugin_name).error(e, exc_info=True)
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, str(e))
    return {
        'status': 0,
        'spent': round(time.time() - t1, 3),
        'result': ret
    }


if __name__ == '__main__':
    plugin_manager.load_plugins()
    plugin_manager.activate_plugins()
    logger.info('starting server')
    sleep(0.5)
    uvicorn.run(
        app,
        workers=1,
        host='127.0.0.1', port=8080,
        log_config={'version': 1, 'disable_existing_loggers': False}
    )
