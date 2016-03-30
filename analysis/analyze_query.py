#!/usr/bin/env python
import os, sys
sys.path.append(os.path.join(os.path.dirname(__file__), os.pardir))

import re
import csv
import numpy as np
import sqlparse
from dump import dump_stats, dump_all_stats

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "cmudbac.settings")
import django
django.setup()

from library.models import *

QUERIES_DIRECTORY = 'queries'

def query_stats(directory = '.'):
    stats = {'query_type': {}}

    for repo in Repository.objects.exclude(latest_successful_attempt = None):
        actions = Action.objects.filter(attempt = repo.latest_successful_attempt)
        if len(actions) == 0:
            continue
        
        for action in actions:
            counters = Counter.objects.filter(action = action)
            for counter in counters:
                project_type_name = repo.project_type.name
                if project_type_name not in stats['query_type']:
                    stats['query_type'][project_type_name] = {}
                if counter.description not in stats['query_type'][project_type_name]:
                    stats['query_type'][project_type_name][counter.description] = 0
                stats['query_type'][project_type_name][counter.description] += counter.count

    dump_all_stats(directory, stats)

def coverage_stats(directory = '.'):
    stats = {'table_coverage': {}, 'column_coverage': {}, 'index_coverage': {}, 'table_access': {}}

    for repo in Repository.objects.exclude(latest_successful_attempt = None):
        actions = Action.objects.filter(attempt = repo.latest_successful_attempt)
        if len(actions) == 0:
            continue
        statistics = Statistic.objects.filter(attempt = repo.latest_successful_attempt).filter(description = 'num_tables')
        if len(statistics) == 0:
            continue
        table_count = statistics[0].count
        if table_count == 0:
            continue

        project_type_name = repo.project_type.name
        
        covered_tables = set()
        for action in actions:
            for query in Query.objects.filter(action = action):
                table_access_count = 0
                for table in re.findall('FROM\s*\S+', query.content.upper()):
                    table_name = table.replace('FROM', '').replace("'", "").replace(' ', '').replace('"', '')
                    if '(' in table_name or ')' in table_name:
                        continue
                    covered_tables.add(table_name)
                    table_access_count += 1
                if project_type_name not in stats['table_access']:
                    stats['table_access'][project_type_name] = []
                stats['table_access'][project_type_name].append(table_access_count)

        table_percentage = int(float(len(covered_tables) * 100) / table_count)
        table_percentage = min(table_percentage, 100)

        if project_type_name not in stats['table_coverage']:
            stats['table_coverage'][project_type_name] = []
        stats['table_coverage'][project_type_name].append(table_percentage)

        informations = Information.objects.filter(attempt = repo.latest_successful_attempt).filter(name = 'columns')
        if len(informations) > 0:
            information = informations[0]
            column_count = 0
            for covered_table in covered_tables:
                column_count += len(re.findall(covered_table.upper(), information.description.upper()))
            if repo.latest_successful_attempt.database.name == 'PostgreSQL':
                column_count = min(column_count, len(re.findall('(\(.*?\))[,\]]', information.description)))
            elif repo.latest_successful_attempt.database.name == 'MySQL':
                column_count = min(column_count, len(re.findall('(\(.*?\))[,\)]', information.description)))
        
            if column_count > 0:
                covered_columns = set()
                for action in actions:
                    for query in Query.objects.filter(action = action):
                        parsed = sqlparse.parse(query.content)[0]
                        tokens = parsed.tokens
                        for token in tokens:
                            if isinstance(token, sqlparse.sql.Identifier):
                                covered_columns.add(token.value)

                column_percentage = int(float(len(covered_columns) * 100) / column_count)
                column_percentage = min(column_percentage, 100)

                if project_type_name not in stats['column_coverage']:
                    stats['column_coverage'][project_type_name] = []
                stats['column_coverage'][project_type_name].append(column_percentage)

        informations = Information.objects.filter(attempt = repo.latest_successful_attempt).filter(name = 'indexes')
        if len(informations) > 0:
            information = informations[0]
            index_count = 0
            for covered_table in covered_tables:
                index_count += len(re.findall(covered_table.upper(), information.description.upper()))
            statistics = Statistic.objects.filter(attempt = repo.latest_successful_attempt).filter(description = 'num_indexes')
            if len(statistics) == 0:
                continue
            if statistics[0].count > 0:
                index_count = min(index_count, statistics[0].count)
            
            if index_count > 0:
                covered_indexes = set()
                for action in actions:
                    for query in Query.objects.filter(action = action):
                        for explain in Explain.objects.filter(query = query):
                            for raw_index in re.findall('Index.*?Scan.*?on \S+', explain.output):
                                index = raw_index.split()[-1]
                                covered_indexes.add(index)
                   
                index_percentage = int(float(len(covered_indexes) * 100) / index_count)
                index_percentage = min(index_percentage, 100)

                if project_type_name not in stats['index_coverage']:
                    stats['index_coverage'][project_type_name] = []
                stats['index_coverage'][project_type_name].append(index_percentage)

    dump_all_stats(directory, stats)

