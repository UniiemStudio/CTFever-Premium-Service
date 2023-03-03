import asyncio
import logging
import os
import sys
from time import sleep

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi import Form
from pydantic import BaseModel
from pydantic.fields import Any, Union, Json

from core import PluginManager

app = FastAPI()

os.path.exists('log') or os.mkdir('log')

formatter = logging.Formatter(f'%(levelname)0.7s\t  %(asctime)0.19s\t  [%(name)s] %(message)s')
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setLevel(logging.INFO)
console_handler.setFormatter(formatter)
file_handler = logging.FileHandler('log/runtime.log', encoding='UTF-8')
file_handler.setLevel(logging.INFO)
file_handler.setFormatter(formatter)
logging.basicConfig(level=logging.INFO, handlers=[console_handler, file_handler], encoding='UTF-8')
logger = logging.getLogger('core')

logger.info('initializing plugin manager')
plugin_manager = PluginManager('plugins')


@app.get("/")
async def root():
    return {"message": "Hello World"}


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
        args: Union[Json, None] = Form(None)
):
    try:
        logger.info(f'arg type: {type(args)}')
        ret = await plugin_manager.call_plugin_method(plugin_name, method, args)
    except Exception as e:
        logger.error(e)
        raise HTTPException(500, str(e))
    return ret


if __name__ == '__main__':
    plugin_manager.load_plugins()
    plugin_manager.activate_plugins()
    logger.info('starting server')
    sleep(0.5)
    uvicorn.run(
        app,
        host='127.0.0.1', port=8080,
        log_config={'version': 1, 'disable_existing_loggers': False}
    )
