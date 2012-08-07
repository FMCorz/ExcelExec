# -*- coding: utf-8 -*-

"""
White Spaces

Plugin for Sublime Text 2 to execute a command and redirect its output into a view

Copyright (c) 2012 Frédéric Massart - FMCorz.net

Licensed under The MIT License
Redistributions of files must retain the above copyright notice.

http://github.com/FMCorz/ExcelExec
"""

import sublime, sublime_plugin
import os, sys
import thread
import subprocess, shlex
import functools
import datetime, time
import math

class ProcessListener(object):
    def on_data(self, proc, data):
        pass

    def on_finished(self, proc):
        pass

# Encapsulates subprocess.Popen, forwarding stdout to a supplied
# ProcessListener (on a separate thread)
class AsyncProcess(object):

    cmd = None
    process_start = None
    process_end = None

    def __init__(self, arg_list, env, listener, working_dir = None, path="", shell=False):

        self.listener = listener
        self.killed = False
        self.cmd = arg_list
        self.working_dir = working_dir

        # Hide the console window on Windows
        startupinfo = None
        if os.name == "nt":
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

        # Set temporary PATH to locate executable in arg_list
        if path:
            old_path = os.environ["PATH"]
            # The user decides in the build system whether he wants to append $PATH
            # or tuck it at the front: "$PATH;C:\\new\\path", "C:\\new\\path;$PATH"
            os.environ["PATH"] = os.path.expandvars(path).encode(sys.getfilesystemencoding())

        proc_env = os.environ.copy()
        proc_env.update(env)
        for k, v in proc_env.iteritems():
            proc_env[k] = os.path.expandvars(v).encode(sys.getfilesystemencoding())

        self.listener.on_start(self)
        self.process_start = datetime.datetime.now()
        self.proc = subprocess.Popen(arg_list, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, startupinfo=startupinfo, env=proc_env,
            shell=shell, cwd=working_dir)

        if path:
            os.environ["PATH"] = old_path

        if self.proc.stdout:
            thread.start_new_thread(self.read_stdout, ())

        if self.proc.stderr:
            thread.start_new_thread(self.read_stderr, ())

    def elapsed(self):
        process_end = self.process_end
        if process_end == None:
            process_end = datetime.datetime.now()
        return process_end - self.process_start

    def kill(self):
        if not self.killed:
            self.killed = True
            self.proc.kill()
            self.process_end = datetime.datetime.now()
            self.listener = None

    def poll(self):
        return self.proc.poll() == None

    def read_stdout(self):
        while True:
            data = os.read(self.proc.stdout.fileno(), 2**15)

            if data != "":
                if self.listener:
                    self.listener.on_data(self, data)
            else:
                self.proc.stdout.close()
                self.process_end = datetime.datetime.now()
                if self.listener:
                    self.listener.on_finished(self)
                break

    def read_stderr(self):
        while True:
            data = os.read(self.proc.stderr.fileno(), 2**15)

            if data != "":
                if self.listener:
                    self.listener.on_data(self, data)
            else:
                self.proc.stderr.close()
                break

class ExcelExecWhatCommand(sublime_plugin.WindowCommand):
    def run(self, **kwargs):
        self.kwargs = kwargs
        sublime.active_window().show_input_panel('Command to execute:', '', self.do, None, None)

    def do(self, command):
        kwargs = self.kwargs
        kwargs['cmd'] = command
        sublime.active_window().run_command('excel_exec', kwargs)

class ExcelExecCommand(sublime_plugin.WindowCommand, ProcessListener):
    commands = {}
    def run(self, cmd = [], working_dir = None, encoding = "utf-8", env = {},
            quiet = None, kill = False, inline = False, **kwargs):

        # Cleans the existing ended commands
        for k, c in self.commands.items():
            if kill != False and k == kill and c.proc != None:
                print 'Excel Exec: Killing process'
                c.proc.kill()
            if c.proc == None:
                del self.commands[k]

        if cmd == '' or cmd == []:
            return

        # Default the to the current files directory if no working directory was given
        if ((working_dir == None or working_dir == "") and self.window.active_view() and
                    self.window.active_view().file_name() != None):
            working_dir = os.path.dirname(self.window.active_view().file_name())

        # View in a new window
        if not inline or not self.window.active_view() or self.window.active_view().is_read_only():
            view = self.window.new_file()
            view.set_scratch(True)
            view.set_name((type(cmd) == list and " ".join(cmd)) or cmd)
            mode = 'new'
        # View inline
        else:
            view = self.window.active_view()
            mode = 'inline'

        key = time.time()
        view.settings().set("excel_exec", key)

        # Create new process
        ee = ExcelExec()
        self.commands[key] = ee
        ee.run(cmd = cmd, working_dir = working_dir, encoding = encoding, env = env, quiet = quiet,
                kill = kill, view = view, mode = mode, **kwargs)