def sort_stats(directory = '.'):
    stats = {'sort_keys': {}}

    for repo in Repository.objects.exclude(latest_successful_attempt = None):
        project_type_name = repo.project_type.name
        if project_type_name not in stats['sort_keys']:
            stats['sort_keys'][project_type_name] = {}
        for action in Action.objects.filter(attempt = repo.latest_successful_attempt):
            for query in Query.objects.filter(action = action):
                for explain in Explain.objects.filter(query = query):
                    for sort_keys in re.findall('Sort Key: .*', explain.output):
                        sort_keys_count = len(re.findall(',', sort_keys)) + 1
                        if sort_keys_count <= 3:
                            stats['sort_keys'][project_type_name][str(sort_keys_count)] = stats['sort_keys'][project_type_name].get(str(sort_keys_count), 0) + 1
                        else:
                            stats['sort_keys'][project_type_name]['greater than or equal to 4'] = stats['sort_keys'][project_type_name].get('greater than or equal to 4', 0) + 1

    dump_all_stats(directory, stats)

def scan_stats(directory = '.'):
    stats = {'scan_type': {}}

    for repo in Repository.objects.exclude(latest_successful_attempt = None):
        project_type_name = repo.project_type.name
        if project_type_name not in stats['scan_type']:
            stats['scan_type'][project_type_name] = {}            
        for action in Action.objects.filter(attempt = repo.latest_successful_attempt):
            for query in Query.objects.filter(action = action):
                for explain in Explain.objects.filter(query = query):
                    for scan in re.findall('[A-Za-z][\sA-Za-z]*Scan', explain.output):
                        stats['scan_type'][project_type_name][scan] = stats['scan_type'][project_type_name].get(scan, 0) + 1

    dump_all_stats(directory, stats)

def multiset_stats(directory = '.'):
    stats = {'logical_operator': {}, 'set_operator': {}}

    for repo in Repository.objects.exclude(latest_successful_attempt = None):
        project_type_name = repo.project_type.name
        if project_type_name not in stats['logical_operator']:
            stats['logical_operator'][project_type_name] = {}
        if project_type_name not in stats['set_operator']:
            stats['set_operator'][project_type_name] = {}
        for action in Action.objects.filter(attempt = repo.latest_successful_attempt):
            for query in Query.objects.filter(action = action):
                for logical_word in ['AND', 'OR', 'NOT', 'XOR']:
                    stats['logical_operator'][project_type_name][logical_word] = stats['logical_operator'][project_type_name].get(logical_word, 0) + len(re.findall(logical_word, query.content))
                for set_word in ['UNION', 'INTERSECT', 'EXCEPT']:
                    stats['set_operator'][project_type_name][set_word] = stats['set_operator'][project_type_name].get(set_word, 0) + len(re.findall(set_word, query.content))

    dump_all_stats(directory, stats)

