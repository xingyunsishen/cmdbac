import os, sys
sys.path.append(os.path.join(os.path.dirname(__file__), os.pardir))

import logging
import re
import time
import traceback
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from basedeployer import BaseDeployer
from library.models import *
import utils

## =====================================================================
## LOGGING CONFIGURATION
## =====================================================================
LOG = logging.getLogger()

## =====================================================================
## SETTINGS
## =====================================================================
WAIT_TIME = 15

## =====================================================================
## Drupal DEPLOYER
## =====================================================================
class DrupalDeployer(BaseDeployer):
    def __init__(self, repo, database, deploy_id, database_config = None, runtime = None):
        BaseDeployer.__init__(self, repo, database, deploy_id, database_config, runtime)
        if database_config == None:
            self.database_config['name'] = 'drupal_app' + str(deploy_id)
        self.main_filename = None

        ## HACK
        ## self.database_config['password'] = ''
    ## DEF

    def configure_settings(self, path):
        pass
    ## DEF
    
    def get_main_url(self):
        return 'http://127.0.0.1:{}/'.format(self.port)
    ## DEF

    def configure_profile(self):
        from pyvirtualdisplay import Display
        display = Display(visible=0, size=(800, 600))
        display.start()

        browser = webdriver.PhantomJS()
        browser.get('http://127.0.0.1:8181/install.php')
    
        # select profile
        try:
            WebDriverWait(browser, WAIT_TIME).until(EC.presence_of_element_located((By.ID, 'edit-profile--4')))
            browser.find_element_by_id('edit-profile--4').click()
            browser.find_element_by_tag_name('form').submit()
            print 'Selecting profile ...'
        except:
            traceback.print_exc()
            pass

        # select locale
        try:
            WebDriverWait(browser, WAIT_TIME).until(EC.presence_of_element_located((By.TAG_NAME, 'form')))
            browser.find_element_by_tag_name('form').submit()
            print 'Selecting locale ...'
        except:
            traceback.print_exc()
            pass
        
        # configure database
        try:
            WebDriverWait(browser, WAIT_TIME).until(EC.presence_of_element_located((By.ID, 'edit-mysql-database')))
            browser.find_element_by_id('edit-mysql-database').send_keys(self.database_config['name'])
            browser.find_element_by_id('edit-mysql-username').send_keys(self.database_config['username'])
            browser.find_element_by_id('edit-mysql-password').send_keys(self.database_config['password'])
            browser.find_element_by_class_name('fieldset-title').click()
        except:
            traceback.print_exc()
            pass
        
        browser.save_screenshot('/tmp/screenshot.png')
        try:
            WebDriverWait(browser, WAIT_TIME).until(EC.presence_of_element_located((By.ID, 'edit-mysql-host')))
            browser.find_element_by_id('edit-mysql-host').clear()
            browser.find_element_by_id('edit-mysql-host').send_keys(self.database_config['host'])
            browser.find_element_by_id('edit-mysql-port').send_keys(self.database_config['port'])
            browser.find_element_by_tag_name('form').submit()
            print 'Configuring database ...'
        except:
            traceback.print_exc()
            pass

        browser.save_screenshot('/tmp/screenshot.png')
        # configure site
        try:
            WebDriverWait(browser, WAIT_TIME).until(EC.presence_of_element_located((By.ID, 'edit-site-name')))
            browser.find_element_by_id('edit-site-name').send_keys(self.database_config['name'])
            browser.find_element_by_id('edit-site-mail').send_keys('admin@test.com')
            browser.find_element_by_id('edit-account-name').send_keys('admin')
            browser.find_element_by_id('edit-account-pass-pass1').send_keys('admin')
            browser.find_element_by_id('edit-account-pass-pass2').send_keys('admin')
            browser.find_element_by_tag_name('form').submit()
            print 'Configuring site ...'
        except:
            traceback.print_exc()
            pass

        browser.save_screenshot('/tmp/screenshot.png')
        # feature set
        try:
            WebDriverWait(browser, WAIT_TIME).until(EC.presence_of_element_located((By.CLASS_NAME, 'form-checkbox')))
            for option in browser.find_elements_by_class_name('form-checkbox'):
                if not option.is_selected():
                    option.click()
            browser.find_element_by_tag_name('form').submit()
            print 'Configuring feature set ...'
        except:
            traceback.print_exc()
            pass

        browser.save_screenshot('/tmp/screenshot.png')
        # layout
        try:
            WebDriverWait(browser, WAIT_TIME).until(EC.presence_of_element_located((By.TAG_NAME, 'form')))
            browser.find_element_by_tag_name('form').submit()
            print 'Configuring layout ...'
        except:
            traceback.print_exc()
            pass

        browser.save_screenshot('/tmp/screenshot.png')
        # general user
        try:
            WebDriverWait(browser, WAIT_TIME).until(EC.presence_of_element_located((By.ID, 'edit-name')))
            browser.find_element_by_id('edit-name').send_keys('test')
            browser.find_element_by_id('edit-mail').send_keys('test@test.com')
            try:
                browser.find_element_by_id('edit-pass-pass1').send_keys('test')
                browser.find_element_by_id('edit-pass-pass2').send_keys('test')
            except:
                pass
            browser.find_element_by_tag_name('form').submit()
            print 'Configuring general user ...'
        except:
            traceback.print_exc()
            pass

        time.sleep(WAIT_TIME * 2)
        browser.save_screenshot('/tmp/screenshot.png')
        browser.quit()
        display.stop()
        ## DEF

    def sync_server(self, path):
        LOG.info('Syncing server ...')
        utils.run_command_async('drush ss', input=['0.0.0.0\n', '{}\n'.format(self.port)], cwd=path)

        time.sleep(WAIT_TIME)

        try:
            self.configure_profile()
        except:
            traceback.print_exc()
    ## DEF

    def run_server(self, path):
        pass
    ## DEF

    def get_runtime(self):
        out = utils.run_command('php -v')
        return {
            'executable': 'php',
            'version': out[1].split('\n')[0].split()[1]
        }
    ## DEF

    def try_deploy(self, deploy_path):
        LOG.info('Configuring settings ...')
        self.kill_server()
        self.clear_database()
        self.configure_settings(deploy_path)
        self.runtime = self.get_runtime()
        LOG.info(self.runtime)

        self.attempt.database = self.get_database()
        LOG.info('Database: ' + self.attempt.database.name)

        self.sync_server(deploy_path)

        return ATTEMPT_STATUS_SUCCESS

        self.run_server(deploy_path)
        time.sleep(5)
        
        attemptStatus = self.check_server()

        return attemptStatus
    ## DEF
    
    def deploy_repo_attempt(self, deploy_path):
        package_jsons = utils.search_file(deploy_path, 'install.php')
        base_dir = sorted([os.path.dirname(package_json) for package_json in package_jsons])[0]

        # TODO : delete robots.txt

        self.setting_path = base_dir

        print self.setting_path

        return self.try_deploy(base_dir)
    ## DEF
    
## CLASS