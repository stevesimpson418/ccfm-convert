#!/bin/sh
set -e

# If first arg is "ccfm", the user passed it explicitly — strip it
# so we don't double up (ENTRYPOINT already provides ccfm).
if [ "$1" = "ccfm" ]; then
    shift
fi

# If first arg looks like a flag (starts with -), run ccfm with those flags.
if [ "${1#-}" != "$1" ]; then
    exec ccfm "$@"
fi

# If no args, show help.
if [ $# -eq 0 ]; then
    exec ccfm --help
fi

# Otherwise, the caller wants to run an arbitrary command (e.g. GitLab CI
# injecting a shell script). Execute it directly.
exec "$@"
