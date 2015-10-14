# -*- coding: utf-8 -*-

import scrapy
from scrapy.spiders import CrawlSpider, Rule
from scrapy.contrib.linkextractors.sgml import SgmlLinkExtractor

from driver.items import InputItem, FormItem

class FormSpider(CrawlSpider):
    name = "form"
    allowed_domains = ["127.0.0.1"]    

    def __init__(self, *args, **kwargs): 
        super(FormSpider, self).__init__(*args, **kwargs)

        self.start_urls = [kwargs.get('start_url')]
        
        follow = True if kwargs.get('follow') == 'true' else False
        self.rules = (
            Rule (SgmlLinkExtractor(allow=('')), callback='parse_form', follow=follow),
        )
        super(FormSpider, self)._compile_rules()

 
    def parse_form(self, response):
        for sel in response.xpath('//form'):
            formItem = FormItem()

            formItem['action'] = ''
            try:
                formItem['action'] = sel.xpath('@action').extract()[0]
            except:
                pass
            formItem['url'] = response.url
            try:
                formItem['method'] = sel.xpath('@method').extract()[0].lower()
            except:
                formItem['method'] = ''

            for ip in sel.xpath('//input[@type="text" or @type="password" or @type="email"]|//textarea'):
                try:
                    id = ip.xpath('@id').extract()[0]
                except:
                    id = ''
                name = ip.xpath('@name').extract()[0]
                type = ip.xpath('@type').extract()[0]
                inputItem = InputItem()
                inputItem['id'] = id
                inputItem['name'] = name
                inputItem['type'] = type
                inputItem['value'] = ''
                if 'inputs' in formItem:
                    formItem['inputs'].append(inputItem)
                else:
                    formItem['inputs'] = [inputItem]
            yield formItem
            
