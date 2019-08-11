#!/usr/bin/env python2.7
# coding=utf-8
#
# Script for performing automated build events.
# http://dengine.net/dew/index.php?title=Automated_build_system
#
# The Build Pilot (pilot.py) is responsible for task distribution
# and management.

import sys
import os
import subprocess
import shutil
import time
import string
import glob
import builder
import pickle
import zipfile
from builder.git import *
from builder.utils import *


def pull_from_branch():
    """Pulls commits from the repository."""
    git_pull()


def create_build_event():
    """Creates and tags a new build for with today's number."""
    print 'Creating a new build event.'
    git_pull()

    # Identifier/tag for today's build.
    todaysBuild = todays_build_tag()

    # Tag the source with the build identifier.
    git_tag(todaysBuild)

    # Prepare the build directory.
    ev = builder.Event(todaysBuild)
    ev.clean()

    # Save the version number and release type.
    import build_version
    build_version.find_version(quiet=True)
    print >> file(ev.file_path('version.txt'), 'wt'), \
        build_version.DOOMSDAY_VERSION_FULL
    print >> file(ev.file_path('releaseType.txt'), 'wt'), \
        build_version.DOOMSDAY_RELEASE_TYPE

    update_changes()


def todays_platform_release():
    """Build today's release for the current platform."""
    print "Building today's build."
    ev = builder.Event()

    git_pull()

    git_checkout(ev.tag() + builder.config.TAG_MODIFIER)

    # We'll copy the new files to the build dir.
    os.chdir(builder.config.DISTRIB_DIR)
    oldFiles = DirState('releases', subdirs=False)

    try:
        print 'platform_release.py...'
        run_python2("platform_release.py > %s 2> %s" % \
            ('buildlog.txt', 'builderrors.txt'))
    except Exception, x:
        print 'Error during platform_release:', x

    for n in DirState('releases', subdirs=False).list_new_files(oldFiles):
        # Copy any new files.
        remote_copy(os.path.join('releases', n), ev.file_path(n))

        if builder.config.APT_REPO_DIR:
            # Copy also to the appropriate apt directory.
            arch = 'i386'
            if '_amd64' in n: arch = 'amd64'
            remote_copy(os.path.join('releases', n),
                        os.path.join(builder.config.APT_REPO_DIR,
                                     builder.config.APT_DIST + \
                                     '/main/binary-%s' % arch, n))

    # Also the build logs.
    remote_copy('buildlog.txt', ev.file_path('doomsday-out-%s.txt' % sys_id()))
    remote_copy('builderrors.txt', ev.file_path('doomsday-err-%s.txt' % sys_id()))

    #if 'linux' in sys_id():
    #    remote_copy('dsfmod/fmod-out-%s.txt' % sys_id(), ev.file_path('fmod-out-%s.txt' % sys_id()))
    #    remote_copy('dsfmod/fmod-err-%s.txt' % sys_id(), ev.file_path('fmod-err-%s.txt' % sys_id()))

    git_checkout(builder.config.BRANCH)


def sign_packages():
    """Sign all packages in the latest build."""
    ev = builder.Event(latestAvailable=True)
    print "Signing build %i." % ev.number()
    for fn in os.listdir(ev.path()):
        if fn.endswith('.msi') or fn.endswith('.exe') or fn.endswith('.dmg') or fn.endswith('.deb'):
            # Make a signature for this.
            os.system("gpg --output %s -ba %s" % (ev.file_path(fn) + '.sig', ev.file_path(fn)))


def publish_packages():
    """Publish all packages to SourceForge."""
    ev = builder.Event(latestAvailable=True)
    print "Publishing build %i." % ev.number()
    system_command('deng_copy_build_to_sourceforge.sh "%s"' % ev.path())


