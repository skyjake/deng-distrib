#!/usr/bin/python
# coding=utf-8

# Script for managing automated build events.
# http://dengine.net/dew/index.php?title=Automated_build_system

import sys
import os
import shutil
import time
import string
import glob
import build_version
import builder
from builder.git import * 
from builder.utils import * 
    
    
def create_build_event():
    """Creates and tags a new build for with today's number."""
    print 'Creating a new build event.'
    git_pull()

    # Identifier/tag for today's build.
    todaysBuild = todays_build_tag()
    
    # Tag the source with the build identifier.
    git_tag(todaysBuild)
    
    prevBuild = builder.find_newest_event()['tag']
    print 'The previous build is:', prevBuild
    
    if prevBuild == todaysBuild:
        prevBuild = ''
    
    # Prepare the build directory.
    ev = builder.Event(todaysBuild)
    ev.clean()

    if prevBuild:
        update_changes(prevBuild, todaysBuild)
    

def todays_platform_release():
    """Build today's release for the current platform."""
    print "Building today's build."
    ev = builder.Event()
    
    git_pull()
    git_checkout(ev.tag())
    
    # We'll copy the new files to the build dir.
    os.chdir(builder.config.DISTRIB_DIR)
    existingFiles = os.listdir('releases')    
    
    print 'platform_release.py...'
    os.system("python platform_release.py > %s 2> %s" % ('buildlog.txt', 'builderrors.txt'))
    
    currentFiles = os.listdir('releases')
    for n in existingFiles:
        currentFiles.remove(n)
        
    for n in currentFiles:
        # Copy any new files.
        remote_copy(os.path.join('releases', n), ev.filePath(n))

        if builder.config.APT_REPO_DIR:
            # Copy also to the appropriate apt directory.
            arch = 'i386'
            if '_amd64' in n: arch = 'amd64'
            remote_copy(os.path.join('releases', n),
                        os.path.join(builder.config.APT_REPO_DIR, 'dists/unstable/main/binary-%s' % arch, n))
                                 
    # Also the build log.
    remote_copy('buildlog.txt', ev.filePath('doomsday-out-%s.txt' % sys_id()))
    remote_copy('builderrors.txt', ev.filePath('doomsday-err-%s.txt' % sys_id()))
                                             
    git_checkout('master')


def update_changes(fromTag=None, toTag=None, debChanges=False):
    """Generates the list of commits for the latest build."""
    
    if debChanges:
        # Make sure we have the latest changes.
        git_pull()
        fromTag = aptrepo_find_latest_tag()
        toTag = 'master' # Everything up to now.
    else:
        # Use the two most recent builds by default.
        if fromTag is None or toTag is None:
            builds = builder.events_by_time()
            if len(builds) < 2: return
            fromTag = builds[1][1].tag()
            toTag = builds[0][1].tag()

    changes = builder.Changes(fromTag, toTag)

    if debChanges:
        changes.generate('deb')
    else:
        changes.generate('html')
           
           
def update_debian_changelog():
    """Updates the Debian changelog at (distrib)/debian/changelog."""
    # Update debian changelog.
    update_changes(None, None, True)
           

def rebuild_apt_repository():
    """Rebuilds the Apt repository by running apt-ftparchive."""
    aptDir = builder.config.APT_REPO_DIR
    print 'Rebuilding the apt repository in %s...' % aptDir
    
    os.system("apt-ftparchive generate ~/Dropbox/APT/ftparchive.conf")
    os.system("apt-ftparchive -c ~/Dropbox/APT/ftparchive-release.conf release %s/dists/unstable > %s/dists/unstable/Release" % (aptDir, aptDir))
    os.chdir("%s/dists/unstable" % aptDir)
    os.remove("Release.gpg")
    os.system("gpg --output Release.gpg -ba Release")
    os.system("~/Dropbox/Scripts/mirror-tree.py %s %s" % (aptDir, os.path.join(builder.config.EVENT_DIR, 'apt')))


def write_index_html(tag):
    ev = builder.Event(tag)
    f = file(ev.filePath('index.html'), 'wt')
    print >> f, "<html>"
    print >> f, "<head><title>Build %i</title></head>" % ev.number()
    print >> f, "<body>"
    print >> f, "<h1>Build %i</h1>" % ev.number()
    print >> f, ev.html_description(False)
    print >> f, "</body>"
    print >> f, "</html>"


