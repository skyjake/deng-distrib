#!/usr/bin/env python3
# This script builds the distribution packages platform-independently.
# No parameters needed; config is auto-detected.

import sys
import os
import platform
import shutil
import string
import time
import glob
import build_version
import build_number
import builder.utils

# Configuration.
LAUNCH_DIR    = os.path.abspath(os.path.dirname(__file__))
DOOMSDAY_DIR  = os.path.abspath(os.path.join(LAUNCH_DIR, '..', 'deng', 'doomsday')) \
                if len(sys.argv) == 1 else os.path.abspath(sys.argv[1])
WORK_DIR      = os.path.join(LAUNCH_DIR, 'work')
OUTPUT_DIR    = os.path.join(LAUNCH_DIR, 'releases')
DOOMSDAY_VERSION_FULL       = "0.0.0-Name"
DOOMSDAY_VERSION_FULL_PLAIN = "0.0.0"
DOOMSDAY_VERSION_MAJOR      = 0
DOOMSDAY_VERSION_MINOR      = 0
DOOMSDAY_VERSION_REVISION   = 0
DOOMSDAY_RELEASE_TYPE       = "Unstable"
DOOMSDAY_BUILD_NUMBER       = build_number.todays_build()
DOOMSDAY_BUILD              = 'build' + DOOMSDAY_BUILD_NUMBER

TIMESTAMP = time.strftime('%y-%m-%d')
now = time.localtime()


def exit_with_error():
    os.chdir(LAUNCH_DIR)
    sys.exit(1)


def mkdir(n):
    try:
        os.mkdir(n)
    except OSError:
        print('Directory', n, 'already exists.')


def remkdir(n):
    attempts = 10
    while attempts > 0:
        try:
            builder.utils.remkdir(n)
            return
        except:
            pass
        attempts -= 1
        time.sleep(5)
    raise Exception("Failed to clear directory: " + n)


def remove(n):
    try:
        os.remove(n)
    except OSError:
        print('Cannot remove', n)


def copytree(s, d):
    try:
        shutil.copytree(s, d)
    except Exception as x:
        print(x)
        print('Cannot copy', s, 'to', d)


def duptree(s, d):
    os.system('cp -fRp "%s" "%s"' % (s, d))


def find_version():
    build_version.find_version(doomsdayDir=DOOMSDAY_DIR)

    global DOOMSDAY_VERSION_FULL
    global DOOMSDAY_VERSION_FULL_PLAIN
    global DOOMSDAY_VERSION_MAJOR
    global DOOMSDAY_VERSION_MINOR
    global DOOMSDAY_VERSION_REVISION
    global DOOMSDAY_RELEASE_TYPE
    
    DOOMSDAY_RELEASE_TYPE = build_version.DOOMSDAY_RELEASE_TYPE
    DOOMSDAY_VERSION_FULL_PLAIN = build_version.DOOMSDAY_VERSION_FULL_PLAIN
    DOOMSDAY_VERSION_FULL = build_version.DOOMSDAY_VERSION_FULL
    DOOMSDAY_VERSION_MAJOR = build_version.DOOMSDAY_VERSION_MAJOR
    DOOMSDAY_VERSION_MINOR = build_version.DOOMSDAY_VERSION_MINOR
    DOOMSDAY_VERSION_REVISION = build_version.DOOMSDAY_VERSION_REVISION

    print('Build:', DOOMSDAY_BUILD, 'on', TIMESTAMP)
    print('Version:', DOOMSDAY_VERSION_FULL_PLAIN, DOOMSDAY_RELEASE_TYPE)


def prepare_work_dir():
    remkdir(WORK_DIR)
    print("Work directory prepared.")


def mac_os_version():
    """Determines the Mac OS version."""
    return builder.utils.mac_os_version()


def mac_os_8_or_later():
    try:
        v = mac_os_version().split('.')
        return int(v[1]) >= 8
    except:
        return False


def mac_target_ext():
    if mac_os_8_or_later(): return '.dmg'
    if mac_os_version() == '10.6': return '_mac10_6.dmg'
    return '_32bit.dmg'


def mac_osx_suffix():
    if mac_os_8_or_later(): return 'macx8'
    if mac_os_version() == '10.6': return 'macx6'
    return 'macx'


def output_filename(ext='', extra=''):
    if extra != '' and not extra.endswith('_'): extra += '_'
    if DOOMSDAY_RELEASE_TYPE == "Stable":
        return 'doomsday_' + extra + DOOMSDAY_VERSION_FULL + ext
    else:
        return 'doomsday_' + extra + DOOMSDAY_VERSION_FULL + "_" + DOOMSDAY_BUILD + ext


def cmake_options_path():
    import pilot
    return 'cmake.%s.rsp' % pilot.currentBranch()


def cmake_options():
    """Reads the contents of the CMake options file that determines which flags are used
    when building a release."""
    try:
        opts = open(os.path.join(LAUNCH_DIR, cmake_options_path()), 'rt').read().replace('\n', ' ')
    except:
        print(("No additional options provided for CMake (%s missing)" % cmake_options_path()))
        opts = ''
    common = ' -DCMAKE_BUILD_TYPE=Release -DDENG_BUILD=%s -DDE_BUILD=%s' % (
        DOOMSDAY_BUILD_NUMBER, DOOMSDAY_BUILD_NUMBER)
    return [o + common for o in map(str.strip, opts.split('-----'))]


def cmake_release(makeOptions, outputGlobs):
    """Runs cmake in the work directory and copies the output files to OUTPUT_DIR."""
    for currentOptions in cmake_options():
        os.chdir(LAUNCH_DIR)
        remkdir(WORK_DIR)
        os.chdir(WORK_DIR)

        try:
            postCommand = open(os.path.join(LAUNCH_DIR, 'postcommand.txt'), 'rt').read()
        except:
            postCommand = None

        if os.system('cmake %s %s' % (currentOptions, DOOMSDAY_DIR)):
            raise Exception("Failed to configure the build.")
        if os.system('cmake --build . --config Release' + (' -- %s' % makeOptions if makeOptions else '')):
            raise Exception("Build failed!")

        # Use CPack to create the package.
        if os.system('cmake --build . --config Release --target package'):
            raise Exception("Failed to package the binaries.")
        for outputGlob in outputGlobs:
            for fn in glob.glob(outputGlob):
                if postCommand:
                    os.system(postCommand % fn)
                shutil.copy(fn, OUTPUT_DIR)


def mac_release():
    cmake_release('-j4', ['*.dmg'])


def win_release():
    cmake_release('/m', ['*.msi', '*.zip'])


def linux_release():
    cmake_release('-j`nproc`', ['*.deb', '*.rpm'])


def main():
    prepare_work_dir()
    find_version()

    print("Checking OS...", end=' ')

    try:
        if sys.platform == "darwin":
            print("Mac OS X (%s)" % mac_os_version())
            mac_release()
        elif sys.platform == "win32":
            print("Windows")
            win_release()
        elif sys.platform == "linux2" or sys.platform == "linux":
            print("Linux")
            linux_release()
        else:
            print("Unknown!")
            print("I don't know how to make a release on this platform.")
            exit_with_error()
    except Exception as x:
        print("Creating the release failed!")
        print(x)
        exit_with_error()

    os.chdir(LAUNCH_DIR)
    print("Done.")


if __name__ == '__main__':
    main()