def find_previous_tag(toTag, version):
    """Finds the build tag preceding `toTag`.

    Arguments:
        toTag:   Build tag ("buildNNNN").
        version: The preceding build tag must be from this version,
                 comparing only major and minor version components.
                 Set to None to omit comparisons based on version.
    Returns:
        Build tag ("buildNNNN").
        None, if there is no applicable previous build.
    """
    builds = builder.events_by_time() # descending by timestamp

    print "Finding previous build for %s (version:%s)" % (toTag, version)

    # Disregard builds later than `toTag`.
    while len(builds) and builds[0][1].tag() != toTag:
        del builds[0]
    if len(builds): del builds[0] # == toTag
    if len(builds) == 0:
        return None

    for timestamp, ev in builds:
        print ev.tag(), ev.version(), time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime(ev.timestamp()))

        if version is None:
            # Anything goes.
            return ev.tag()
        else:
            requiredVer = version_split(version)
            eventVer = version_split(ev.version())
            if requiredVer[:2] == eventVer[:2]:
                return ev.tag()

    # Nothing suitable found. Fall back to a more lax search.
    return find_previous_tag(toTag, None)


def update_changes(debChanges=False):
    """Generates the list of commits for the latest build."""

    git_pull()
    toTag = todays_build_tag()

    import build_version

    # Look up the relevant version.
    event = builder.Event(toTag)
    refVersion = event.version()

    # Let's find the previous event of this version.
    fromTag = find_previous_tag(toTag, refVersion)

    if fromTag is None or toTag is None:
        # Range not defined.
        return

    print 'Changes for range', fromTag, '..', toTag

    changes = builder.Changes(fromTag, toTag)

    if debChanges:
        # Only update the Debian changelog.
        changes.generate('deb')

        # Also update the doomsday-fmod changelog (just version number).
        #os.chdir(os.path.join(builder.config.DISTRIB_DIR, 'dsfmod'))
        #fmodVer = build_version.parse_cmake_for_version('../../doomsday/cmake/Version.cmake')
        #debVer = "%s.%s.%s-%s" % (fmodVer[0], fmodVer[1], fmodVer[2], todays_build_tag())
        #print "Marking new FMOD version:", debVer
        #msg = 'New release: Doomsday Engine build %i.' % builder.Event().number()
        #os.system('rm -f debian/changelog && dch --check-dirname-level 0 --create --package doomsday-fmod -v %s "%s"' % (debVer, msg))
        #os.system('dch --release ""')

    else:
        changes.generate('html')
        changes.generate('xml')


def update_debian_changelog():
    """Updates the Debian changelog at (distrib)/debian/changelog."""
    # Update debian changelog.
    update_changes(debChanges=True)


