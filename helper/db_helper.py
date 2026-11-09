#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
@author: xiaoyang
@time: 2018/3/6 9:10
@file: db_helper.py
@desc: 获取db
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from helper.sys_conf_helper import SysConfHelper
from tools.log_util import info


class DbHelper:
    session = None
    engine = None
    uri = None

    @staticmethod
    def get_session(hostname='127.0.0.1', port='3306', username=None, pwd=None, database=None):
        """
        初始化db session
        连接参数变化时自动重建；pool_pre_ping 保证断线（wait_timeout）自动重连
        """

        uri = SysConfHelper.get_item("mysql", "uri_pattern")

        uri = uri.format(username=username, pwd=pwd, hostname=hostname, port=port, database=database)

        if DbHelper.session and DbHelper.uri == uri:
            return DbHelper.session

        # 释放旧的缓存连接，避免复用已断线的 session
        if DbHelper.session:
            try:
                DbHelper.session.close()
            except Exception:
                pass
            DbHelper.session = None
        if DbHelper.engine:
            try:
                DbHelper.engine.dispose()
            except Exception:
                pass
            DbHelper.engine = None

        info('DbHelper', 'begin init database {0}'.format(uri))

        # 初始化数据库连接（取连接前先 ping，断线自动重连）:
        engine = create_engine(uri, pool_pre_ping=True)
        # 创建DBSession类型:
        db_session = sessionmaker(bind=engine)
        # 创建session对象:
        DbHelper.engine = engine
        DbHelper.uri = uri
        DbHelper.session = db_session()

        return DbHelper.session

    @staticmethod
    def get_db():
        """
        供错误处理器回滚使用（保持原接口兼容）
        """
        return DbHelper
