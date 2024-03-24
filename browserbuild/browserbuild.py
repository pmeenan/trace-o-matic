#!/usr/bin/env python3
# Copyright 2024 Google Inc.
"""Trace-O-Matic Browser Test agent"""
import greenstalk
import gzip
import hashlib
import logging
import os
import re
import shutil
import subprocess
import time
from time import monotonic
try:
    import ujson as json
except BaseException:
    import json

class BrowserBuild(object):
    """Main builder workflow"""
    def __init__(self, options):
        self.options = options
        self.path = os.path.abspath(os.path.dirname(__file__))
        self.root_path = os.path.abspath(os.path.join(self.path, os.pardir))
        self.tmp = os.path.join(self.path, "tmp")
        self.job = None
        self.log_formatter = logging.Formatter(fmt="%(asctime)s.%(msecs)03d - %(message)s",
                                               datefmt="%H:%M:%S")

        # Load the settings
        self.settings = {}
        with open(os.path.join(self.root_path, 'settings.json'), "rt", encoding="utf-8") as f_settings:
            self.settings = json.load(f_settings)

        # Connect to beanstalk
        self.queue = greenstalk.Client(('127.0.0.1', 11300))
        self.queue.watch('build')
        self.queue.use('test')

    def get_work(self):
        result = False
        error = None
        try:
            self.job = self.queue.reserve()
            if self.job:
                test_id = self.job.body
                if test_id == 'latest':
                    self.test = {
                        'id': 'latest',
                        'apk': os.path.join(self.settings["apk_dir"], "latest.apk")
                        }
                elif re.fullmatch(r"[\w]+", test_id):
                    test_path = os.path.join(self.settings['results_dir'], test_id.replace('_', '/'))
                    with open(os.path.join(test_path, 'testinfo.json'), "rt", encoding="utf-8") as f:
                        self.test = json.load(f)
                    self.test['id'] = test_id
                    self.test['path'] = test_path
                    cl = self.test['cl'] if 'cl' in self.test else 'latest'
                    self.test['apk'] = os.path.join(self.settings["apk_dir"], cl + ".apk")
                    result = True
        except Exception:
            logging.exception("Error loading test")
        return result
    
    def set_status(self, status):
        """ Update the .building file with the build status"""
        if self.test is not None and 'path' in self.test:
            logging.debug(status)
            with open(os.path.join(self.test['path'], '.building'), 'wt') as f:
                f.write(status)
            if (self.job is not None):
                self.queue.touch(self.job)

    def run(self):
        try:
            while(True):
                if self.get_work():
                    try:
                        self.set_status("Build started")

                        shutil.rmtree(self.tmp, ignore_errors=True)
                        os.mkdir(self.tmp)

                        # Capture a debug log along with the test
                        if 'path' in self.test:
                            log_file = os.path.join(self.tmp, 'build.log')
                            log_handler = logging.FileHandler(log_file)
                            log_handler.setFormatter(self.log_formatter)
                            logging.getLogger().addHandler(log_handler)

                        # TODO build

                        # Turn off the logging
                        if 'path' in self.test:
                            try:
                                log_handler.close()
                                logging.getLogger().removeHandler(log_handler)
                                with open(log_file, 'rb') as f_in:
                                    with gzip.open(log_file + '.gz', 'wb') as f_out:
                                        shutil.copyfileobj(f_in, f_out)
                                os.remove(log_file)
                            except Exception:
                                pass

                            # Move the build log to the results directory
                            logging.debug("Uploading build log")
                            files = os.listdir(self.tmp)
                            for file in files:
                                logging.debug("Uploading %s...", file)
                                shutil.move(os.path.join(self.tmp, file), self.test['path'])

                        # send the test to the testing queue
                        if self.test['id'] != 'latest':
                            self.queue.put(self.test['id'])

                        self.queue.delete(self.job)
                        logging.debug("Test complete")
                    except Exception:
                        logging.exception("Unhandled exception running test")
        except Exception:
            logging.exception("Unhandled exception")
        self.cleanup()

def main():
    """Startup and initialization"""
    import argparse
    parser = argparse.ArgumentParser(description='Trace-O-Matic Browser Test agent.', prog='browsertest')
    parser.add_argument('-v', '--verbose', action='count',
                        help="Increase verbosity (specify multiple times for more)."
                        " -vvvv for full debug output.")
    options, _ = parser.parse_known_args()

    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s.%(msecs)03d - %(message)s", datefmt="%H:%M:%S")
    agent = BrowserBuild(options)
    agent.run()

if __name__ == '__main__':
    main()
    # Force a hard exit so unclean threads can't hang the agent
    os._exit(0)