def build_source_package():
    """Builds the source tarball and a Debian source package."""
    update_debian_changelog()
    git_pull()
    ev = builder.Event(latestAvailable=True)
    print "Creating source tarball for build %i." % ev.number()

    # Check distribution.
    system_command("lsb_release -a | perl -n -e 'm/Codename:\s(.+)/ && print $1' > /tmp/distroname")
    hostDistro = file('/tmp/distroname', 'rt').read()
    distros = ['xenial', 'bionic', 'disco']

    for distro in distros:
        for pkgName in ['doomsday', 'doomsday-server']:
            isServerOnly = pkgName.endswith('-server')

            os.chdir(os.path.join(builder.config.DISTRIB_DIR))
            remkdir('srcwork')
            os.chdir('srcwork')

            if ev.release_type() == 'stable':
                print 'Stable packages will be prepared'
                system_command('deng_package_source.sh stable %i %s' % (ev.number(), ev.version_base()))
                pkgName += '-stable'
            else:
                system_command('deng_package_source.sh unstable %i %s' % (ev.number(), ev.version_base()))
            for fn in os.listdir('.'):
                if fn[:9] == 'doomsday-' and fn[-7:] == '.tar.gz' and ev.version_base() in fn:
                    remote_copy(fn, ev.file_path(fn))
                    break

            # Create a source Debian package and upload it to Launchpad.
            pkgVer = '%s.%i+%s' % (ev.version_base(), ev.number(), distro)
            pkgDir = pkgName + '-%s' % pkgVer

            print "Extracting", fn
            system_command('tar xzf %s' % fn)
            print "Renaming", fn[:-7], 'to', pkgDir + '.orig'
            os.rename(fn[:-7], pkgDir + '.orig')

            origName = pkgName + '_%s' % ev.version_base() + '.orig.tar.gz'
            print "Symlink to", origName
            system_command('ln %s %s' % (fn, origName))

            print "Extracting", fn
            system_command('tar xzf %s' % fn)
            print "Renaming", fn[:-7], 'to', pkgDir
            os.rename(fn[:-7], pkgDir)
            os.chdir(pkgDir)
            #system_command('echo "" | dh_make --yes -s -c gpl2 --file ../%s' % fn)
            os.chdir('debian')
            for fn in os.listdir('.'):
                if fn[-3:].lower() == '.ex': os.remove(fn)
            #os.remove('README.Debian')
            #os.remove('README.source')

            def gen_changelog(src, dst, extraSub=''):
                system_command("sed 's/%s-build%i/%s/;%s' %s > %s" % (
                        ev.version_base(), ev.number(), pkgVer, extraSub, src, dst))

            # Figure out the name of the distribution.
            dsub = ''
            if distro != hostDistro:
                dsub = 's/) %s;/) %s;/' % (hostDistro, distro)
            if pkgName != 'doomsday':
                if dsub: dsub += ';'
                dsub += 's/^doomsday /%s /' % pkgName

            dengDir = builder.config.DOOMSDAY_DIR

            gen_changelog(os.path.join(dengDir, 'debian/changelog'), 'changelog', dsub)
            control = open(os.path.join(dengDir, 'doomsday/build/debian/control')).read()
            control = control.replace('${Arch}', 'i386 amd64')
            control = control.replace('${Package}', pkgName)
            control = control.replace('${DEBFULLNAME}', os.getenv('DEBFULLNAME'))
            control = control.replace('${DEBEMAIL}', os.getenv('DEBEMAIL'))
            if isServerOnly:
                for guiDep in ['libsdl2-mixer-dev', 'libxrandr-dev', 'libxxf86vm-dev',
                               'libqt5opengl5-dev', 'libqt5x11extras5-dev',
                               'libfluidsynth-dev']:
                    control = control.replace(guiDep + ', ', '')
                control = control.replace('port with enhanced graphics',
                                          'port with enhanced graphics (server only)')
            open('control', 'w').write(control)
            system_command("sed 's/${BuildNumber}/%i/;s/..\/..\/doomsday/..\/doomsday/;"
                        "s/APPNAME := doomsday/APPNAME := %s/';"
                        "s/COTIRE=OFF/COTIRE=OFF -DDENG_ENABLE_GUI=OFF/ "
                        "%s/doomsday/build/debian/rules > rules" %
                        (ev.number(), pkgName, dengDir))
            os.chdir('..')
            system_command('debuild -S')
            os.chdir('..')
            system_command('dput ppa:sjke/doomsday %s_%s_source.changes' % (pkgName, pkgVer))


def rebuild_apt_repository():
    """Rebuilds the Apt repository by running apt-ftparchive."""
    aptDir = builder.config.APT_REPO_DIR
    print 'Rebuilding the apt repository in %s...' % aptDir

    os.system("apt-ftparchive generate ~/Dropbox/APT/ftparchive.conf")
    os.system("apt-ftparchive -c %s release %s/%s > %s/%s/Release" % (builder.config.APT_CONF_FILE, aptDir, builder.config.APT_DIST, aptDir, builder.config.APT_DIST))
    os.chdir("%s/%s" % (aptDir, builder.config.APT_DIST))
    try:
        os.remove("Release.gpg")
    except OSError:
        # Never mind.
        pass
    os.system("gpg --output Release.gpg -ba Release")
    os.system("~/Scripts/mirror-tree.py %s %s" % (aptDir, os.path.join(builder.config.EVENT_DIR, 'apt')))


