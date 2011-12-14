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
import platform
import gzip
import codecs
import build_version
import builder
from builder.git import * 
from builder.utils import * 


def text_build_summary(name):
    msg = "The build event was started on %s." % (time.strftime(builder.config.RFC_TIME, 
                                                  time.gmtime(build_timestamp(name))))
    
    msg += ' It'
    
    pkgCount = len(list_package_files(name))
        
    changesName = os.path.join(builder.config.EVENT_DIR, name, 'changes.html')
    commitCount = 0
    if os.path.exists(changesName):
        commitCount = count_word('<li>', file(changesName).read())
    if commitCount:
        msg += " contains %i commits and" % commitCount
        
    msg += " produced %i installable binary package%s." % \
        (pkgCount, 's' if (pkgCount != 1) else '')
    
    return msg
    
        
def html_build_description(name, encoded=True):
    buildDir = os.path.join(builder.config.EVENT_DIR, name)
    
    msg = '<p>' + text_build_summary(name) + '</p>'
    
    # What do we have here?
    files = list_package_files(name)    

    oses = [('Windows (x86)',             '.exe',      'win32-32bit'),
            ('Mac OS X 10.4+ (i386/ppc)', '.dmg',      'darwin-32bit'),
            ('Ubuntu (x86)',              'i386.deb',  'linux2-32bit'),
            ('Ubuntu (x86_64)',           'amd64.deb', 'linux2-64bit')]
    
    # Prepare compiler logs.
    for package in ['doomsday', 'fmod']:
        for osName, osExt, osIdent in oses:
            names = glob.glob(os.path.join(buildDir, '%s-*-%s.txt' % (package, osIdent)))
            if not names: continue
            # Join the logs into a single file.
            combinedName = os.path.join(buildDir, 'buildlog-%s-%s.txt' % (package, osIdent))
            combined = file(combinedName, 'wt')
            for n in names:
                combined.write(file(n).read() + "\n\n")
                # Remove the original log.
                os.remove(n)
            combined.close()            
            os.system('gzip -f9 %s' % combinedName)
    
    # Print out the matrix.
    msg += '<p><table cellspacing="4" border="0">'
    msg += '<tr style="text-align:left;"><th>OS<th>Binary<th>Logs<th>Er/Wrn</tr>'
    
    for osName, osExt, osIdent in oses:
        isFirst = True
        # Find the binaries for this OS.
        binaries = []
        for f in files:
            if osExt in f:
                binaries.append(f)
        
        if not binaries:
            # Nothing available for this OS.
            msg += '<tr><td>' + osName + '<td>n/a</tr>'
            continue

        # List all the binaries. One row per binary.
        for binary in binaries:
            msg += '<tr><td>'
            if isFirst:
                msg += osName
                isFirst = False
            msg += '<td>'
            msg += '<a href="%s/%s/%s">%s</a>' % (builder.config.BUILD_URI, name, binary, binary)

            if 'fmod' in binary:
                packageName = 'fmod'
            else:
                packageName = 'doomsday'
        
            # Status of the log.
            logName = 'buildlog-%s-%s.txt.gz' % (packageName, osIdent)
            logFileName = os.path.join(buildDir, logName)
            if not os.path.exists(logFileName):
                msg += '</tr>'
                continue                            

            # Link to the compressed log.
            msg += '<td><a href="%s/%s/%s">txt.gz</a>' % (builder.config.BUILD_URI, name, logName)
              
            # Show a traffic light indicator based on warning and error counts.              
            errors, warnings = count_log_status(logFileName)
            form = '<td bgcolor="%s" style="text-align:center;">'
            if errors > 0:
                msg += form % '#ff4444' # red
            elif warnings > 0:
                msg += form % '#ffee00' # yellow
            else:
                msg += form % '#00ee00' # green
            msg += str(errors + warnings)

        msg += '</tr>'
    
    msg += '</table></p>'
    
    # Changes.
    chgFn = os.path.join(buildDir, 'changes.html')
    if os.path.exists(chgFn):
        if count_word('<li>', file(chgFn).read()):
            msg += '<p><b>Commits</b></p>' + file(chgFn, 'rt').read()
        
    # Enclose it in a CDATA block if needed.
    if encoded: return '<![CDATA[' + msg + ']]>'    
    return msg
    

