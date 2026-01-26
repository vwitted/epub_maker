#!/bin/bash
set -e

# Start SSH service
# We verify the directory exists to avoid errors on some systems
mkdir -p /run/sshd

# Start sshd in background? 
# Usually 'service ssh start' works for systemd/init systems, but in basic containers we might execute directly.
# However, python:3.10-slim is based on Debian.
# Let's try standard service start if available, or direct execution.
if [ -x "$(command -v service)" ]; then
    service ssh start
else
    /usr/sbin/sshd
fi

# Execute the passed command
# We don't use 'exec' here so the script can continue if KEEP_ALIVE is set
"$@" || true

# Keep alive if requested
if [ "$KEEP_ALIVE" = "1" ]; then
    echo "Command finished. KEEP_ALIVE is set, idling... (SSH access remains active)"
    tail -f /dev/null
fi
