# -*- coding: utf-8 -*-

from ipaddress import IPv4Network

from ..datasource import DataSource, Dormitory
from . import user

datasource = DataSource(
    name='sample',
    user_class=user.User,
    mail_server="test.agdsn.de",
    init_context=user.init_context,
)

Dormitory(name='localhost', display_name="Lokalgastgeber",
          datasource=datasource,
          subnets=[
              IPv4Network('127.0.0.0/8'),  # loopback
              IPv4Network('172.0.0.0/8'),  # used by docker
          ])

__all__ = ['datasource']
