import os
import sys

def get_arg(label):
    """Find the value for the command line option @a label."""
    if label in sys.argv:
        return sys.argv[sys.argv.index(label) + 1]
    return None

BUILD_AUTHOR_NAME = "skyjake"
BUILD_AUTHOR_EMAIL = "skyjake@users.sourceforge.net"
BUILD_URI = "http://code.iki.fi/builds"
RFC_TIME = "%a, %d %b %Y %H:%M:%S +0000"
if 'HOME' in os.environ:
    EVENT_DIR = os.path.join(os.environ['HOME'], 'BuildMaster')
else:
    EVENT_DIR = '.'
DISTRIB_DIR = '.'
APT_REPO_DIR = ''
TAG_MODIFIER = ''

val = get_arg('--distrib')
if val is not None: DISTRIB_DIR = val

val = get_arg('--events')
if val is not None: EVENT_DIR = val

val = get_arg('--apt')
if val is not None: APT_REPO_DIR = val

val = get_arg('--tagmod')
if val is not None: TAG_MODIFIER = val
