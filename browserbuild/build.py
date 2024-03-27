#!/usr/bin/env python3
# Copyright 2024 Google Inc.
"""Trace-O-Matic Browser Build cli - send a build latest command to the build queue"""
import greenstalk

queue = greenstalk.Client(('127.0.0.1', 11300))
queue.use('build')
queue.put('latest')
print('Build job added to queue')