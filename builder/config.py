import os
import sys

def get_arg(label):
    """Find the value for the command line option @a label."""
    if label in sys.argv:
        return sys.argv[sys.argv.index(label) + 1]
    return None

BUILD_AUTHOR_NAME = "skyjake"
BUILD_AUTHOR_EMAIL = "skyjake@dengine.net"
BUILD_URI = "http://files.dengine.net/builds"
RFC_TIME = "%a, %d %b %Y %H:%M:%S +0000"
if 'HOME' in os.environ:
    EVENT_DIR = os.path.join(os.environ['HOME'], 'BuildMaster')
else:
    EVENT_DIR = '.'
DISTRIB_DIR = '.'
DENG_ROOT_DIR = ''
APT_REPO_DIR = ''
TAG_MODIFIER = ''
BRANCH = 'master'

val = get_arg('--distrib')
if val is not None: DISTRIB_DIR = val

val = get_arg('--dengroot')
if val is not None: DENG_ROOT_DIR = val

val = get_arg('--events')
if val is not None: EVENT_DIR = val

val = get_arg('--apt')
if val is not None: APT_REPO_DIR = val

val = get_arg('--branch')
if val is not None: BRANCH = val

val = get_arg('--tagmod')
if val is not None: TAG_MODIFIER = val

# Determine APT repository path.
oldCwd = os.getcwd()
if DISTRIB_DIR:
    DISTRIB_DIR = os.path.abspath(DISTRIB_DIR)
    os.chdir(DISTRIB_DIR)
import build_version
build_version.find_version(quiet=True)
if build_version.DOOMSDAY_RELEASE_TYPE == 'Stable':
    APT_DIST = 'dists/stable'
    APT_CONF_FILE = '~/Dropbox/APT/ftparchive-release-stable.conf'
else:
    APT_DIST = 'dists/unstable'
    APT_CONF_FILE = '~/Dropbox/APT/ftparchive-release.conf'
os.chdir(oldCwd)
