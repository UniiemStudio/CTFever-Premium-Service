import logging
import os
import sys
from time import sleep

import uvicorn
from fastapi import FastAPI
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


@app.get("/")
async def root():
    return {"message": "Hello World"}


@app.get("/hello/{name}")
async def say_hello(name: str):
    return {"message": f"Hello {name}"}


if __name__ == '__main__':
    logger.info('initializing plugin manager')
    plugin_manager = PluginManager('plugins')
    plugin_manager.load_plugins()
    plugin_manager.activate_plugins()
    logger.info('starting server')
    sleep(0.5)
    uvicorn.run(app, host='127.0.0.1', port=8080, log_config={'version': 1, 'disable_existing_loggers': False})