def purge_obsolete():
    """Purge old builds from the event directory (old > 4 weeks)."""
    threshold = 3600 * 24 * 7 * 4

    # We'll keep a small number of events unpurgable.
    totalCount = len(builder.find_old_events(0))

    # Purge the old events.
    print 'Deleting build events older than 4 weeks...'
    for ev in builder.find_old_events(threshold):
        if totalCount > 5:
            print ev.tag()
            shutil.rmtree(ev.path())
            totalCount -= 1

    print 'Purge done.'


def dir_cleanup():
    """Purges empty build directories from the event directory."""
    print 'Event directory cleanup starting...'
    for emptyEventPath in builder.find_empty_events():
        print 'Deleting', emptyEventPath
        os.rmdir(emptyEventPath)
    print 'Cleanup done.'


def system_command(cmd):
    result = subprocess.call(cmd, shell=True)
    if result != 0:
        raise Exception("Error from " + cmd)


def generate_apidoc():
    """Run Doxygen to generate all API documentation."""
    git_pull()

    print >> sys.stderr, "\nSDK docs..."
    os.chdir(os.path.join(builder.config.DOOMSDAY_DIR, 'doomsday'))
    system_command('doxygen sdk.doxy >/dev/null 2>doxyissues-sdk.txt')
    system_command('wc -l doxyissues-sdk.txt')

    print >> sys.stderr, "\nSDK docs for Qt Creator..."
    os.chdir(os.path.join(builder.config.DOOMSDAY_DIR, 'doomsday'))
    system_command('doxygen sdk-qch.doxy >/dev/null 2>doxyissues-qch.txt')
    system_command('wc -l doxyissues-qch.txt')

    print >> sys.stderr, "\nPublic API docs..."
    os.chdir(os.path.join(builder.config.DOOMSDAY_DIR, 'doomsday/apps/libdoomsday'))
    system_command('doxygen api.doxy >/dev/null 2>../../doxyissues-api.txt')
    system_command('wc -l ../../doxyissues-api.txt')


def generate_wiki():
    """Automatically generate wiki pages."""
    git_pull()
    sys.path += ['/Users/jaakko/Scripts']
    import dew
    dew.login()
    # Today's event data.
    ev = builder.Event(latestAvailable=True)
    if ev.release_type() == 'stable':
        dew.submitPage('Latest Doomsday release',
            '#REDIRECT [[Doomsday version %s]]' % ev.version())
    dew.logout()


def show_help():
    """Prints a description of each command."""
    for cmd in sorted_commands():
        if commands[cmd].__doc__:
            print "%-17s " % (cmd + ":") + commands[cmd].__doc__
        else:
            print cmd


def sorted_commands():
    sc = commands.keys()
    sc.sort()
    return sc


commands = {
    'pull': pull_from_branch,
    'create': create_build_event,
    'platform_release': todays_platform_release,
    'sign': sign_packages,
    'publish': publish_packages,
    'changes': update_changes,
    'debchanges': update_debian_changelog,
    'source': build_source_package,
    'apt': rebuild_apt_repository,
    'purge': purge_obsolete,
    'cleanup': dir_cleanup,
    'apidoc': generate_apidoc,
    'wiki': generate_wiki,
    'help': show_help
}

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print 'The arguments must be: (command) [args]'
        print 'Commands:', string.join(sorted_commands())
        print 'Arguments:'
        print '--branch    Branch to use (default: master)'
        print '--distrib   "deng-distrib" directory'
        print '--doomsday  Doomsday source root directory'
        print '--events    Event directory (builds are stored here in subdirs)'
        print '--apt       Apt repository'
        print '--tagmod    Additional suffix for build tag for platform_release'
        sys.exit(1)

    if sys.argv[1] not in commands:
        print 'Unknown command:', sys.argv[1]
        sys.exit(1)

    commands[sys.argv[1]]()