def update_changes(fromTag=None, toTag=None, debChanges=False):
    """Generates the list of commits for the latest build."""
    if debChanges:
        # Make sure we have the latest changes.
        git_pull()
        
        # Use the apt repo for determining fromTag.
        os.system('dpkg --print-architecture > debarch.tmp')
        arch = file('debarch.tmp', 'rt').read().strip()
        os.remove('debarch.tmp')
        debs = aptrepo_by_time(arch)
        
        biggest = 0
        for deb in debs:
            number = int(deb[deb.find('-build')+6 : deb.find('_'+arch)])
            biggest = max(biggest, number)
        
        fromTag = 'build' + str(biggest)
        toTag = 'master' # Everything up to now.
    else:
        # Determine automatically?
        if fromTag is None or toTag is None:
            builds = builds_by_time()
            if len(builds) < 2: return
            fromTag = builds[1][1]
            toTag = builds[0][1]

    # Generate a changelog.
    if not debChanges:
        buildDir = os.path.join(builder.config.EVENT_DIR, toTag)
        fn = os.path.join(buildDir, 'changes.html')
        changes = file(fn, 'wt')
        print >> changes, '<ol>'
    else:
        buildDir = builder.config.EVENT_DIR
    
    tmpName = os.path.abspath(os.path.join(buildDir, 'ctmp'))
    
    format = '{{{{li}}}}{{{{b}}}}[[subjectline]]%s[[/subjectline]]{{{{/b}}}}' + \
             '{{{{br/}}}}by {{{{i}}}}%an{{{{/i}}}} on ' + \
             '%ai ' + \
             '{{{{a href=\\"http://deng.git.sourceforge.net/git/gitweb.cgi?' + \
             'p=deng/deng;a=commit;h=%H\\"}}}}(show in repository){{{{/a}}}}' + \
             '{{{{blockquote}}}}%b{{{{/blockquote}}}}'
    os.system("git log %s..%s --format=\"%s\" >> %s" % (fromTag, toTag, format, tmpName))

    logText = unicode(file(tmpName, 'rt').read(), 'utf-8')
    logText = logText.replace(u'ä', u'&auml;')
    logText = logText.encode('utf-8')
    logText = logText.replace('<', '&lt;')
    logText = logText.replace('>', '&gt;')
    logText = logText.replace('{{{{', '<')
    logText = logText.replace('}}}}', '>')
    
    # Check that the subject lines are not too long.
    MAX_SUBJECT = 100
    pos = 0
    changeEntries = []
    while True:
        pos = logText.find('[[subjectline]]', pos)
        if pos < 0: break
        end = logText.find('[[/subjectline]]', pos)
        
        subject = logText[pos+15:end]    
        extra = ''
        if len(collated(subject)) > MAX_SUBJECT:
            extra = '...' + subject[MAX_SUBJECT:] + ' '
            subject = subject[:MAX_SUBJECT] + '...'
        else:
            # If there is a single dot at the end of the subject, remove it.
            if subject[-1] == '.' and subject[-2] != '.':
                subject = subject[:-1]

        if subject not in changeEntries:
            changeEntries.append(subject)
        
        # Do the replace.
        logText = logText[:pos] + subject + logText[end+16:]
        
        if len(extra):
            # Place the extra bit in the blockquote.
            bq = logText.find('<blockquote>', pos)
            logText = logText[:bq+12] + extra + logText[bq+12:]            
    
    if not debChanges:
        logText = logText.replace('\n\n', '<br/><br/>').replace('\n', ' ').replace('</blockquote><br/>', '</blockquote>')
        print >> changes, logText

    if not debChanges:
        print >> changes, '</ol>'
        changes.close()
    else:
        # Append the changes to the debian package changelog.
        os.chdir(os.path.join(builder.config.DISTRIB_DIR, 'linux'))
        
        # First we need to update the version.
        build_version.find_version()
        debVersion = build_version.DOOMSDAY_VERSION_FULL_PLAIN + '-' + todays_build_tag()
        
        # Always make one entry.
        print 'Marking new version...'
        msg = 'New release: unstable ' + todays_build_tag() + '.'
        os.system("dch --check-dirname-level 0 -v %s \"%s\"" % (debVersion, msg))       

        for ch in changeEntries:
            # Quote it for the command line.
            qch = ch.replace('"', '\\"').replace('!', '\\!')
            print ' *', qch
            os.system("dch --check-dirname-level 0 -a \"%s\"" % qch)

    os.remove(tmpName)
           

def create_build_event():
    """Creates and tags a new build for with today's number."""
    print 'Creating a new build event.'
    git_pull()

    # Identifier/tag for today's build.
    todaysBuild = todays_build_tag()
    
    # Tag the source with the build identifier.
    git_tag(todaysBuild)
    
    prevBuild = find_newest_build()['tag']
    print 'The previous build is:', prevBuild
    
    if prevBuild == todaysBuild:
        prevBuild = ''
    
    buildDir = os.path.join(builder.config.EVENT_DIR, todaysBuild)

    # Make sure we have a clean directory for this build.
    if os.path.exists(buildDir):
        # Kill it and recreate.
        shutil.rmtree(buildDir, True)
    os.mkdir(buildDir)

    if prevBuild:
        update_changes(prevBuild, todaysBuild)


