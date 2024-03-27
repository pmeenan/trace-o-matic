#!/usr/bin/env python3
# Copyright 2024 Google Inc.
"""Trace-O-Matic Browser Build agent"""
import greenstalk
import gzip
import logging
import os
import re
import shutil
import subprocess
import threading
import time
try:
    import ujson as json
except BaseException:
    import json

class BrowserBuild(object):
    """Main builder workflow"""
    def __init__(self):
        self.path = os.path.abspath(os.path.dirname(__file__))
        self.root_path = os.path.abspath(os.path.join(self.path, os.pardir))
        self.tmp = os.path.join(self.path, "tmp")
        self.job = None
        self.last_update = time.monotonic()
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

        # Start a background thread to touch build jobs periodically
        self.thread = threading.Thread(target=self.job_watcher)

    def job_watcher(self):
        logging.debug('Background job watcher thread started')
        while True:
            time.sleep(30)
            try:
                if self.job is not None:
                    self.queue.touch(self.job)
            except Exception:
                logging.exception("Error running background job watcher")

    def get_work(self):
        result = False
        try:
            self.job = self.queue.reserve(30)
            if self.job:
                test_id = self.job.body
                logging.debug("Builkd job for %s", test_id)
                if test_id == 'latest':
                    self.test = {
                        'id': 'latest',
                        'apk': os.path.join(self.settings["apk_dir"], "latest.apk")
                        }
                    result = True
                elif re.fullmatch(r"[\w]+", test_id):
                    test_path = os.path.join(self.settings['results_dir'], test_id.replace('_', '/'))
                    with open(os.path.join(test_path, 'testinfo.json'), "rt", encoding="utf-8") as f:
                        self.test = json.load(f)
                    self.test['id'] = test_id
                    self.test['path'] = test_path
                    cl = self.test['cl'] if 'cl' in self.test else 'latest'
                    self.test['apk'] = os.path.join(self.settings["apk_dir"], cl + ".apk")
                    result = True
        except greenstalk.TimedOutError:
            pass
        except Exception:
            logging.exception("Error loading test")
        return result
    
    def set_status(self, status):
        """ Update the .building file with the build status"""
        self.last_update = time.monotonic()
        logging.debug(status)
        if self.test is not None and 'path' in self.test:
            with open(os.path.join(self.test['path'], '.building'), 'wt') as f:
                f.write(status)
        if self.job is not None and self.queue is not None:
            self.queue.touch(self.job)

    def exec(self, cmd):
        """ Run the given command, Throwing an exception if it fails """
        self.set_status(' '.join(cmd))
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=True, encoding='utf-8', cwd=self.settings['src_dir'])
        for line in iter(proc.stdout.readline, ''):
            try:
                if (time.monotonic() - self.last_update >= 30):
                    self.set_status(line.rstrip())
                else:
                    logging.debug(line.rstrip())
            except Exception:
                logging.exception('Error processing build log line %s', line.rstrip())
        proc.wait()
        if proc.returncode != 0:
            raise Exception(' '.join(cmd) + ' returned {}'.format(proc.returncode))

    def run(self):
        try:
            while(True):
                if self.get_work():
                    try:
                        self.set_status("Build started")
                        ok = False

                        shutil.rmtree(self.tmp, ignore_errors=True)
                        os.mkdir(self.tmp)

                        # Capture a debug log along with the test
                        if 'path' in self.test:
                            log_file = os.path.join(self.tmp, 'build.log')
                            log_handler = logging.FileHandler(log_file)
                            log_handler.setFormatter(self.log_formatter)
                            logging.getLogger().addHandler(log_handler)

                        # Build Chromium
                        try:
                            logging.debug('Building in %s', self.settings['src_dir'])
                            self.exec(['git', 'checkout', 'origin/main'])
                            if 'cl' not in self.test:
                                # Update the "latest" build
                                self.exec(['git', 'pull', 'origin', 'main'])
                                self.exec(['gclient', 'sync', '-D'])
                            self.exec(['git', 'checkout', 'mods'])
                            self.exec(['git', 'rebase', 'origin/main'])
                            try:
                                self.exec(['git', 'branch', '-D', 'build'])
                            except Exception:
                                 pass
                            self.exec(['git', 'checkout', '-b', 'build'])
                            self.exec(['autoninja', '-C', 'out/Default', 'chrome_public_apk'])
                            self.exec(['git', 'checkout', 'origin/main'])
                            self.exec(['git', 'branch', '-D', 'build'])
                            shutil.copy2(os.path.join(self.settings['src_dir'], '/out/Default/apks/ChromePublic.apk'), self.test['apk'])
                            ok = True
                        except subprocess.CalledProcessError as e:
                            logging.exception("Error %d building: %s", e.returncode, e.cmd)
                        except Exception:
                            logging.exception("Error building")

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
                        if ok and self.test['id'] != 'latest':
                            self.queue.put(self.test['id'])

                        self.queue.delete(self.job)
                        logging.debug("Build complete")

                        if not ok and 'path' in self.test:
                            error = 'Build error'
                            with open(os.path.join(self.test['path'], '.error'), 'wt', encoding='utf-8') as f:
                                f.write(error)
                            building_file = os.path.join(self.test['path'], '.building')
                            if os.path.exists(building_file):
                                os.remove(building_file)
                    except Exception:
                        logging.exception("Unhandled exception running test")
        except Exception:
            logging.exception("Unhandled exception")
        self.cleanup()

def main():
    """Startup and initialization"""
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s.%(msecs)03d - %(message)s", datefmt="%H:%M:%S")
    agent = BrowserBuild()
    agent.run()

if __name__ == '__main__':
    main()
    # Force a hard exit so unclean threads can't hang the agent
    os._exit(0)
