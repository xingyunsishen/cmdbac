#!/usr/bin/env python
import os, sys
sys.path.append(os.path.join(os.path.dirname(__file__), os.pardir))
sys.path.append(os.path.join(os.path.dirname(__file__), os.pardir, os.pardir))

import traceback
# TODO : Do not directly use shutil
import shutil

from run import run_command
from file import cd

copied_dir = ['crawler', 'db_webcrawler', 'core', 'secrets']
vagrant_dir = os.path.join(os.path.dirname(__file__), os.pardir, os.pardir, 'vagrant')
copied_files = []

def vagrant_setup():
    print ('Setuping Vagrant ...')

    ## Copy files
    for new_dir in copied_dir:
        old_dir = os.path.join(os.path.dirname(__file__), os.pardir, os.pardir, new_dir)
        shutil.copytree(old_dir, os.path.join(vagrant_dir, new_dir))

    # run_command('{} && {}'.format(cd(vagrant_dir), 'vagrant up'))

def vagrant_clear():
    # Delete files
    for new_dir in copied_dir:
        try:
            shutil.rmtree(os.path.join(vagrant_dir, new_dir))
        except:
            pass

    # run_command('{} && {}'.format(cd(vagrant_dir), 'vagrant halt'))

def set_vagrant_database():
    settings_file = os.path.join(vagrant_dir, "db_webcrawler", "settings.py")
    settings = open(settings_file).read()
    if "'HOST': 'localhost'" in settings:
        settings = settings.replace("'HOST': 'localhost'", "'HOST': '10.0.2.2'")
        fout = open(settings_file, 'w')
        fout.write(settings)
        fout.flush()
        fout.close()

def unset_vagrant_database():
    settings_file = os.path.join(vagrant_dir, "db_webcrawler", "settings.py")
    settings = open(settings_file).read()
    if "'HOST': '10.0.2.2'" in settings:
        settings = settings.replace("'HOST': 'localhost'", "'HOST': 'localhost'")
        fout = open(settings_file, 'w')
        fout.write(settings)
        fout.flush()
        fout.close()

def vagrant_deploy(repo, database):
    set_vagrant_database()
    out = os.system('{} && {}'.format(
        cd(vagrant_dir),
        'vagrant ssh -c "{}"'.format(
            'python /vagrant/core/scripts/vagrant_deploy.py {} {}'.format(repo, database))))
    unset_vagrant_database()

    return out