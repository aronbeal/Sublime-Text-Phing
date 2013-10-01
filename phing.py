import sublime, sublime_plugin
from sys import stdout, exc_info
from subprocess import call, PIPE, STDOUT, Popen
import re, os
from time import time, sleep
import xml.parsers.expat
from glob import glob

def which(name, flags=os.X_OK):
    """Search PATH for executable files with the given name.

    On newer versions of MS-Windows, the PATHEXT environment variable will be
    set to the list of file extensions for files considered executable. This
    will normally include things like ".EXE". This fuction will also find files
    with the given name ending with any of these extensions.

    On MS-Windows the only flag that has any meaning is os.F_OK. Any other
    flags will be ignored.

    @type name: C{str}
    @param name: The name for which to search.

    @type flags: C{int}
    @param flags: Arguments to L{os.access}.

    @rtype: C{list}
    @param: A list of the full paths to files found, in the
    order in which they were found.
    """
    result = []
    exts = filter(None, os.environ.get('PATHEXT', '').split(os.pathsep))
    path = os.environ.get('PATH', None)
    if path is None:
        return []
    for p in os.environ.get('PATH', '').split(os.pathsep):
        p = os.path.join(p, name)
        if os.access(p, flags):
            result.append(p)
        for e in exts:
            pext = p + e
            if os.access(pext, flags):
                result.append(pext)
    return result

class PhingCommand(sublime_plugin.WindowCommand):
    """
        Executes phing within Sublime Text, and allows
        the user to choose from a list of phing targets
    """
    def run(self):
        """ Command main method """
        print('Executing "phing" command');
        phing_candidates = which('phing')
        if len(phing_candidates) == 0:
            sublime.error_message("Phing does not appear to be installed on this system.")
            return
        self.phing = os.path.realpath(phing_candidates[0].strip())        
        if not os.path.exists(self.phing) or not os.access(self.phing, os.X_OK):
            sublime.error_message("Phing does not appear to be installed on this system.")
        
        """ Test xml for valid syntax """
        project_data = self.window.project_data()
        self.project_root = os.path.expanduser(project_data['folders'][0]['path'])
        try:
            if not os.path.isfile("%s/build.xml" % self.project_root):
                sublime.error_message("Project build.xml file not found.  Cannot run phing")
                return
            parser = xml.parsers.expat.ParserCreate()
            parser.ParseFile(open("%s/build.xml" % self.project_root, 'r'))
        except (Exception) as e:
            print("Could not open build.xml file: ")

        """ Invoke phing on the build file in the project root.  
        Use the returned phing target list to build a quick panel
        for the user to choose the desired one. """
        try:
            p = Popen([self.phing, '-list','-logger', 'phing.listener.DefaultLogger'],
                cwd=self.project_root, stdout=PIPE, stderr=STDOUT)
            output = p.communicate(None)
            if(output is None):
                sublime.error_message("Error communicating with code evaluation process")
                return
            if type(output) is not str:    
                output = output[0].decode()
            #print ("Output: ", output)
        except (IOError, Exception) as e:
            sublime.error_message("Error({0}): {1}".format(e.errno, e.strerror))
            return
        main_regex = re.compile('Main targets:\n?-{1,}\n?(.*)Subtargets:\n?-{1,}\n?(.*)', re.DOTALL)
        matches = re.search(main_regex, output)
        if(matches is None):
            return

        #A phing "main target" is one that has a description
        #We use phing to sort these out, and then remove
        #all the targets that are listed from a separate buildfile
        main_output = re.split("\n", matches.group(1))
        self.targets = []
        for index, item in enumerate(main_output):
            line = item.strip()
            if line == '':
                continue
            output = re.split("\s{2,}", line)
            #output length will either be 0 or > 2
            #because main targets always have a description
            cmd = output.pop(0)
            if(re.search("\.", cmd) is not None):
                continue
            self.targets.append([cmd, '  '.join(output)])

        #Don't care about sub targets for now.
        self.targets.sort()
        self.window.show_quick_panel(self.targets, self.on_target)

    def on_target(self, index):
        """
            Executes when an entry is chosen from the
            Sublime Text quick panel drop-down
        """
        if index != -1:
            target = self.targets[index][0]
            if not isinstance(target, str):
                sublime.error_dialog("Error: Could not determine target")
                return
            try:
                print ("running target " + target)
                process_start_time = time()
                process_end_time = process_start_time + 30 #max 60 seconds
                p = Popen([self.phing, '-logger', 'phing.listener.DefaultLogger', target],
                    cwd=self.project_root, stdout=PIPE, stderr=STDOUT)
                output = p.communicate(None)[0]
                if type(output) is str:
                    print (output)
                else:
                    print (output.decode())

            except (IOError, Exception) as e:
                sublime.error_message("Error({0}): {1}".format(e.errno, e.strerror))
            return
            self.window.run_command("call",
                {"cmd": [self.phing, '-logger',
                    'phing.listener.DefaultLogger',
                    self.targets[index][0]],
                    "working_dir": self.project_root
                }
            )

    def on_done(self, text):
        """ Executes after command completion """
        self.window.show_quick_panel(self.targets, self.on_target)

    def on_cancel(self):
        """ Executes on command cancel """
        print("Cancelled")