def todays_platform_release():
    """Build today's release for the current platform."""
    print "Building today's build."
    git_pull()
    git_checkout(todays_build_tag())
    
    os.chdir(builder.config.DISTRIB_DIR)
    # We'll copy the new files to the build dir.
    existingFiles = os.listdir('releases')    
    
    print 'platform_release.py...'
    os.system("python platform_release.py > %s 2> %s" % ('buildlog.txt', 'builderrors.txt'))
    
    currentFiles = os.listdir('releases')
    for n in existingFiles:
        currentFiles.remove(n)
        
    for n in currentFiles:
        # Copy any new files.
        remote_copy(os.path.join('releases', n),
                    os.path.join(builder.config.EVENT_DIR, todays_build_tag(), n))

        if builder.config.APT_REPO_DIR:
            # Copy also to the appropriate apt directory.
            arch = 'i386'
            if '_amd64' in n: arch = 'amd64'
            remote_copy(os.path.join('releases', n),
                        os.path.join(builder.config.APT_REPO_DIR, 'dists/unstable/main/binary-%s' % arch, n))
                                 
    # Also the build log.
    remote_copy('buildlog.txt', os.path.join(builder.config.EVENT_DIR, todays_build_tag(), 
        'doomsday-out-%s-%s.txt' % (sys.platform, platform.architecture()[0])))
    remote_copy('builderrors.txt', os.path.join(builder.config.EVENT_DIR, todays_build_tag(), 
        'doomsday-err-%s-%s.txt' % (sys.platform, platform.architecture()[0])))
                                             
    git_checkout('master')


def write_index_html(tag):
    f = file(os.path.join(builder.config.EVENT_DIR, tag, 'index.html'), 'wt')
    print >> f, "<html>"
    print >> f, "<head><title>Build %s</title></head>" % tag[5:]
    print >> f, "<body>"
    print >> f, "<h1>Build %s</h1>" % tag[5:]
    print >> f, html_build_description(tag, False)
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
        time.gmtime(find_newest_build()['time']))
    print >> out, '<generator>dengBot</generator>'
    print >> out, '<ttl>180</ttl>' # 3 hours
    
    for timestamp, tag in builds_by_time():
        print >> out, '<item>'
        print >> out, '<title>Build %s</title>' % tag[5:]
        print >> out, '<link>%s/%s/</link>' % (builder.config.BUILD_URI, tag)
        print >> out, '<author>skyjake@users.sourceforge.net (skyjake)</author>'
        print >> out, '<pubDate>%s</pubDate>' % time.strftime(builder.config.RFC_TIME, time.gmtime(timestamp))
        print >> out, '<atom:summary>%s</atom:summary>' % text_build_summary(tag)
        print >> out, '<description>%s</description>' % html_build_description(tag)
        print >> out, '<guid isPermaLink="false">%s</guid>' % tag
        print >> out, '</item>'
        
        write_index_html(tag)
    
    # Close.
    print >> out, '</channel>'
    print >> out, '</rss>'


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
    for bld in find_old_builds(threshold):
        print bld['tag']
        shutil.rmtree(os.path.join(builder.config.EVENT_DIR, bld['tag']))  
        
    print 'Purge done.'


def dir_cleanup():
    """Purges empty build directories from the event directory."""
    print 'Event directory cleanup starting...'
    for bp in find_empty_events():
        print 'Deleting', bp
        os.rmdir(bp)
    print 'Cleanup done.'


def update_debian_changelog():
    """Updates the Debian changelog at (distrib)/debian/changelog."""
    # Update debian changelog.
    update_changes(None, None, True)


def show_help():
    """Prints a description of each command."""
    sortedCommands = commands.keys()
    sortedCommands.sort()
    for cmd in sortedCommands:
        if commands[cmd].__doc__:
            print "%-17s " % (cmd + ":") + commands[cmd].__doc__
        else:
            print cmd
    

commands = {
    'create': create_build_event,
    'platform_release': todays_platform_release,
    'feed': update_feed,
    'apt': rebuild_apt_repository,
    'changes': update_changes,
    'debchanges': update_debian_changelog,
    'purge': purge_obsolete,
    'cleanup': dir_cleanup,
    'help': show_help
}

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print 'The arguments must be: (command) [args]'
        sortedCommands = commands.keys()
        sortedCommands.sort()
        print 'Commands:', string.join(sortedCommands)
        print 'Arguments:'
        print '--distrib  Doomsday distrib directory'
        print '--events   Event directory (builds are stored here in subdirs)'
        print '--apt      Apt repository'
        sys.exit(1)

    if sys.argv[1] not in commands:
        print 'Unknown command:', sys.argv[1]
        sys.exit(1)

    commands[sys.argv[1]]()
