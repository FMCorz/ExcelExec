Excel Exec
==========

Plugin for Sublime Text 2 to execute a command and redirect its output into a view.

Usage
-----

The following commands are accessible via the command palette:

- Excel Exec: Execute in this window
- Excel Exec: Execute in a new window

### Window commands

#### excel_exec

Executes a command according to the arguments passed.

	sublime.active_window().run_command('excel_exec', { 'cmd': 'ls' })

#### excel_exec_what

Prompts the user for the command to launch.

	sublime.active_window().run_command('excel_exec_what', { 'inline': False })

Parameters
----------

- `cmd (string|list)`: the command to execute
- `inline (bool)`: if false the command output will be displayed in a new window
- `path (string)`: the environment variable $PATH to use
- `shell (bool)`: if true executes the command through a shell
- `working_dir (string)`: the directory the command has to be executed in
- `encoding (string)`: the encoding of the command output
- `env (dict)`: environment variables to set before the command runs
- `quiet (bool)`: enable display of extra information

Installation
------------

Clone this repository into the Packages directory. If you don't know where it is, enter the following command in the console:

    print sublime.packages_path()

_To access the console press CTRL + `_

Note
----

This plugin is based on the Exec command shipped with Sublime Text.

License
-------

Licensed under the [MIT License](http://www.opensource.org/licenses/mit-license.php)
