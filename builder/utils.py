import os, sys, platform
import shutil
import subprocess
import string
import glob
import gzip
import codecs
import time
import build_number
from . import config

def remkdir(n):
    if os.path.exists(n):
        print(n, 'exists, clearing it...')
        shutil.rmtree(n, True)
    os.mkdir(n)


def deltree(n):
    if os.path.exists(n):
        shutil.rmtree(n, True)


def omit_path(path, omitted):
    if path.startswith(omitted):
        path = path[len(omitted):]
        if path[0] == '/' or path[0] == '\\': path = path[1:]
    return path


class FileState:
    def __init__(self, isDir, mtime):
        if isDir:
            self.type = 'dir'
        else:
            self.type = 'file'
        self.mtime = int(mtime)

    def __repr__(self):
        return "(%s, %i)" % (self.type, self.mtime)


class DirState:
    def __init__(self, path=None, subdirs=True):
        self.files = {} # path -> FileState
        self.subdirs = subdirs
        if path:
            self.update(path, path)

    def update(self, path, omitted=None):
        for name in os.listdir(path):
            if name[0] == '.': continue
            fullPath = os.path.join(path, name)
            self.files[omit_path(fullPath, omitted)] = \
                FileState(os.path.isdir(fullPath), os.stat(fullPath).st_mtime)
            if os.path.isdir(fullPath) and self.subdirs:
                self.update(fullPath, omitted)

    def list_new_files(self, oldState):
        new = []
        for path in self.files:
            if self.files[path].type == 'dir': continue
            if path not in oldState.files or self.files[path].mtime > oldState.files[path].mtime:
                new.append(path)
        return new

    def list_removed(self, oldState):
        """Returns a tuple: (list of removed files, list of removed dirs)"""
        rmFiles = []
        rmDirs = []
        for oldPath in oldState.files:
            if oldPath not in self.files:
                if oldState.files[oldPath].type == 'dir':
                    rmDirs.append(oldPath)
                else:
                    rmFiles.append(oldPath)
        return (rmFiles, rmDirs)


def sys_id():
    bits = platform.architecture()[0]

    plat = sys.platform

    # Special case: the Snow Leopard builder targets 64-bit.
    if plat == 'darwin':
        macVer = mac_os_version()
        if macVer in ['10.8', '10.9', '10.10', '10.11']:
            plat = 'macx8'
            bits = '64bit'
        elif macVer == '10.6':
            bits = '64bit'
        elif macVer == '10.5':
            plat = 'macx5'

    return "%s-%s" % (plat, bits)


def remote_copy(src, dst):
    dst = dst.replace('\\', '/')
    os.system('scp %s %s' % (src, dst))


def collated(s):
    s = s.strip()
    while s[-1] == '.':
        s = s[:-1]
    return s


def todays_build_tag():
    now = time.localtime()
    return 'build' + build_number.todays_build()


def deb_arch():
    os.system('dpkg --print-architecture > __debarch.tmp')
    arch = open('__debarch.tmp', 'rt').read().strip()
    os.remove('__debarch.tmp')
    return arch


def aptrepo_by_time():
    files = []
    for fn in os.listdir(os.path.join(config.APT_REPO_DIR,
                                      'dists/unstable/main/binary-' + deb_arch())):
        if fn[-4:] == '.deb':
            files.append(fn)
    return files


def aptrepo_find_latest_tag():
    debs = aptrepo_by_time()
    if not debs: return config.BRANCH
    arch = deb_arch()
    biggest = 0
    for deb in debs:
        number = int(deb[deb.find('-build')+6 : deb.find('_'+arch)])
        biggest = max(biggest, number)
    return 'build' + str(biggest)


def count_log_word(fn, word):
    count = 0
    try:
        for txt in [str(rl, 'latin1').lower() for rl in string.split(gzip.open(fn).read(), '\n')]:
            pos = txt.find(str(word))
            if pos < 0: continue
            endPos = pos + len(word)
            # Ignore some unnecessary messages.
            if 'should be explicitly initialized in the copy constructor' in txt: continue
            if 'deprecated' in txt: continue
            if 'doomsday\\external\\assimp\\code' in txt: continue
            if 'doomsday\\external\\assimp\\contrib' in txt: continue
            if 'doomsday/external/assimp/code' in txt: continue
            if 'doomsday/external/assimp/contrib' in txt: continue
            if ' warning generated.' in txt: continue
            if ' warnings generated.' in txt: continue
            if 'vcinstalldir is not set' in txt: continue
            try:
                if txt[pos-1] not in '/\\_'+string.ascii_letters and \
                    txt[endPos] not in string.ascii_letters+'.(' and \
                    txt[pos-11:pos] != 'shlibdeps: ' and txt[pos-12:pos] != 'genchanges: ' and \
                    txt[pos-12:pos] != 'cc1objplus: ':
                    #print('@', pos, 'in', txt)
                    count += 1
            except IndexError:
                count += 1
    except:
        pass
    #print '%s: counted "%s": %i' % (fn, word, count)
    return count


def count_log_issues(fn):
    """Returns tuple of (#warnings, #errors) in the fn."""
    return (count_log_word(fn, 'error'), count_log_word(fn, 'warning'))


def count_word(word, inText):
    pos = 0
    count = 0
    while True:
        pos = inText.find(word, pos)
        if pos < 0: break
        count += 1
        pos += len(word)
    return count


def mac_os_version():
    """Determines the Mac OS version."""
    ver = platform.mac_ver()[0]
    if not ver: return None
    if ver.count('.') == 1: # "10.9"
        return ver
    return ver[:ver.rindex('.')] # "10.9.3"


def version_split(versionText):
    return list(map(int, versionText.split('.')))


def version_cmp(a, b):
    """Compares two versions, returning -1 if a < b, 0 if a == b, and 1 if a > b.

    Arguments:
        a:  String in the form "1.2.3"
        b:  String in the form "3.4.5"
    """
    va = version_split(a)
    vb = version_split(b)
    if va < vb: return -1
    if va > vb: return 1
    return 0


def system_command(cmd):
    result = subprocess.call(cmd, shell=True)
    if result != 0:
        raise Exception("System command \"%s\" returned error code %i" % (cmd, result))


def python3_executable():
    if sys.platform[:3] == 'win':
        return 'python'
    else:
        return '/usr/bin/env python3'  # required by Snowberry


def run_python3(script):
    system_command(python3_executable() + " " + script)
