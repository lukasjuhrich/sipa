# -*- coding: utf-8 -*-

import datetime

from sqlalchemy import create_engine
from flask.ext.babel import gettext
from flask.globals import current_app
from sqlalchemy.exc import OperationalError

from werkzeug.local import LocalProxy

from model.constants import WEEKDAYS

from sipa.utils import timetag_from_timestamp, timestamp_from_timetag
from sipa.utils.exceptions import DBQueryEmpty
from .ldap_utils import get_current_uid

import logging
logger = logging.getLogger(__name__)


def init_db(app):
    app.extensions['db_atlantis'] = create_engine(
        'mysql+pymysql://{0}:{1}@{2}:3306/netusers'.format(
            app.config['DB_ATLANTIS_USER'],
            app.config['DB_ATLANTIS_PASSWORD'],
            app.config['DB_ATLANTIS_HOST']),
        echo=False, connect_args={'connect_timeout': app.config['SQL_TIMEOUT']}
    )
    app.extensions['db_helios'] = create_engine(
        'mysql+pymysql://{0}:{1}@{2}:{3}/'.format(
            app.config['DB_HELIOS_USER'],
            app.config['DB_HELIOS_PASSWORD'],
            app.config['DB_HELIOS_HOST'],
            int(app.config['DB_HELIOS_PORT'])),
        echo=False, connect_args={'connect_timeout': app.config['SQL_TIMEOUT']}
    )


db_atlantis = LocalProxy(lambda: current_app.extensions['db_atlantis'])
db_helios = LocalProxy(lambda: current_app.extensions['db_helios'])

DORMITORIES = [
    'Wundstraße 5',
    'Wundstraße 7',
    'Wundstraße 9',
    'Wundstraße 11',
    'Wundstraße 1',
    'Wundstraße 3',
    'Zellescher Weg 41',
    'Zellescher Weg 41A',
    'Zellescher Weg 41B',
    'Zellescher Weg 41C',
    'Zellescher Weg 41D',
    'Borsbergstraße 34',
]

STATUS = {
    1: (gettext('Bezahlt, verbunden'), 'success'),
    2: (gettext('Nicht bezahlt, Netzanschluss gesperrt'), 'warning'),
    7: (gettext('Verstoß gegen Netzordnung, Netzanschluss gesperrt'),
        'danger'),
    9: (gettext('Exaktiv'), 'muted'),
    12: (gettext('Trafficlimit überschritten, Netzanschluss gesperrt'),
         'danger')
}


def sql_query(query, args=(), database=db_atlantis):
    """Prepare and execute a raw sql query.
    'args' is a tuple needed for string replacement.
    """
    conn = database.connect()
    result = conn.execute(query, args)
    conn.close()
    return result


def user_id_from_uid(uid=None):
    """Fetch user.id (MySQL) from user.uid (LDAP)

    :param uid: The uid of the LDAP user object
    :return: The user id of the MySQL user
    """
    if uid is None:
        uid = get_current_uid()

    return sql_query("SELECT nutzer_id FROM nutzer WHERE unix_account = %s",
                     (uid,)).fetchone()['nutzer_id']


def ip_from_user_id(user_id):
    result = (sql_query(
        "SELECT c_ip FROM computer WHERE nutzer_id = %s",
        (user_id,)
    ).fetchone())
    if not result:
        raise DBQueryEmpty('Nutzer hat keine IP')
    return result['c_ip']


def user_id_from_ip(ip):
    """Returns the MySQL user.id corresponding to the ip or 0 if foreign to the db
    :param ip: A valid IP address
    :return: A user id
    """

    result = sql_query("SELECT nutzer_id FROM computer WHERE c_ip = %s",
                       (ip,)).fetchone()
    if result is None:
        return 0

    return result['nutzer_id']


def query_current_credit(uid=None, ip=None):
    """Returns the current credit in MiB
    :param uid: The id of the user
    :param ip: The ip of the user
    :return: The current amount of credit or False if foreign IP
    """
    if uid is None:
        if ip is None:
            raise AttributeError('Either ip or user_id must be specified!')
        user_id = user_id_from_ip(ip)
        if user_id is 0:
            return False  # IP doesn't correspond to any user
    else:
        user_id = user_id_from_uid(uid)
        ip = ip_from_user_id(user_id)

    try:
        result = sql_query(
            "SELECT amount - input - output as current "
            "FROM traffic.tuext AS t "
            "LEFT OUTER JOIN credit AS c ON t.timetag = c.timetag "
            "WHERE ip = %(ip)s AND c.user_id = %(user_id)s "
            "AND t.timetag = %(today)s",
            {'today': timetag_from_timestamp(), 'ip': ip, 'user_id': user_id}
        ).fetchone()
    except OperationalError as e:
        logger.critical('Unable to connect to MySQL server',
                        extra={'data': {'exception_args': e.args}})
        raise
    else:
        if result and 'current' in result.keys():
            return round(result['current'] / 1024, 2)
        else:
            logger.warning("Credit query was empty", extra={'data': {
                'today': timetag_from_timestamp(), 'ip': ip, 'user_id': user_id
            }})


