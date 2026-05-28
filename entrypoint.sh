#!/bin/sh
# Ensure /data is writable by appuser regardless of host mount ownership
chown appuser /data 2>/dev/null || true
exec gosu appuser "$@"