def aggregate_stats(directory = '.'):
    stats = {'aggregate_operator': {}}

    for repo in Repository.objects.exclude(latest_successful_attempt = None):
        project_type_name = repo.project_type.name
        if project_type_name not in stats['aggregate_operator']:
            stats['aggregate_operator'][project_type_name] = {}
        for action in Action.objects.filter(attempt = repo.latest_successful_attempt):
            for query in Query.objects.filter(action = action):
                for aggregate_word in ['AVG', 'COUNT', 'MAX', 'MIN', 'SUM']:
                    stats['aggregate_operator'][project_type_name][aggregate_word] = stats['aggregate_operator'][project_type_name].get(aggregate_word, 0) + len(re.findall(aggregate_word, query.content))

    dump_all_stats(directory, stats)

def nested_stats(directory = '.'):
    stats = {'nested_count': {}, 'nested_operator': {}}

    for repo in Repository.objects.exclude(latest_successful_attempt = None):
        project_type_name = repo.project_type.name
        if project_type_name not in stats['nested_count']:
            stats['nested_count'][project_type_name] = {}
        if project_type_name not in stats['nested_operator']:
            stats['nested_operator'][project_type_name] = {}
        for action in Action.objects.filter(attempt = repo.latest_attempt):
            for query in Query.objects.filter(action = action):
                nested_count = 0
                for explain in Explain.objects.filter(query = query):
                    nested_count += len(re.findall('Nested', explain.output))
                if nested_count > 0:
                    stats['nested_count'][project_type_name][str(nested_count)] = stats['nested_count'][project_type_name].get(str(nested_count), 0) + 1
                for nested_word in ['ALL', 'ANY', 'SOME', 'EXISTS', 'IN', 'NOT EXISTS']:
                    stats['nested_operator'][project_type_name][nested_word] = stats['nested_operator'][project_type_name].get(nested_word, 0) + len(re.findall(nested_word, query.content))
                stats['nested_operator'][project_type_name]['EXISTS'] -= len(re.findall('NOT EXISTS', query.content))

    dump_all_stats(directory, stats)

def having_stats(directory = '.'):
    stats = {'having_count': {}, 'group_count': {}}

    for repo in Repository.objects.exclude(latest_successful_attempt = None):
        project_type_name = repo.project_type.name
        if project_type_name not in stats['having_count']:
            stats['having_count'][project_type_name] = {}
        if project_type_name not in stats['group_count']:
            stats['group_count'][project_type_name] = {}
        for action in Action.objects.filter(attempt = repo.latest_attempt):
            for query in Query.objects.filter(action = action):
                having_count = len(re.findall('HAVING', query.content))
                if having_count > 0:
                    stats['having_count'][project_type_name][str(having_count)] = stats['having_count'][project_type_name].get(str(having_count), 0) + 1
                group_count = len(re.findall('GROUP BY', query.content))
                if group_count > 0:
                    stats['group_count'][project_type_name][str(group_count)] = stats['group_count'][project_type_name].get(str(group_count), 0) + 1

    dump_all_stats(directory, stats)

def join_stats(directory = '.'):
    stats = {}

    for repo in Repository.objects.filter(latest_attempt__result = 'OK'):
        for action in Action.objects.filter(attempt = repo.latest_attempt):
            queries = Query.objects.filter(action = action)
            for query in queries:
                content = query.content.upper()
                if 'JOIN' in content:
                    parsed = sqlparse.parse(content)[0]
                    tokens = parsed.tokens
                    for index in xrange(0, len(tokens)):
                        if tokens[index].is_keyword and 'JOIN' in tokens[index].value:
                            stats[tokens[index].value] = stats.get(tokens[index].value, 0) + 1

    dump_stats(directory, 'join', stats)

def main():
    # active
    # query_stats(QUERIES_DIRECTORY)
    coverage_stats(QUERIES_DIRECTORY)
    # sort_stats(QUERIES_DIRECTORY)
    # scan_stats(QUERIES_DIRECTORY)
    # multiset_stats(QUERIES_DIRECTORY)
    # aggregate_stats(QUERIES_DIRECTORY)
    # nested_stats(QUERIES_DIRECTORY)
    # having_stats(QUERIES_DIRECTORY)

    # working
    # join_stats(QUERIES_DIRECTORY)
    
    # deprecated

if __name__ == '__main__':
    main()