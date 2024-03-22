# Copyright 2019 WebPageTest LLC.
# Copyright 2017 Google Inc.
# Use of this source code is governed by the Apache 2.0 license that can be
# found in the LICENSE file.
"""ADB command-line interface"""
import logging
import os
import re
import subprocess
from threading import Timer
from time import monotonic

# cSpell:ignore vpndialogs, sysctl, iptables, ifconfig, dstaddr, clientidbase, nsecs

class Adb(object):
    """ADB command-line interface"""
    def __init__(self, options):
        self.options = options
        self.device = options.device
        self.screenrecord = None
        self.version = None
        self.kernel = None
        self.short_version = None
        self.last_bytes_rx = 0
        self.initialized = False
        self.this_path = os.path.abspath(os.path.dirname(__file__))
        self.root_path = os.path.abspath(os.path.join(self.this_path, os.pardir))
        self.known_apps = {
            'com.motorola.ccc.ota': {},
            'com.google.android.apps.docs': {},
            'com.samsung.android.MtpApplication': {}
        }
        self.exe = 'adb'

    def run(self, cmd, timeout_sec=60, silent=False):
        """Run a shell command with a time limit and get the output"""
        if not silent:
            logging.debug(' '.join(cmd))
        result = subprocess.run(cmd, timeout=timeout_sec, encoding="utf-8", capture_output=True)
        out = None
        if result is not None:
            out = result.stdout
            if not silent and len(out):
                logging.debug(out[:100].strip())
        return out

    def wait_for_process(self, proc, timeout_sec=10, silent=False):
        """Wait for the given process to exit gracefully and return the result"""
        stdout = None
        kill_proc = lambda p: p.kill()
        timer = Timer(timeout_sec, kill_proc, [proc])
        try:
            timer.start()
            stdout, _ = proc.communicate()
            if not silent and stdout is not None and len(stdout):
                logging.debug(stdout[:100].strip())
        except Exception:
            logging.debug('Error waiting for process to exit')
        finally:
            if timer is not None:
                timer.cancel()
        return stdout

    def build_adb_command(self, args):
        """Build an adb command with the (optional) device ID"""
        cmd = [self.exe]
        if self.device is not None:
            cmd.extend(['-s', self.device])
        cmd.extend(args)
        return cmd

    def shell(self, args, timeout_sec=60, silent=False):
        """Run an adb shell command"""
        cmd = self.build_adb_command(['shell'])
        cmd.extend(args)
        return self.run(cmd, timeout_sec, silent)

    def adb(self, args, silent=False):
        """Run an arbitrary adb command"""
        cmd = self.build_adb_command(args)
        if not silent:
            logging.debug(' '.join(cmd))
        proc = subprocess.run(cmd, timeout=120, encoding="utf-8", capture_output=True)
        out = None
        if proc is not None:
            out = proc.stdout
            if not silent:
                logging.debug(out[:100].strip())
        return bool(proc.returncode is not None and proc.returncode == 0)

    def kill_proc(self, procname, kill_signal='-SIGINT'):
        """Kill all processes with the given name"""
        out = self.shell(['ps', '|', 'grep', procname])
        if out is not None:
            for line in out.splitlines():
                match = re.search(r'^\s*[^\s]+\s+(\d+)', line)
                if match:
                    pid = match.group(1)
                    self.shell(['kill', kill_signal, pid])

    def start_screenrecord(self):
        """Start a screenrecord session on the device"""
        self.shell(['rm', '/data/local/tmp/tom_video.mp4'])
        try:
            cmd = self.build_adb_command(['shell', 'screenrecord', '--verbose',
                                          '--bit-rate', '8000000',
                                          '/data/local/tmp/tom_video.mp4'])
            self.screenrecord = subprocess.Popen(cmd)
        except Exception:
            logging.exception('Error starting screenrecord')

    def stop_screenrecord(self, local_file):
        """Stop a screen record and download the video to local_file"""
        if self.screenrecord is not None:
            logging.debug('Stopping screenrecord')
            self.kill_proc('screenrecord')
            self.wait_for_process(self.screenrecord)
            self.screenrecord = None
            if local_file is not None:
                self.adb(['pull', '/data/local/tmp/tom_video.mp4', local_file])
            self.shell(['rm', '/data/local/tmp/tom_video.mp4'])

    def get_battery_stats(self):
        """Get the temperature andlevel of the battery"""
        ret = {}
        out = self.shell(['dumpsys', 'battery'], silent=True)
        if out is not None:
            for line in out.splitlines():
                match = re.search(r'^\s*level:\s*(\d+)', line)
                if match:
                    ret['level'] = int(match.group(1))
                match = re.search(r'^\s*temperature:\s*(\d+)', line)
                if match:
                    ret['temp'] = float(match.group(1)) / 10.0
        return ret

    def is_installed(self, package):
        """See if the given package is installed"""
        ret = False
        out = self.shell(['pm', 'list', 'packages'], silent=True)
        if out is not None:
            for line in out.splitlines():
                if line.find(package) >= 0:
                    ret = True
                    break
        return ret

    def cleanup_device(self):
        """Do some device-level cleanup"""
        start = monotonic()
        # Simulate pressing the home button to dismiss any UI
        self.shell(['input', 'keyevent', '3'])
        # Clear notifications
        self.shell(['settings', 'put', 'global', 'heads_up_notifications_enabled', '0'])
        # Close some known apps that pop-over
        for app in self.known_apps:
            if 'installed' not in self.known_apps[app]:
                out = self.shell(['dumpsys', 'package', app, '|', 'grep', 'versionName'])
                self.known_apps[app]['installed'] = bool(out is not None and len(out.strip()))
            if self.known_apps[app]['installed']:
                self.shell(['am', 'force-stop', app])
        # Cleanup the downloads folders
        self.shell(['rm', '-rf', '/sdcard/Download/*', '/sdcard/Backucup', '/sdcard/UCDownloads', '/data/local/tmp/tom_video.mp4'])
        # Clean up some system apps that collect cruft
        self.shell(['pm', 'clear', 'com.android.providers.downloads'])
        self.shell(['pm', 'clear', 'com.google.android.googlequicksearchbox'])
        self.shell(['pm', 'clear', 'com.google.android.youtube'])
        self.shell(['pm', 'clear', 'com.motorola.motocare'])
        # See if there are any system dialogs that need dismissing
        out = self.shell(['dumpsys', 'window', 'windows'])
        if re.search(r'Window #[^\n]*Application Error\:', out) is not None or \
                re.search(r'Window #[^\n]*systemui\.usb\.UsbDebuggingActivity', out) is not None:
            logging.warning('Dismissing system dialog')
            self.shell(['input', 'keyevent', 'KEYCODE_DPAD_RIGHT'], silent=True)
            self.shell(['input', 'keyevent', 'KEYCODE_DPAD_RIGHT'], silent=True)
            self.shell(['input', 'keyevent', 'KEYCODE_ENTER'], silent=True)
        if out.find('com.google.android.apps.gsa.staticplugins.opa.errorui.OpaErrorActivity') >= 0:
            self.shell(['am', 'force-stop', 'com.google.android.googlequicksearchbox'])
        if out.find('com.motorola.ccc.ota/com.motorola.ccc.ota.ui.DownloadActivity') >= 0:
            self.shell(['am', 'force-stop', 'com.motorola.ccc.ota'])

    def is_device_ready(self):
        """Check to see if the device is ready to run tests"""
        is_ready = True
        if self.version is None:
            # Turn down the volume (just one notch each time it is run)
            self.shell(['input', 'keyevent', '25'])
            self.cleanup_device()
            out = self.shell(['getprop', 'ro.build.version.release'], silent=True)
            if out is not None:
                self.version = 'Android ' + out.strip()
                try:
                    match = re.search(r'^(\d+(\.\d+)?)', out)
                    if match:
                        self.short_version = float(match.group(1))
                        logging.debug('%s (%0.2f)', self.version, self.short_version)
                except Exception:
                    logging.exception('Error parsing Android version')
        if self.version is None:
            logging.debug('Device not detected')
            return False
        if self.kernel is None:
            out = self.shell(['getprop', 'ro.com.google.clientidbase'], silent=True)
            if out is not None:
                self.kernel = out.strip()
        battery = self.get_battery_stats()
        logging.debug(battery)
        if 'level' in battery and battery['level'] < 50:
            logging.info("Device not ready, low battery: %d %%", battery['level'])
            is_ready = False
        if 'temp' in battery and battery['temp'] > self.options.temperature:
            logging.info("Device not ready, high temperature: %0.1f degrees", battery['temp'])
            is_ready = False
        if is_ready and not self.initialized:
            self.initialized = True
            # Disable emergency alert notifications
            self.shell(['uninstall', '-k', '--user', '0', 'com.android.cellbroadcastreceiver'])
            self.shell(['uninstall', '-k', '--user', '0', 'com.google.android.cellbroadcastreceiver'])
        return is_ready

    def get_jiffies_time(self):
        """Get the uptime in nanoseconds and jiffies for hz calculation"""
        out = self.shell(['cat', '/proc/timer_list'], silent=True)
        nsecs = None
        jiffies = None
        if out is not None:
            for line in out.splitlines():
                if nsecs is None:
                    match = re.search(r'^now at (\d+) nsecs', line)
                    if match:
                        nsecs = int(match.group(1))
                if jiffies is None:
                    match = re.search(r'^jiffies:\s+(\d+)', line)
                    if match:
                        jiffies = int(match.group(1))
        return nsecs, jiffies

    def get_bytes_rx(self):
        """Get the incremental bytes received across all non-loopback interfaces"""
        bytes_rx = 0
        out = self.shell(['cat', '/proc/net/dev'], silent=True)
        if out is not None:
            for line in out.splitlines():
                match = re.search(r'^\s*(\w+):\s+(\d+)', line)
                if match:
                    interface = match.group(1)
                    if interface != 'lo':
                        bytes_rx += int(match.group(2))
        delta = bytes_rx - self.last_bytes_rx
        self.last_bytes_rx = bytes_rx
        return delta

    def get_video_size(self):
        """Get the current size of the video file"""
        size = 0
        out = self.shell(['ls', '-l', '/data/local/tmp/tom_video.mp4'], silent=True)
        match = re.search(r'[^\d]+\s+(\d+) \d+', out)
        if match:
            size = int(match.group(1))
        return size

    def screenshot(self, dest_file):
        """Capture a png screenshot of the device"""
        device_path = '/data/local/tmp/tom_screenshot.png'
        self.shell(['rm', '/data/local/tmp/tom_screenshot.png'], silent=True)
        self.shell(['screencap', '-p', device_path])
        self.adb(['pull', device_path, dest_file])

    def get_orientation(self):
        """Get the device orientation"""
        orientation = 0
        out = self.shell(['dumpsys', 'input'], silent=True)
        match = re.search(r'SurfaceOrientation: ([\d])', out)
        if match:
            orientation = int(match.group(1))
        return orientation

    def get_package_version(self, package):
        """Get the version number of the given package"""
        version = None
        out = self.shell(['dumpsys', 'package', package, '|', 'grep', 'versionName'])
        if out is not None:
            for line in out.splitlines():
                separator = line.find('=')
                if separator > -1:
                    ver = line[separator + 1:].strip()
                    if len(ver):
                        version = ver
                        logging.debug('Package version for %s is %s', package, version)
                        break
        return version
