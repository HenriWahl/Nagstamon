#!/usr/bin/env python
# -*- coding: utf-8 -*-

""" Experimental script for automated build
"""

from optparse import OptionParser
import platform
import os
import sys
import shutil

if platform.system() == 'Windows':
    try:
        import win32api
    except:
        print
        print "pyinstaller needs pywin32. Get it at http://sourceforge.net/projects/pywin32."
        print
        sys.exit()

INSTALLER_DIR = '../build/installer%s' % os.path.sep
DEFAULT_LOCATION = os.path.join('..', 'Nagstamon')
BUILD_HELPERS = 'helpers'
REQUIRED_FILES = BUILD_HELPERS + os.sep + 'required_files.txt'

def execute_script_lines(script_lines, opt_dict):
    for line in script_lines:
        command = line % opt_dict
        print 'Running: %s' % command
        os.system(command)

def get_opt_dict(options):
    opt_dict = vars(options)
    opt_dict.update({ 'installer': INSTALLER_DIR, 'default_location': DEFAULT_LOCATION })
    return opt_dict

def get_required_files(location, required_file_list):
    all_files = []
    for dir_path, dir_list, file_list in os.walk(location):
        for file_name in required_file_list:
            if file_name in file_list:
                all_files.append(os.path.join(dir_path, file_name))
    return all_files

def get_all_files(location):
    for dir_path, dir_list, file_list in os.walk(location):
        for file_name in file_list:
            yield os.path.join(dir_path, file_name)


def winmain():
    parser = OptionParser()
    parser.add_option('-g', '--gtk', dest='gtk', help='GTK+ location', default=os.environ['ProgramFiles']+'\\Gtk+')
    parser.add_option('-s', '--iscc', dest='iscc', help='ISCC executable file', default=os.environ['ProgramFiles']+'\\Inno Setup 5\\ISCC')
    parser.add_option('-t', '--target', dest='target', help='Target application directory',
                                                        default='.')
    parser.add_option('-f', '--file', dest='file', help='Nagstamon exec script', default='')
    parser.add_option('-i', '--iss', dest='iss', help='Inno setup installer file', default='nagstamon.iss')
    parser.add_option('-p', '--pyinstaller', dest='pyinstaller', help='PyInstaller location', default='helpers\\pyinstaller-2.0')
    parser.add_option('-o', '--omit-gtk', action='store_true', dest='omit_gtk', default=False,
                                    help="Omits copying of required gtk files to application directory")
    options, args = parser.parse_args()

    if not options.file:
        options.file = '%s\\nagstamon.py' % options.target

    opt_dict = get_opt_dict(options)

    opt_dict.update({ 'resources_dir': '..\\Nagstamon\\Nagstamon\\resources' })
    opt_dict.update({ 'icon': opt_dict['resources_dir'] + '\\nagstamon.ico' })
    opt_dict.update({ 'dist': 'dist\\nagstamon' })
    # useless and disturbing DLLs - lousy workaround, pyinstaller 1.5 seems to do it (mostly) itself
    opt_dict.update({ 'exclude_dlls':'USP10.DLL' })
    # arguments for xcopying gtk windows theme stuff
    opt_dict.update({ 'gtk-windows-theme':BUILD_HELPERS + os.sep + 'gtk-windows-theme' + os.sep + '*.*'})

    script_lines = [
        '%(pyinstaller)s\pyinstaller.py --noconfirm nagstamon.spec',
        'xcopy "%(resources_dir)s" dist\\nagstamon\\resources /y /e /i /h /EXCLUDE:helpers\excludelist.txt',
        'cd %(dist)s & del /q /f %(exclude_dlls)s & cd ..'
    ]

    execute_script_lines(script_lines, opt_dict)

    if not options.omit_gtk:
        dist_location = ['dist', 'nagstamon']
        if os.path.isfile(REQUIRED_FILES):
            required_file_list = [x.strip() for x in open(REQUIRED_FILES).readlines()]
            for required_file in get_required_files(opt_dict['gtk'], required_file_list):
                len_gtk_path = len(opt_dict['gtk'].split(os.path.sep))
                dest_path = os.path.abspath(os.path.join(*dist_location + \
                                                         required_file.split(os.path.sep)[len_gtk_path:]))
                if not os.path.exists(dest_path):
                    dir_name = os.path.dirname(dest_path)
                    if not os.path.isdir(dir_name):
                        os.makedirs(dir_name)
                    shutil.copyfile(required_file, dest_path)

        # copy gtk windows theme stuff to nagstamon directory
        os.system('xcopy %(gtk-windows-theme)s dist\\nagstamon /y /e /i /h /EXCLUDE:helpers\excludelist.txt' % opt_dict)


        if os.path.exists(os.path.join(*dist_location)):
            iss_location = '%(target)s\\%(installer)s\\windows\\%(iss)s' % opt_dict
            if os.path.isfile(iss_location):
                iss_file = open(iss_location)
                iss_temp_file = open('nagstamon.iss', 'w')
                iconfile_entry = 'SetupIconFile'
                for line in iss_file:
                    if line.startswith(iconfile_entry):
                       iss_temp_file.write('%s=%s\n' % (iconfile_entry,
                                              os.path.abspath(os.path.join(*dist_location + ['resources', 'nagstamon.ico']))))
                    else:
                        iss_temp_file.write(line)
                    if line.startswith('[Files]'):
                        break
                iss_file.close()
                for file_name in get_all_files(os.path.join(*dist_location)):
                    relative_location = os.path.dirname(file_name.split(dist_location[-1], 1)[-1]).rstrip('\\')
                    iss_temp_file.write('Source: %s; DestDir: {app}%s\n' % (file_name, relative_location))
                iss_temp_file.close()
                execute_script_lines(['"%(iscc)s" nagstamon.iss'], opt_dict)
            else:
                print 'Missing "%s" file' % iss_location


def debmain():
    parser = OptionParser()
    parser.add_option('-t', '--target', dest='target', help='Target application directory', default=DEFAULT_LOCATION)
    parser.add_option('-d', '--debian', dest='debian', help='"debian" directory location', default='')
    options, args = parser.parse_args()
    if not options.debian:
        options.debian = '%s/%sdebian' % (options.target, INSTALLER_DIR)
    else:
        options.debian = '%s/debian' % options.debian
    options.debian = os.path.abspath(options.debian)

    print options.debian
    print options.target

    if not os.path.isfile('%s/rules' % (options.debian)):
        print 'Missing required "rules" file in "%s" directory' % options.debian
        return
    execute_script_lines(['cd %(target)s; ln -s %(debian)s; chmod 755 %(debian)s/rules; fakeroot debian/rules build; \
fakeroot debian/rules binary; fakeroot debian/rules clean; rm debian'],
                         get_opt_dict(options))

    print "\nFind .deb output in ../.\n"


DISTS = {
    'debian': debmain,
    'Ubuntu': debmain
}

if __name__ == '__main__':
    if platform.system() == 'Windows':
        winmain()
    else:
        dist = platform.dist()[0]
        if dist in DISTS:
            DISTS[dist]()
        else:
            print 'Your system is not supported for automated build yet'