def update_feed():
    """Generate events.rss into the event directory."""
    
    feedName = os.path.join(builder.config.EVENT_DIR, "events.rss")
    print "Updating feed in %s..." % feedName
    
    out = file(feedName, 'wt')
    print >> out, '<?xml version="1.0" encoding="UTF-8"?>'
    print >> out, '<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">'
    print >> out, '<channel>'
    
    print >> out, '<title>Doomsday Engine Builds</title>'
    print >> out, '<link>http://dengine.net/</link>'
    print >> out, '<atom:link href="%s/events.rss" rel="self" type="application/rss+xml" />' % builder.config.BUILD_URI
    print >> out, '<description>Automated binary builds of the Doomsday Engine.</description>'
    print >> out, '<language>en-us</language>'
    print >> out, '<webMaster>skyjake@users.sourceforge.net (Jaakko Keränen)</webMaster>'
    print >> out, '<lastBuildDate>%s</lastBuildDate>' % time.strftime(builder.config.RFC_TIME, 
        time.gmtime(builder.find_newest_event()['time']))
    print >> out, '<generator>autobuild.py</generator>'
    print >> out, '<ttl>180</ttl>' # 3 hours
    
    for timestamp, ev in builder.events_by_time():
        print >> out, '<item>'
        print >> out, '<title>Build %i</title>' % ev.number()
        print >> out, '<link>%s/%s/</link>' % (builder.config.BUILD_URI, ev.tag())
        print >> out, '<author>skyjake@users.sourceforge.net (skyjake)</author>'
        print >> out, '<pubDate>%s</pubDate>' % time.strftime(builder.config.RFC_TIME, time.gmtime(timestamp))
        print >> out, '<atom:summary>%s</atom:summary>' % ev.text_summary()
        print >> out, '<description>%s</description>' % ev.html_description()
        print >> out, '<guid isPermaLink="false">%s</guid>' % ev.tag()
        print >> out, '</item>'
        
        write_index_html(ev.tag())
    
    # Close.
    print >> out, '</channel>'
    print >> out, '</rss>'
    

def purge_apt_repository(atLeastSeconds):
    for d in ['i386', 'amd64']:
        binDir = os.path.join(builder.config.APT_REPO_DIR, 'dists/unstable/main/binary-') + d
        print 'Pruning binary apt directory', binDir
        # Find the old files.
        for fn in os.listdir(binDir):
            if fn[-4:] != '.deb': continue
            debPath = os.path.join(binDir, fn)
            ct = os.stat(debPath).st_ctime
            if time.time() - ct >= atLeastSeconds:
                print 'Deleting', debPath
                os.remove(debPath)


def purge_obsolete():
    """Purge old builds from the event directory (old > 12 weeks)."""
    threshold = 3600 * 24 * 7 * 12

    # Also purge the apt repository if one has been specified.
    if builder.config.APT_REPO_DIR:
        purge_apt_repository(threshold)
    
    # Purge the old events.
    print 'Deleting build events older than 12 weeks...'
    for ev in builder.find_old_events(threshold):
        print ev.tag()
        shutil.rmtree(ev.path()) 
        
    print 'Purge done.'


def dir_cleanup():
    """Purges empty build directories from the event directory."""
    print 'Event directory cleanup starting...'
    for emptyEventPath in builder.find_empty_events():
        print 'Deleting', emptyEventPath
        os.rmdir(emptyEventPath)
    print 'Cleanup done.'


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
    'create': create_build_event,
    'platform_release': todays_platform_release,
    'changes': update_changes,
    'debchanges': update_debian_changelog,
    'apt': rebuild_apt_repository,
    'feed': update_feed,
    'purge': purge_obsolete,
    'cleanup': dir_cleanup,
    'help': show_help
}

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print 'The arguments must be: (command) [args]'
        print 'Commands:', string.join(sorted_commands())
        print 'Arguments:'
        print '--distrib  Doomsday distrib directory'
        print '--events   Event directory (builds are stored here in subdirs)'
        print '--apt      Apt repository'
        sys.exit(1)

    if sys.argv[1] not in commands:
        print 'Unknown command:', sys.argv[1]
        sys.exit(1)

    commands[sys.argv[1]]()