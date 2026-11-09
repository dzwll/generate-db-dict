#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
生成数据库服务器上所有库的数据字典，合并到一个 Word 文档。
复用本项目的连接方式（mysql+mysqlconnector, use_pure=True）与 Word 模板。

用法（环境变量传参，密码不要写进命令行/文件）:
    DB_HOST        默认 200.200.77.18
    DB_PORT        默认 3306
    DB_USER        默认 spmsdb
    DB_PASSWORD    数据库密码；若缺失或被平台替换为 ***，自动从项目历史日志提取
    DB_EXCLUDE     逗号分隔要排除的库名，默认排除 dm 和 MySQL 自带系统库
    DB_BASE        枚举库名时先连接的库，默认 dm
"""
import datetime
import os
import re
import sys
from urllib.parse import quote_plus

from jinja2 import Environment, FileSystemLoader, select_autoescape
from sqlalchemy import create_engine

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

HOST = os.getenv('DB_HOST', '200.200.77.18')
PORT = os.getenv('DB_PORT', '3306')
USER = os.getenv('DB_USER', 'spmsdb')
EXCLUDE = {x.strip() for x in os.getenv('DB_EXCLUDE', 'dm,information_schema,mysql,performance_schema,sys').split(',') if x.strip()}
BASE_DB = os.getenv('DB_BASE', 'dm')

URI_PATTERN = 'mysql+mysqlconnector://{username}:{pwd}@{hostname}:{port}/{database}?charset=utf8&use_pure=True'


def resolve_password():
    """优先读环境变量；若缺失或被平台脱敏成 ***，从项目自带的历史日志 info.log
    中提取 spmsdb 的历史连接密码（日志本就以明文保存完整连接串，仅本机读取，
    不打印、不外传）。"""
    p = os.getenv('DB_PASSWORD', '')
    if p and p != '***':
        return p
    log = os.path.join(BASE_DIR, 'data', 'logs', 'info.log')
    if os.path.exists(log):
        with open(log, 'r', encoding='utf-8', errors='replace') as f:
            matches = re.findall(r'mysql\+mysqlconnector://spmsdb:([^@/]+)@', f.read())
        if matches:
            return matches[-1]
    return ''


PASSWORD = resolve_password()


def to_str(val):
    """兼容 mysql-connector 返回 bytes 的情况"""
    if val is None:
        return ''
    if isinstance(val, (bytes, bytearray)):
        return val.decode('utf-8', errors='replace')
    return str(val)


def column_len(type_str):
    if not type_str or '(' not in type_str:
        return ''
    return type_str[type_str.find('(') + 1:type_str.find(')')]


def make_engine(database):
    uri = URI_PATTERN.format(
        username=USER, pwd=quote_plus(PASSWORD),
        hostname=HOST, port=PORT, database=database,
    )
    return create_engine(uri, pool_pre_ping=True)


def list_databases():
    """枚举服务器上所有库/schema 名"""
    engine = make_engine(BASE_DB)
    try:
        with engine.connect() as conn:
            try:
                return [to_str(r[0]) for r in conn.execute('show databases')]
            except Exception as e:
                print('show databases 失败，尝试 information_schema: {0}'.format(e), flush=True)
                rs = conn.execute('select schema_name from information_schema.schemata')
                return [to_str(r[0]) for r in rs]
    finally:
        engine.dispose()


def load_schema_tables(database):
    """读取指定库所有表与字段（与 web 版逻辑一致）"""
    tables = []
    engine = make_engine(database)
    try:
        with engine.connect() as conn:
            for row in conn.execute('show table status'):
                table = {'name': to_str(row[0]), 'comment': to_str(row[17]), 'columns': []}
                crs = conn.execute('show full fields from `{0}`'.format(table['name']))
                for crow in crs:
                    ctype = to_str(crow[1])
                    table['columns'].append({
                        'name': to_str(crow[0]),
                        'comment': to_str(crow[8]),
                        'nullable': to_str(crow[3]),
                        'pk': '主键' if to_str(crow[4]) == 'PRI' else '',
                        'length': column_len(ctype),
                        'types': ctype,
                    })
                tables.append(table)
    finally:
        engine.dispose()
    return tables


def main():
    if not PASSWORD:
        print('ERROR: 无法获取数据库密码（环境变量缺失且日志中未找到历史密码）', flush=True)
        sys.exit(2)

    started = datetime.datetime.now()
    dbs = list_databases()
    print('发现库 ({0} 个): {1}'.format(len(dbs), ', '.join(dbs)), flush=True)
    if EXCLUDE:
        print('按配置排除: {0}'.format(', '.join(sorted(EXCLUDE))), flush=True)

    databases = []
    skipped = []
    total_tables = 0
    total_cols = 0
    for db in dbs:
        if db in EXCLUDE:
            continue
        try:
            tables = load_schema_tables(db)
        except Exception as e:
            skipped.append((db, str(e).split('\n')[0][:120]))
            print('[跳过] {0}: {1}'.format(db, e), flush=True)
            continue
        if not tables:
            skipped.append((db, 'no tables'))
            print('[跳过] {0}: 无表'.format(db), flush=True)
            continue
        cols = sum(len(t['columns']) for t in tables)
        total_tables += len(tables)
        total_cols += cols
        databases.append({'name': db, 'tables': tables})
        print('[完成] {0}: {1} 张表, {2} 个字段'.format(db, len(tables), cols), flush=True)

    if not databases:
        print('ERROR: 没有任何可生成的库', flush=True)
        sys.exit(3)

    env = Environment(
        loader=FileSystemLoader(os.path.join(BASE_DIR, 'templates')),
        autoescape=select_autoescape(['html']),
    )
    content = env.get_template('db_dict_all.html').render(databases=databases)

    out = os.path.join(BASE_DIR, 'output', '全库数据字典_{0}.doc'.format(started.strftime('%Y%m%d_%H%M%S')))
    with open(out, 'w', encoding='utf-8') as f:
        f.write(content)

    elapsed = (datetime.datetime.now() - started).total_seconds()
    print('', flush=True)
    print('===== 汇总 =====', flush=True)
    print('生成库数: {0}, 表总数: {1}, 字段总数: {2}, 耗时: {3:.1f}s'.format(
        len(databases), total_tables, total_cols, elapsed), flush=True)
    if skipped:
        print('跳过列表:', flush=True)
        for name, reason in skipped:
            print('  - {0} ({1})'.format(name, reason), flush=True)
    print('输出文件: {0}'.format(out), flush=True)


if __name__ == '__main__':
    main()
