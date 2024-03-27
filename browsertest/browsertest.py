#!/usr/bin/env python3
# Copyright 2024 Google Inc.
"""Trace-O-Matic Browser Test agent"""
import adb
import greenstalk
import gzip
import hashlib
import logging
import os
import re
import shutil
import signal
import subprocess
import time
from time import monotonic
try:
    import ujson as json
except BaseException:
    import json

CHROME_COMMAND_LINE_OPTIONS = [
    '--no-default-browser-check',
    '--no-first-run',
    '--disable-background-downloads',
    '--disable-external-intent-requests',
    '--disable-fre',
]

DISABLE_CHROME_FEATURES = [
    'AutofillServerCommunication',
    'CalculateNativeWinOcclusion',
    'HeavyAdPrivacyMitigations',
    'InterestFeedContentSuggestions',
    'MediaRouter',
    'OfflinePagesPrefetching',
    'OptimizationHints',
    'Translate',
]

ENABLE_CHROME_FEATURES = [
    "EnablePerfettoSystemTracing",
]

ENABLE_BLINK_FEATURES = [
]

COMMAND_LINE_PATH = '/data/local/tmp/chrome-command-line'
POLICY_PATH = "/data/local/tmp/policies/recommended/policies.json"

TRACE_CATEGORIES = [
    "blink",
    "blink.console",
    "blink.net",
    "blink.resource",
    "blink.user_timing",
    "browser",
    "devtools",
    "devtools.timeline",
    "ipc",
    "loading",
    "mojom",
    "navigation",
    "net",
    "netlog",
    "rail",
    "resources",
    "scheduler",
    "sequence_manager",
    "toplevel",
    "toplevel.flow",
    "v8",
    "v8.execute",
    "disabled-by-default-devtools.screenshot",
    "disabled-by-default-ipc.flow",
    "disabled-by-default-net",
    "disabled-by-default-network",
    "disabled-by-default-toplevel.flow",
]