class ExcelExec(ProcessListener):

    def run(self, cmd = [], working_dir = None, encoding = "utf-8", env = {}, quiet = None,
            kill = False, view = None, mode = 'new', **kwargs):

        self.view = view
        self.mode = mode
        if self.view == None:
            return

        if type(cmd) != list:
            cmd = shlex.split(str(cmd))

        self.encoding = encoding

        if quiet == None:
            quiet == (self.mode != 'new' or False)
        self.quiet = quiet

        self.proc = None
        print "Excel Exec: Running " + " ".join(cmd)

        merged_env = env.copy()

        # Change to the working dir, rather than spawning the process with it,
        # so that emitted working dir relative path names make sense
        if working_dir == None:
            working_dir = os.getcwd()

        err_type = OSError
        if os.name == "nt":
            err_type = WindowsError

        try:
            # Forward kwargs to AsyncProcess
            self.proc = AsyncProcess(cmd, merged_env, self, working_dir = working_dir, **kwargs)
        except err_type as e:
            self.append_data(None, str(e) + "\n")
            if not self.quiet:
                self.append_data(None, "\n[Execution stopped! Time elapsed %s]" % (self.elapsed_nice(proc.elapsed())))

            # Just in case
            self.view.end_edit(self.edit)

    def append_data(self, proc, data):
        if proc != self.proc:
            if proc:
                proc.kill()
            return

        try:
            str = data.decode(self.encoding)
        except:
            str = "[Decode error - output not " + self.encoding + "]"
            proc = None

        # Normalize newlines, Sublime Text always uses a single \n separator
        # in memory.
        str = str.replace('\r\n', '\n').replace('\r', '\n')

        selection_was_at_end = (len(self.view.sel()) == 1
            and self.view.sel()[0] == sublime.Region(self.view.size()))
        self.view.set_read_only(False)

        try:
            if self.mode != 'new':
                edit = self.edit
            else:
                edit = self.view.begin_edit()

            if self.mode != 'new':
                regions = self.view.sel()
                for region in regions:
                    self.view.erase(edit, region)
                    self.view.insert(edit, region.begin(), str)
            else:
                self.view.insert(edit, self.view.size(), str)

            if selection_was_at_end and self.mode == 'new':
                self.view.show(self.view.size())

        finally:

            if self.mode == 'new':
                self.view.end_edit(edit)

            if self.view.is_scratch():
                self.view.set_read_only(True)

    def start(self, proc):
        # Creates the edit
        if self.mode != 'new':
            self.edit = self.view.begin_edit()

        if not self.quiet:
            self.append_data(proc, '$ ' + ' '.join(proc.cmd) + '\n')
            self.append_data(proc, '%s\n\n' % proc.working_dir)

    def finish(self, proc):
        if not self.quiet:
            self.append_data(proc, "\n[Time elapsed %s]" % (self.elapsed_nice(proc.elapsed())))

        # Closes the edit
        if self.mode != 'new':
            self.view.end_edit(self.edit)

        # Release the process
        self.proc = None
        self.edit = None

    def elapsed_nice(self, td):
        totalseconds = (td.seconds + td.days * 24 * 3600) + ((0. + td.microseconds) / 10**6)
        seconds = math.floor(totalseconds)
        micro = math.floor((totalseconds - seconds) * 10**6)
        if seconds > 59:
            mins = math.floor(seconds / 60)
            secs = seconds - (mins * 60)
            txt = '%d min %d sec %d ms' % (mins, secs, micro)
        else:
            txt = '%d sec %d ms' % (seconds, micro)
        return txt

    def on_data(self, proc, data):
        sublime.set_timeout(functools.partial(self.append_data, proc, data), 0)

    def on_start(self, proc):
        sublime.set_timeout(functools.partial(self.start, proc), 0)

    def on_finished(self, proc):
        sublime.set_timeout(functools.partial(self.finish, proc), 0)

class ExcelExecEvent(sublime_plugin.EventListener):

    def on_close(self, view):
        key = view.settings().get('excel_exec')
        if key != None and sublime.active_window():
            sublime.active_window().run_command('excel_exec', { 'kill': key } )
