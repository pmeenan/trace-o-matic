#!/usr/bin/env python3
# Copyright 2024 Google Inc.
"""Trace-O-Matic Browser Test agent"""
import adb
import hashlib
import logging
import os
import time
try:
    import ujson as json
except BaseException:
    import json

class BrowserTest(object):
    """Main agent workflow"""
    def __init__(self, options):
        self.options = options
        self.PACKAGE = "org.chromium.chrome"
        self.ACTIVITY = "com.google.android.apps.chrome.Main"
        self.adb = adb.Adb(options)
        self.path = os.path.abspath(os.path.dirname(__file__))
        self.root_path = os.path.abspath(os.path.join(self.path, os.pardir))
        self.apk = None
        self.url = None
        self.runs = 0
        self.current_run = 0
        # Load the status from the last run
        self.status = {}
        self.status_file = os.path.join(self.root_path, 'status')
        if self.options.device is not None:
            self.status_file += self.options.device
        self.status_file += ".json"
        if os.path.exists(self.status_file):
            with open(self.status_file, "rt", encoding="utf-8") as f_status:
                self.status = json.load(f_status)

        # Load the settings
        self.settings = {}
        with open(os.path.join(self.root_path, 'settings.json'), "rt", encoding="utf-8") as f_settings:
            self.settings = json.load(f_settings)

    def cleanup(self):
        with open(self.status_file, "wt", encoding="utf-8") as f_status:
            json.dump(self.status, f_status)
    
    def wait_for_device_ready(self):
        while not self.adb.is_device_ready():
            time.sleep(1)
    
    def get_work(self):
        self.apk = os.path.join(self.settings["apk_dir"], "latest.apk")
        self.runs = 1
        self.current_run = 0
        self.url = "https://www.google.com/search?q=flowers"
        return True
    
    def hash_file(self, file_path):
        out = None
        BUF_SIZE = 65536
        sha256 = hashlib.sha256()
        with open(file_path, "rb") as f_in:
            while True:
                data = f_in.read(BUF_SIZE)
                if not data:
                    break
                sha256.update(data)
            out = sha256.hexdigest()
        return out

    def navigate(self, url):
        # Navigate the Chromium browser to the provided URL
        activity = '{0}/{1}'.format(self.PACKAGE, self.ACTIVITY)
        return self.adb.shell(['am', 'start', '-n', activity, '-a', 'android.intent.action.VIEW', '-d', url])

    def run_test(self):
        logging.debug("Running test run # %d", self.current_run)
        # clear browser profile/cache
        self.adb.shell(['am', 'force-stop', self.PACKAGE])

        # Launch browser to https://trace-o-matic.com/blank.html
        self.navigate("https://trace-o-matic.com/blank.html")
        time.sleep(10)

        # Wait for network idle(ish)
        # Start video capture (and wait)
        # start perfetto capture

        # Navigate to test page
        self.navigate(self.url)
        time.sleep(10)
        # Wait for video-based completion
        # stop perfetto capture
        # stop video capture
        # close the browser
        self.adb.shell(['am', 'force-stop', self.PACKAGE])
        # Pull perfetto file
        # Pull video file

    def run(self):
        try:
            # Prepare device
            self.wait_for_device_ready()
            # Install browser
            if self.get_work():
                self.adb.cleanup_device()
                apk_hash = self.hash_file(self.apk)
                if apk_hash is not None:
                    if 'last_apk' not in self.status or self.status['last_apk'] != apk_hash:
                        logging.info("Installing browser apk %s (hash %s)...", self.apk, apk_hash)
                        if self.adb.adb(["install", self.apk]):
                            self.status['last_apk'] = apk_hash
                    else:
                        logging.debug("Browser APK unchanged")

                # run the tests
                for self.current_run in range(1, self.runs + 1):
                    self.run_test()
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
    parser.add_argument('--device',
                        help="Device ID (only needed if more than one android device attached).")
    parser.add_argument('--temperature', type=int, default=36,
                        help="set custom temperature treshold for device as int")
    options, _ = parser.parse_known_args()

    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s.%(msecs)03d - %(message)s", datefmt="%H:%M:%S")
    agent = BrowserTest(options)
    agent.run()

if __name__ == '__main__':
    main()
    # Force a hard exit so unclean threads can't hang the agent
    os._exit(0)
