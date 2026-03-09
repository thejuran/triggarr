#!/bin/bash
set -e

# ---- PUID / PGID handling ----
# Follows LinuxServer.io conventions: set PUID/PGID env vars to control
# the UID/GID the application runs as inside the container.
PUID="${PUID:-1000}"
PGID="${PGID:-1000}"

# Validate numeric
if ! [[ "$PUID" =~ ^[0-9]+$ ]]; then
    echo "WARNING: PUID '$PUID' is not numeric, defaulting to 1000"
    PUID=1000
fi
if ! [[ "$PGID" =~ ^[0-9]+$ ]]; then
    echo "WARNING: PGID '$PGID' is not numeric, defaulting to 1000"
    PGID=1000
fi

# Create group if GID doesn't already exist
if ! getent group "$PGID" > /dev/null 2>&1; then
    groupadd -g "$PGID" fetcharr
fi

# Create user if UID doesn't already exist
if ! getent passwd "$PUID" > /dev/null 2>&1; then
    useradd -u "$PUID" -g "$PGID" -d /config -s /sbin/nologin fetcharr
fi

# Ensure the config volume is owned by the runtime user
chown -R "$PUID:$PGID" /config

# Drop privileges and exec into Fetcharr.
# exec replaces this shell so python becomes PID 1 and receives SIGTERM
# from `docker stop` directly.
# Detect --no-new-privileges support (Synology DSM ships a stripped setpriv)
if setpriv --no-new-privileges true 2>/dev/null; then
    NO_NEW_PRIVS="--no-new-privileges"
else
    echo "WARNING: setpriv --no-new-privileges not supported, skipping"
    NO_NEW_PRIVS=""
fi
exec setpriv --reuid="$PUID" --regid="$PGID" --init-groups $NO_NEW_PRIVS python -m fetcharr
