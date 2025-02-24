#
# CLI interactions with the chiadog script.
#

import datetime
import os
import psutil
import signal
import shutil
import sqlite3
import time
import traceback
import yaml

from flask import Flask, jsonify, abort, request, flash, g
from subprocess import Popen, TimeoutExpired, PIPE

from api.models import chiadog
from api import app

def load_config(blockchain):
    return open('/root/.chia/{0}dog/config.yaml'.format(blockchain),'r').read()

def save_config(config, blockchain):
    try:
        # Validate the YAML first
        yaml.safe_load(config)
        # Save a copy of the old config file
        src='/root/.chia/{0}dog/config.yaml'.format(blockchain)
        dst='/root/.chia/{0}dog/config.yaml'.format(blockchain)+time.strftime("%Y%m%d-%H%M%S")+".yaml"
        shutil.copy(src,dst)
        # Now save the new contents to main config file
        with open(src, 'w') as writer:
            writer.write(config)
    except Exception as ex:
        app.logger.info(traceback.format_exc())
        raise Exception('Updated config.yaml failed validation!\n' + str(ex))
    else:
        if get_chiadog_pid(blockchain):
            stop_chiadog(blockchain)
            start_chiadog(blockchain)

def get_chiadog_pid(blockchain):
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        if proc.info['name'] == 'python3' and '/root/.chia/{0}dog/config.yaml'.format(blockchain) in proc.info['cmdline']:
            return proc.info['pid']
    return None

def get_notifications(since):
    return chiadog.Notification.query.filter(chiadog.Notification.created_at >= since). \
        order_by(chiadog.Notification.created_at.desc()).limit(20).all()

def dispatch_action(job):
    service = job['service']
    if service != 'monitoring':
        raise Exception("Only monitoring jobs handled here!")
    action = job['action']
    if action == "start":
        start_chiadog()
    elif action == "stop":
        stop_chiadog()
    elif action == "restart":
        stop_chiadog()
        time.sleep(5)
        start_chiadog()
    else:
        raise Exception("Unsupported action {0} for monitoring.".format(action))

def start_chiadog():
    #app.logger.info("Starting monitoring....")
    blockchains = [ b.strip() for b in os.environ['blockchains'].split(',') ]
    for blockchain in blockchains:
        try:
            workdir = "/{0}dog".format(blockchain)
            configfile = "/root/.chia/{0}dog/config.yaml".format(blockchain)
            logfile = "/root/.chia/{0}dog/logs/{0}dog.log".format(blockchain)
            proc = Popen("nohup /{0}-blockchain/venv/bin/python3 -u main.py --config {1} >> {2} 2>&1 &".format(blockchain, configfile, logfile), \
                shell=True, universal_newlines=True, stdout=None, stderr=None, cwd="/{0}dog".format(blockchain))
        except:
            app.logger.info('Failed to start monitoring!')
            app.logger.info(traceback.format_exc())

def stop_chiadog():
    #app.logger.info("Stopping monitoring....")
    blockchains = [ b.strip() for b in os.environ['blockchains'].split(',') ]
    for blockchain in blockchains:
        try:
            os.kill(get_chiadog_pid(blockchain), signal.SIGTERM)
        except:
            app.logger.info('Failed to stop monitoring!')
            app.logger.info(traceback.format_exc())
