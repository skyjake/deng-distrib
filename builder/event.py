import os, glob, shutil
import build_number
import config
import utils

class Event:
    """Build event. Manages the contents of a single build directory under
    the event directory."""
    
    def __init__(build=None):
        if build is None:
            # Use today's build number.
            self.name = 'build' + build_number.todays_build()
            self.number = int(self.name[5:])
        elif type(build) == int:
            self.name = 'build' + str(build)
            self.number = build
        elif type(build) == str:
            if build[:5] != 'build': 
                raise Exception("Event build name must begin with 'build'")
            self.name = build
            self.number = int(build[5:])
        # Where the build is located.
        self.buildDir = os.path.join(config.EVENT_DIR, self.name)
        
    def tag():
        return self.name
        
    def name():
        return self.name
        
    def number():
        return self.number
        
    def path():
        return self.buildDir
        
    def filePath(fileName):
        return os.path.join(self.buildDir, fileName)
        
    def clean():
        # Make sure we have a clean directory for this build.
        if os.path.exists(self.buildDir):
            # Kill it and recreate.
            shutil.rmtree(self.buildDir, True)
        os.mkdir(self.buildDir)        
        
    def list_package_files():
        files = glob.glob(os.path.join(self.buildDir, '*.dmg')) + \
                glob.glob(os.path.join(self.buildDir, '*.exe')) + \
                glob.glob(os.path.join(self.buildDir, '*.deb'))

        return [os.path.basename(f) for f in files]

    def timestamp():
        """Looks through the files of the build and returns the timestamp
        for the oldest file."""
        oldest = os.stat(self.buildDir).st_ctime

        for fn in os.listdir(self.buildDir):
            t = os.stat(os.path.join(self.buildDir, fn))
            if int(t.st_ctime) < oldest:
                oldest = int(t.st_ctime)

        return oldest        
        
    def text_summary():
        """Composes a textual summary of the event."""
        
        msg = "The build event was started on %s." % (time.strftime(config.RFC_TIME, 
                                                      time.gmtime(self.timestamp())))

        msg += ' It'

        pkgCount = len(self.list_package_files())

        changesName = os.path.join(config.EVENT_DIR, name, 'changes.html')
        commitCount = 0
        if os.path.exists(changesName):
            commitCount = utils.count_word('<li>', file(changesName).read())
        if commitCount:
            msg += " contains %i commits and" % commitCount

        msg += " produced %i installable binary package%s." % \
            (pkgCount, 's' if (pkgCount != 1) else '')

        return msg
        
    def html_description(encoded=True):
        """Composes an HTML build report. Compresses any .txt logs present in 
        the build directory into a combined .txt.gz (one per package)."""
        
        name = self.name
        buildDir = self.buildDir

        msg = '<p>' + self.text_summary() + '</p>'

        # What do we have here?
        files = self.list_package_files()

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
                msg += '<a href="%s/%s/%s">%s</a>' % (config.BUILD_URI, 
                                                      name, binary, binary)

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
                msg += '<td><a href="%s/%s/%s">txt.gz</a>' % (config.BUILD_URI, name, logName)

                # Show a traffic light indicator based on warning and error counts.              
                errors, warnings = utils.count_log_status(logFileName)
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
            if utils.count_word('<li>', file(chgFn).read()):
                msg += '<p><b>Commits</b></p>' + file(chgFn, 'rt').read()

        # Enclose it in a CDATA block if needed.
        if encoded: return '<![CDATA[' + msg + ']]>'    
        return msg


def find_newest_event():
    newest = None
    for fn in os.listdir(config.EVENT_DIR):
        if fn[:5] != 'build': continue
        ev = Event(fn)
        bt = ev.timestamp()
        if newest is None or newest[0] < bt:
            newest = (bt, ev)

    if newest is None:
        return {'event':None, 'tag':None, 'time':time.time()}
    else:
        return {'event':newest[1], 'tag':newest[1].tag(), 'time':newest[0]}


def find_old_events(atLeastSecs):
    """Returns a list of Event instances."""
    result = []
    now = time.time()
    if not os.path.exists(config.EVENT_DIR): return result
    for fn in os.listdir(config.EVENT_DIR):
        if fn[:5] != 'build': continue
        ev = Event(fn)
        if now - ev.timestamp() >= atLeastSecs:
            result.append(ev)
    return result
    

def find_empty_events(baseDir=None):
    """Returns a list of build directory paths."""
    result = []
    if not baseDir: baseDir = config.EVENT_DIR
    print 'Finding empty subdirs in', baseDir
    for fn in os.listdir(baseDir):
        path = os.path.join(baseDir, fn)
        if os.path.isdir(path):
            # Is this an empty directory?
            empty = True
            for c in os.listdir(path):
                if c != '.' and c != '..':
                    empty = False
                    break
            if empty:
                result.append(path)
    return result


def events_by_time():
    builds = []
    for fn in os.listdir(config.EVENT_DIR):
        if fn[:5] == 'build':
            builds.append((build_timestamp(fn), fn, Event(fn)))
    builds.sort()
    builds.reverse()
    return builds