class BrowserTest(object):
    """Main agent workflow"""
    def __init__(self, options):
        self.options = options
        self.PACKAGE = "org.chromium.chrome"
        self.ACTIVITY = "com.google.android.apps.chrome.Main"
        self.TIME_LIMIT = 120
        self.adb = adb.Adb(options)
        self.path = os.path.abspath(os.path.dirname(__file__))
        self.root_path = os.path.abspath(os.path.join(self.path, os.pardir))
        self.tmp = os.path.join(self.path, "tmp")
        if self.options.device is not None:
            self.tmp += self.options.device
        self.test = None
        self.job = None
        self.current_run = 0
        self.log_formatter = logging.Formatter(fmt="%(asctime)s.%(msecs)03d - %(message)s",
                                               datefmt="%H:%M:%S")
        self.must_exit = False
        """
        signal.signal(signal.SIGTERM, self.signal_handler)
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGHUP, self.signal_handler)
        """

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

        # Connect to beanstalk
        self.queue = greenstalk.Client(('127.0.0.1', 11300))
        self.queue.watch('test')

    def signal_handler(self, signum, frame):
        """Ctrl+C handler"""
        try:
            if not self.must_exit:
                logging.info("Exiting...")
                self.must_exit = True
            else:
                logging.info("Waiting for graceful exit...")
        except Exception as e:
            logging.exception("Error in signal handler")

    def cleanup(self):
        with open(self.status_file, "wt", encoding="utf-8") as f_status:
            json.dump(self.status, f_status)
    
    def wait_for_device_ready(self):
        while not self.adb.is_device_ready():
            time.sleep(1)

    def reset_shaper(self):
        """ Remove any tc config on a remote traffic-shaping bridge """
        if ('shaper' in self.settings):
            cmd = ['ssh', self.settings['shaper'], 'sudo tc qdisc del dev wlan0 root']
            logging.debug('%s', ' '.join(cmd))
            subprocess.call(cmd)

    def configure_shaper(self):
        if ('shaper' in self.settings and 'latency' in self.test and self.test['latency'] > 0):
            cmd = ['ssh', self.settings['shaper'], 'sudo tc qdisc add dev wlan0 root netem delay {}ms'.format(self.test['latency'])]
            logging.debug('%s', ' '.join(cmd))
            subprocess.call(cmd)
    
    def get_work(self):
        result = False
        error = None
        try:
            self.job = self.queue.reserve(30)
            if self.job:
                test_id = self.job.body
                if re.fullmatch(r"[\w]+", test_id):
                    test_path = os.path.join(self.settings['results_dir'], test_id.replace('_', '/'))
                    with open(os.path.join(test_path, 'testinfo.json'), "rt", encoding="utf-8") as f:
                        self.test = json.load(f)
                    self.test['id'] = test_id
                    self.test['path'] = test_path
                    cl = self.test['cl'] if 'cl' in self.test else 'latest'
                    self.test['apk'] = os.path.join(self.settings["apk_dir"], cl + ".apk")
                    if not os.path.exists(self.test['apk']):
                        error = "Browser apk not available"
                        self.set_status(error)
                    self.current_run = 0
                    self.test['clear'] = bool('clear' in self.test and self.test['clear'])
                    self.test['video'] = bool('video' in self.test and self.test['video'])
                    self.test['cpu'] = bool('cpu' in self.test and self.test['cpu'])
                    if 'categories' not in self.test:
                        self.test['categories'] = TRACE_CATEGORIES
                    self.test['categories'].append("__metadata")
                    if 'url' in self.test and 'runs' in self.test and error is None:
                        result = True
        except greenstalk.TimedOutError:
            pass
        except Exception:
            logging.exception("Error loading test")
        return result
    
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
        return self.adb.shell(['am', 'start', '-n', activity,
                               '-a', 'android.intent.action.VIEW',
                               '-d', url,
                               '--es', 'com.android.browser.application_id', 'com.android.browser'])
    
    def wait_for_network_idle(self, timeout=60, threshold=10000):
        """Wait for 5 one-second intervals that receive less than 10KB/sec"""
        logging.debug('Waiting for network idle')
        end_time = monotonic() + timeout
        self.adb.get_bytes_rx()
        idle_count = 0
        while idle_count < 5 and monotonic() < end_time:
            time.sleep(1)
            bytes_rx = self.adb.get_bytes_rx()
            logging.debug("Bytes received: %d", bytes_rx)
            if bytes_rx > threshold:
                idle_count = 0
            else:
                idle_count += 1
            if (self.job is not None):
                self.queue.touch(self.job)

    def wait_for_page_load(self):
        """Once the video starts growing, wait for it to stop"""
        logging.debug('Waiting for the page to load')
        # Wait for the video to start (up to 30 seconds)
        end_startup = monotonic() + 30
        end_time = monotonic() + self.TIME_LIMIT
        last_size = self.adb.get_video_size()
        video_started = False
        bytes_rx = self.adb.get_bytes_rx()
        while not video_started and monotonic() < end_startup:
            time.sleep(5)
            video_size = self.adb.get_video_size()
            bytes_rx = self.adb.get_bytes_rx()
            delta = video_size - last_size
            logging.debug('Video Size: %d bytes (+ %d)', video_size, delta)
            last_size = video_size
            if delta > 50000:
                video_started = True
            if (self.job is not None):
                self.queue.touch(self.job)
        logging.debug('Page started loading')
        # Wait for the activity to stop
        video_idle_count = 0
        while video_idle_count <= 3 and monotonic() < end_time:
            time.sleep(5)
            video_size = self.adb.get_video_size()
            bytes_rx = self.adb.get_bytes_rx()
            delta = video_size - last_size
            logging.debug('Video Size: %d bytes (+ %d) - %d bytes received',
                          video_size, delta, bytes_rx)
            last_size = video_size
            #if delta > 10000 or bytes_rx > 5000:
            if delta > 10000:
                video_idle_count = 0
            else:
                video_idle_count += 1
            if (self.job is not None):
                self.queue.touch(self.job)

    def launch_browser(self):
        """ Prepare and launch the browser """
        # Copy the policies over
        self.adb.shell(['rm', POLICY_PATH])
        self.adb.adb(['push', os.path.join(self.path, "chrome_policy.json"), COMMAND_LINE_PATH])

        # set up the Chromium command-line
        self.adb.shell(['rm', COMMAND_LINE_PATH])
        args = list(CHROME_COMMAND_LINE_OPTIONS)
        features = list(ENABLE_CHROME_FEATURES)
        disable_features = list(DISABLE_CHROME_FEATURES)
        blink_features = list(ENABLE_BLINK_FEATURES)
        if len(features):
            args.append('--enable-features=' + ','.join(features))
        if len(disable_features):
            args.append('--disable-features=' + ','.join(disable_features))
        if len(blink_features):
            args.append('--enable-blink-features=' + ','.join(blink_features))
        command_line = '_ ' + ' '.join(args)
        local_command_line = os.path.join(self.path, 'chrome-command-line')
        logging.debug(command_line)
        with open(local_command_line, 'wt', encoding="utf-8") as f_out:
            f_out.write(command_line)
        self.adb.adb(['push', local_command_line, COMMAND_LINE_PATH])
        os.remove(local_command_line)

        # Launch browser to https://trace-o-matic.com/blank.html
        self.navigate("https://trace-o-matic.com/blank.html")
        time.sleep(10)
        self.wait_for_network_idle()

    def build_perfetto_config(self, dest):
        """ Build the perfetto trace config file for the given Chrome categories """
        config_file = "trace_config_cpu.txt" if self.test['cpu'] else "trace_config.txt"
        with open(os.path.join(self.path, config_file), "rt", encoding="utf-8") as f:
            config_txt = f.read()
        config = {
            "record_mode": "record-until-full",
            "included_categories":self.test['categories'],
            "excluded_categories":["*"],
            "memory_dump_config":{}
            }
        config_json = json.dumps(json.dumps(config, separators=(',', ':')))
        categories_txt = ""
        for category in self.test['categories']:
            categories_txt += "            enabled_categories: \"{}\"\n".format(category)
        config_txt = config_txt.replace("%CONFIG_JSON%", config_json)
        config_txt = config_txt.replace("%ENABLED_CATEGORIES%", categories_txt)
        config_file = os.path.join(self.tmp, "perfetto.pbtx")
        with open(config_file, "wt", encoding="utf-8") as f:
            f.write(config_txt)
        ret = self.adb.adb(["push", config_file, dest])
        os.remove(config_file)
        return ret

    def run_test(self):
        logging.debug("Running test run # %d", self.current_run)
        if self.test['video']:
            video_file = os.path.join(self.tmp, "{:03d}-video.mp4".format(self.current_run))
        else:
            video_file = None
        trace_file = os.path.join(self.tmp, "{:03d}-trace.perfetto".format(self.current_run))
        trace_file_json = os.path.join(self.tmp, "{:03d}-trace.json".format(self.current_run))
        screenshot_file = os.path.join(self.tmp, "{:03d}-screenshot.png".format(self.current_run))

        # Clear browser profile/cache and launch the browser
        self.set_status('Preparing browser')
        if self.current_run == 1 or self.test['clear']:
            self.adb.shell(['am', 'force-stop', self.PACKAGE])
            self.adb.shell(['pm', 'clear', self.PACKAGE])
            self.launch_browser()

        # Start video capture (and wait)
        self.adb.start_screenrecord()
        # start perfetto capture
        remote_trace_config = "/data/misc/perfetto-configs/tom.pbtx"
        remote_trace_file = "/data/misc/perfetto-traces/trace"
        self.adb.shell(['rm', remote_trace_file])
        self.build_perfetto_config(remote_trace_config)
        cmd = self.adb.build_adb_command(['shell', 'perfetto', '-c', remote_trace_config, '--txt', '-o', remote_trace_file])
        perfetto = subprocess.Popen(cmd)

        # Navigate to test page
        self.set_status('Waiting for page to finish loading')
        time.sleep(2)
        self.navigate(self.test['url'])
        self.wait_for_page_load()
        self.set_status('Collecting trace data')

        # stop perfetto capture
        self.adb.shell(['killall', 'perfetto'])

        # stop video capture
        self.adb.stop_screenrecord(video_file)

        # Grab a screenshot
        self.adb.screenshot(screenshot_file)

        # Pull perfetto file
        self.adb.wait_for_process(perfetto)
        self.adb.adb(['pull', remote_trace_file, trace_file])

        # Go back to the blank page
        self.navigate("https://trace-o-matic.com/blank.html")

        # compress the trace
        logging.debug("Compressing the trace file")
        if os.path.exists(trace_file):
            with open(trace_file, 'rb') as f_in:
                with gzip.open(trace_file + '.gz', 'wb') as f_out:
                    shutil.copyfileobj(f_in, f_out)
            # create a json version of the trace
            logging.debug("Converting trace to json")
            subprocess.call(['python3', os.path.join(self.path, "tools", "traceconv"), "json", trace_file, trace_file_json])
            if os.path.exists(trace_file_json):
                with open(trace_file_json, 'rb') as f_in:
                    with gzip.open(trace_file_json + '.gz', 'wb') as f_out:
                        shutil.copyfileobj(f_in, f_out)
                os.remove(trace_file_json)
            os.remove(trace_file)

    def set_status(self, status):
        """ Update the .running file with the test status"""
        if self.test is not None and 'path' in self.test:
            status_txt = ''
            if self.current_run > 0 and 'runs' in self.test and self.test['runs'] > 1:
                status_txt = 'Run {} of {} - '.format(self.current_run, self.test['runs'])
            status_txt += status
            logging.debug(status_txt)
            with open(os.path.join(self.test['path'], '.running'), 'wt') as f:
                f.write(status_txt)
            if (self.job is not None):
                self.queue.touch(self.job)

    def run(self):
        try:
            # Prepare device
            self.wait_for_device_ready()
            self.reset_shaper()
            while(not self.must_exit):
                if self.get_work():
                    try:
                        self.current_run = 0
                        self.set_status("Test started")
                        building_file = os.path.join(self.test['path'], '.building')
                        if os.path.exists(building_file):
                            os.remove(building_file)

                        shutil.rmtree(self.tmp, ignore_errors=True)
                        os.mkdir(self.tmp)

                        # Capture a debug log along with the test
                        log_file = os.path.join(self.tmp, 'test.log')
                        log_handler = logging.FileHandler(log_file)
                        log_handler.setFormatter(self.log_formatter)
                        logging.getLogger().addHandler(log_handler)

                        logging.debug("Running test %s", self.test['id'])
                        self.adb.cleanup_device()
                        self.adb.shell(['am', 'force-stop', self.PACKAGE])
                        apk_hash = self.hash_file(self.test['apk'])
                        if apk_hash is not None:
                            if 'last_apk' not in self.status or self.status['last_apk'] != apk_hash:
                                self.set_status("Installing browser apk {} (hash {})...".format(self.test['apk'], apk_hash))
                                if self.adb.adb(["install", self.test['apk']]):
                                    self.status['last_apk'] = apk_hash
                            else:
                                logging.debug("Browser APK unchanged")

                        # Clear browser profile/cache
                        self.adb.shell(['pm', 'clear', self.PACKAGE])

                        # run the tests
                        self.configure_shaper()
                        for self.current_run in range(1, self.test['runs'] + 1):
                            self.run_test()
                        self.reset_shaper()

                        # Reset the browser state
                        self.adb.shell(['am', 'force-stop', self.PACKAGE])
                        self.adb.shell(['pm', 'clear', self.PACKAGE])

                        # Turn off the logging
                        try:
                            log_handler.close()
                            logging.getLogger().removeHandler(log_handler)
                            with open(log_file, 'rb') as f_in:
                                with gzip.open(log_file + '.gz', 'wb') as f_out:
                                    shutil.copyfileobj(f_in, f_out)
                            os.remove(log_file)
                        except Exception:
                            pass

                        # Move the test results to the results directory
                        logging.debug("Uploading test results")
                        files = os.listdir(self.tmp)
                        for file in files:
                            logging.debug("Uploading %s...", file)
                            shutil.move(os.path.join(self.tmp, file), self.test['path'])

                        # Mark the test as done
                        with open(os.path.join(self.test['path'], '.done'), 'wt') as f:
                            pass
                        running_file = os.path.join(self.test['path'], '.running')
                        if os.path.exists(running_file):
                            os.remove(running_file)
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
