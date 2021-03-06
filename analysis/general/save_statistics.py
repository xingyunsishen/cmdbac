#!/usr/bin/env python
import os, sys
sys.path.append(os.path.join(os.path.dirname(__file__), os.pardir))
sys.path.append(os.path.join(os.path.dirname(__file__), os.pardir, os.pardir))
sys.path.append(os.path.join(os.path.dirname(__file__), os.pardir, os.pardir, "core"))

import re
import csv
import numpy as np
import sqlparse
import traceback
from utils import filter_repository

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "cmudbac.settings")
import django
django.setup()

from library.models import *

def save_statistic(description, count, attempt):
    try:
        Statistic.objects.get_or_create(description=description, count=count, attempt=attempt)
    except:
        pass

def transaction_stats(directory = '.'):
    for repo in Repository.objects.exclude(latest_successful_attempt = None):
        transaction_count = 0
        for action in Action.objects.filter(attempt = repo.latest_successful_attempt):
            transaction = False

            for query in Query.objects.filter(action = action):
                if 'BEGIN' in query.content.upper() or 'START TRANSACTION' in query.content.upper():
                    transaction = True
                elif transaction:
                    if 'COMMIT' in query.content.upper():
                        # for each transaction, count the number of transactions
                        transaction_count += 1
                        transaction = False

        save_statistic('num_transactions', transaction_count, repo.latest_successful_attempt)

def coverage_stats(directory = '.'):
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
        informations = Information.objects.filter(attempt = repo.latest_successful_attempt).filter(name = 'tables')
        if len(informations) == 0:
            continue

        information = informations[0]
        tables = set()
        if repo.latest_successful_attempt.database.name == 'PostgreSQL':
            regex = '(\(.*?\))[,\]]'
        elif repo.latest_successful_attempt.database.name == 'MySQL':
            regex = '(\(.*?\))[,\)]'

        for table in re.findall(regex, information.description):
            cells = table.split(',')
            table_name = str(cells[2]).replace("'", "").strip()
            tables.add(table_name)

        covered_tables = set()
        for action in actions:
            for query in Query.objects.filter(action = action):
                last_token = None
                for token in query.content.split():
                    token = token.replace('"', '').replace('`', '')
                    if token in tables:
                        covered_tables.add(token)
                    elif last_token == 'FROM' and '(' not in token and ')' not in token:
                        covered_tables.add(token)
                        tables.add(token)
                    last_token = token
        table_percentage = int(float(len(covered_tables) * 100) / table_count)
        table_percentage = min(table_percentage, 100)

        save_statistic('table_coverage', table_percentage, repo.latest_successful_attempt)

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
            save_statistic('num_columns', column_count, repo.latest_successful_attempt)

            if column_count > 0:
                covered_columns = set()
                for action in actions:
                    for query in Query.objects.filter(action = action):
                        parsed = sqlparse.parse(query.content)[0]
                        tokens = parsed.tokens
                        for token in tokens:
                            token_name = token.value.replace('`', '')
                            if isinstance(token, sqlparse.sql.Identifier):
                                covered_columns.add(token_name)

                column_percentage = int(float(len(covered_columns) * 100) / column_count)
                column_percentage = min(column_percentage, 100)

                save_statistic('column_coverage', column_percentage, repo.latest_successful_attempt)

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

                save_statistic('index_coverage', index_percentage, repo.latest_successful_attempt)

def secondary_index_stats():
    for repo in Repository.objects.exclude(latest_successful_attempt = None):
        informations = Information.objects.filter(attempt = repo.latest_successful_attempt).filter(name = 'indexes')
        if len(informations) > 0:
            information = informations[0]
            if repo.latest_successful_attempt.database.name == 'PostgreSQL':
                regex = '(\(.*?\))[,\]]'
            elif repo.latest_successful_attempt.database.name == 'MySQL':
                regex = '(\(.*?\))[,\)]'

            secondary_index_count = 0
            for index in re.findall(regex, information.description):
                cells = index.split(',')

                index_name = cells[5].replace("'", "").strip()

                if index_name != 'PRIMARY':
                    secondary_index_count += 1

            save_statistic('num_secondary_indexes', secondary_index_count, repo.latest_successful_attempt)

def transaction_ratio_stats():
    for repo in Repository.objects.exclude(latest_successful_attempt = None):
        statistics = Statistic.objects.filter(attempt = repo.latest_successful_attempt).filter(description = 'num_transactions')
        if len(statistics) == 0:
            continue
        transaction_count = max(statistic.count for statistic in statistics)
        action_count = repo.latest_successful_attempt.actions_count
        if action_count > 0:
            transaction_ratio = transaction_count * 100 / action_count
            save_statistic('transaction_ratio', transaction_ratio, repo.latest_successful_attempt)


def join_stats():
    for repo in Repository.objects.exclude(latest_successful_attempt = None):
        join_count = 0
        for action in Action.objects.filter(attempt = repo.latest_successful_attempt):
            for query in Query.objects.filter(action = action):
                join_count += len(re.findall('JOIN', query.content.upper()))
        save_statistic('num_joins', join_count, repo.latest_successful_attempt)

def action_stats():
    for repo in Repository.objects.exclude(latest_successful_attempt = None):
        read_count, write_count = 0, 0
        table_access_count = 0
        query_count, action_count = 0, 0
        for action in Action.objects.filter(attempt = repo.latest_successful_attempt):
            is_read, is_write = False, False
            for query in Query.objects.filter(action = action):
                if 'SELECT' in query.content:
                    is_read = True
                if 'INSERT' in query.content or 'UPDATE' in query.content or 'DELETE' in query.content:
                    is_write = True

                last_token = None
                tables = set()
                for token in query.content.split():
                    token = token.replace('"', '').replace('`', '')
                    if last_token == 'FROM' and '(' not in token and ')' not in token:
                        tables.add(token)
                    last_token = token
                table_access_count += len(tables)

                query_count += 1

            if is_read:
                read_count += 1
            if is_write:
                write_count += 1

        save_statistic('num_read_actions', read_count, repo.latest_successful_attempt)
        save_statistic('num_write_actions', write_count, repo.latest_successful_attempt)
        save_statistic('table_access_count_action', float(table_access_count) / max(action_count, 1), repo.latest_successful_attempt)
        save_statistic('table_access_count_query', float(table_access_count) * 100 / max(query_count, 1), repo.latest_successful_attempt)

def main():
    transaction_stats()
    coverage_stats()
    secondary_index_stats()
    transaction_ratio_stats()
    join_stats()
    action_stats()

if __name__ == '__main__':
    main()