def query_trafficdata(ip, user_id):
    """Query traffic input/output for IP

    :param ip: a valid ip
    :param user_id: an id of a mysql user tuple
    :return: a dict containing the traffic data in the form of
    {'history': [('weekday', in, out, credit), …], 'credit': credit}
    """
    trafficdata = sql_query(
        "SELECT t.timetag - %(today)s AS day, input, output, amount "
        "FROM traffic.tuext AS t "
        "LEFT OUTER JOIN credit AS c ON t.timetag = c.timetag "
        "WHERE ip = %(ip)s AND c.user_id = %(uid)s "
        "AND t.timetag BETWEEN %(weekago)s AND %(today)s "
        "ORDER BY 'day' DESC ",
        {'today': timetag_from_timestamp(),
         'weekago': timetag_from_timestamp() - 6,
         'ip': ip,
         'uid': user_id}
    ).fetchall()

    if not trafficdata:
        raise DBQueryEmpty('No trafficdata retrieved for user {}@{}'
                           .format(user_id, ip))

    traffic = {'history': [], 'credit': 0}
    returned_days = [int(i['day']) for i in trafficdata]

    # loop through expected days ([-6..0])
    for d in range(-6, 1):
        day = datetime.date.fromtimestamp(
            timestamp_from_timetag(timetag_from_timestamp() + d)
        ).strftime('%w')
        if d in returned_days:
            # pick the to `d` corresponding item of the mysql-result
            i = next((x for x in trafficdata if x['day'] == d), None)

            (input, output, credit) = (
                round(i[param] / 1024.0, 2)
                for param in ['input', 'output', 'amount']
            )
            traffic['history'].append(
                (WEEKDAYS[int(day)], input, output, credit))
        else:
            traffic['history'].append(
                (WEEKDAYS[int(day)], 0.0, 0.0, 0.0))

    traffic['credit'] = (lambda x: x[3] - x[1] - x[2])(traffic['history'][-1])

    return traffic


def update_macaddress(ip, oldmac, newmac):
    """Update a MAC address in computer table.

    Adding a `LIMIT 1` would be an “unsafe statement”, because using a
    `LIMIT` w/o an `ORDER BY` does not give control over which row
    actually would be affected, if the `WHERE` clauses would apply to
    more than one row.

    """
    sql_query(
        "UPDATE computer "
        "SET c_etheraddr = %s "
        "WHERE c_ip = %s "
        "AND c_etheraddr = %s ",
        (newmac.lower(), ip, oldmac)
    )


def user_has_mysql_db(username):
    """Returns true if a database with the given name exists on
    helios-userdatabase, otherwise false.
    """
    userdb = sql_query(
        "SELECT SCHEMA_NAME "
        "FROM INFORMATION_SCHEMA.SCHEMATA "
        "WHERE SCHEMA_NAME = %s",
        (username,),
        database=db_helios
    ).fetchone()

    if userdb is not None:
        return True
    return False


def create_mysql_userdatabase(username, password):
    """A user specific database on helios is going to be created.
    """
    sql_query(
        "CREATE DATABASE "
        "IF NOT EXISTS `%s`" % username,
        database=db_helios
    )

    change_mysql_userdatabase_password(username, password)


def change_mysql_userdatabase_password(username, password):
    """This changes a user password for the helios MySQL-database.
    """
    user = sql_query(
        "SELECT user "
        "FROM mysql.user "
        "WHERE user = %s",
        (username,),
        database=db_helios
    ).fetchall()

    if not user:
        sql_query(
            "CREATE USER %s@'10.1.7.%%' "
            "IDENTIFIED BY %s",
            (username, password),
            database=db_helios
        )
    else:
        sql_query(
            "SET PASSWORD "
            "FOR %s@'10.1.7.%%' = PASSWORD(%s)",
            (username, password),
            database=db_helios
        )

    sql_query(
        "GRANT SELECT, INSERT, UPDATE, DELETE, "
        "ALTER, CREATE, DROP, INDEX, LOCK TABLES "
        "ON `%s`.* "
        "TO %%s@'10.1.7.%%%%'" % username,
        (username,),
        database=db_helios
    )


def drop_mysql_userdatabase(username):
    """This removes a userdatabase on helios.
    """
    sql_query(
        "DROP DATABASE "
        "IF EXISTS `%s`" % username,
        database=db_helios
    )

    sql_query(
        "DROP USER %s@'10.1.7.%%'",
        (username,),
        database=db_helios
    )


def calculate_userid_checksum(user_id):
    """Calculate checksum for a userid.
    (Modulo 10 on the sum of all digits)

    :param user_id: The id of the mysql user tuple
    """
    return sum(map(int, str(user_id))) % 10
