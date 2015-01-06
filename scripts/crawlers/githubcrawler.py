import os, sys
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

import time
import json
import re
import urllib2
import logging

from string import Template
from bs4 import BeautifulSoup
from datetime import datetime

from utils import Utils
from basecrawler import BaseCrawler
from crawler.models import *

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "db_webcrawler.settings")
#import django
#django.setup()

## =====================================================================
## LOGGING CONFIGURATION
## =====================================================================

LOG = logging.getLogger(__name__)
LOG_handler = logging.StreamHandler()
LOG_formatter = logging.Formatter(fmt='%(asctime)s [%(funcName)s:%(lineno)03d] %(levelname)-5s: %(message)s',
                                  datefmt='%m-%d-%Y %H:%M:%S')
LOG_handler.setFormatter(LOG_formatter)
LOG.addHandler(LOG_handler)
LOG.setLevel(logging.INFO)

## =====================================================================
## GITHUB CONFIGURATION
## =====================================================================

BASE_URL = "https://github.com/search?utf8=%E2%9C%93&q=${query}+" + \
           "in%3Apath+filename%3A${filename}+" +  \
           "size%3A${size}&" + \
           "type=Code&ref=searchresults"
           
GITHUB_HOST = 'https://github.com/'
API_GITHUB_REPO = 'https://api.github.com/repos/'
API_GITHUB_SLEEP = 1 # seconds

## =====================================================================
## GITHUB CRAWLER
## =====================================================================
class GitHubCrawler(BaseCrawler):
    def __init__(self, crawlerStatus):
        BaseCrawler.__init__(self, crawlerStatus)

        # Basic Search String
        self.template = Template(BASE_URL)

        # model file less than min_size don't use database
        #self.min_size = self.project_type.min_size
        
        # less then 1000 files larger than threshold_size
        #self.max_size = self.project_type.max_size
        #self.cur_size = self.project_type.cur_size
    ## DEF
    
    def loadURL(self, url):
        LOG.info("Retrieving data from %s" % url)
        request = urllib2.Request(url)
        request.add_header('Authorization', 'token %s' % TOKEN)
        response = urllib2.urlopen(request)
        return response
    ## DEF
    
    def nextURL(self):
        # Check whether there is a next url that we need to load
        # from where we left off from our last run
        if not self.crawlerStatus.next_url is None:
            return self.crawlerStatus.next_url
        
        # Otherwise, compute what the next page we want to load
        args = {
            "query": self.crawlerStatus.project_type.filename,
            "filename": self.crawlerStatus.project_type.filename,
        }
        if self.crawlerStatus.cur_size == self.crawlerStatus.max_size:
            args["size"] = '>'+str(self.crawlerStatus.cur_size)
            self.crawlerStatus.cur_size = self.min_size
        else:
            args["size"] = self.crawlerStatus.cur_size
            self.crawlerStatus.cur_size = self.crawlerStatus.cur_size + 1
        return self.template.substitute(args)
    ## DEF
    
    def search(self):
        # Load and parse!
        response = self.loadURL(self.nextURL())
        soup = BeautifulSoup(response.read())
        titles = soup.find_all(class_='title')
        LOG.info("Found %d repositories" % len(titles))
        
        # Pick through the results and find repos
        for title in titles:
            name = title.contents[1].string
            if Repository.objects.filter(name=name).exists():
                LOG.info("Repository '%s' already exists" % name)
            else:
                LOG.info("Found new repository '%s'" % name)
                api_data = self.get_api_data(name)
                webpage_data = self.get_webpage_data(name)
                
                # Create the new repository
                repo = Repository()
                repo.name = name
                repo.repo_type = self.project_type
                repo.last_attempt = None
                repo.private = api_data['private']
                repo.description = Utils.none2empty(api_data['description'])
                repo.fork = api_data['fork']
                repo.created_at = datetime.strptime(api_data['created_at'], "%Y-%m-%dT%H:%M:%SZ")
                repo.updated_at = datetime.strptime(api_data['updated_at'], "%Y-%m-%dT%H:%M:%SZ")
                repo.pushed_at = datetime.strptime(api_data['pushed_at'], "%Y-%m-%dT%H:%M:%SZ")
                repo.homepage = Utils.none2empty(api_data['homepage'])
                repo.size = api_data['size']
                repo.stargazers_count = api_data['stargazers_count']
                repo.watchers_count = api_data['watchers_count']
                repo.language = Utils.none2empty(api_data['language'])
                repo.has_issues = api_data['has_issues']
                repo.has_downloads = api_data['has_downloads']
                repo.has_wiki = api_data['has_wiki']
                repo.has_pages= api_data['has_pages']
                repo.forks_count = api_data['forks_count']
                repo.open_issues_count = api_data['open_issues_count']
                repo.default_branch = api_data['default_branch']
                repo.network_count = api_data['network_count']
                repo.subscribers_count = api_data['subscribers_count']
                repo.commits_count = webpage_data['commits_count']
                repo.branches_count = webpage_data['branches_count']
                repo.releases_count = webpage_data['releases_count']
                repo.contributors_count = webpage_data['contributors_count']
                repo.attempts_count = 0
                repo.save()
                
                # Sleep for a little bit to prevent us from getting blocked
                time.sleep(API_GITHUB_SLEEP)
            ## IF
        ## FOR

        # Figure out what is the next page that we need to load
        next_page = soup.find(class_='next_page')
        next_url = None
        if not next_page or not next_page.has_attr('href'):
            LOG.info("No next page link found!")
            self.crawlerStatus.next_url = None
        else:
            self.crawlerStatus.next_url = GITHUB_HOST + next_page['href']
            
        # Make sure we update our crawler status
        self.crawlerStatus.save()
            
        return
    ## DEF

    def get_webpage_data(self, name):
        data = {}
        response = self.loadURL(os.path.join(GITHUB_HOST, name))
        soup = BeautifulSoup(response.read())
        numbers = soup.find_all(class_='num text-emphasized')
        
        # The fields that we want to extract integers
        # The order matters here
        fields = [
            "commits_count",
            "branches_count",
            "releases_count",
            "contributors_count",
        ]
        for i in xrange(len(fields)):
            try:
                data[fields[i]] = int(re.sub("\D", "", numbers[i].string))
            except:
                data[fields[i]] = 0
        ## FOR

        return data
    ## DEF

    def get_api_data(self, name):
        reponse = self.loadURL(os.path.join(API_GITHUB_REPO, name))
        data = json.load(reponse)
        return data
    ## DEF

    #def save(self):
        #repo_type = ProjectType.objects.get(name=self.name)
        #repo_type.cur_size = self.cur_size
        #repo_type.save()