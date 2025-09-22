# Nagstamon - Nagios status monitor for your desktop
# Copyright (C) 2008-2025 Henri Wahl <henri@nagstamon.de> et al.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA

from pathlib import Path
import requests
import sqlite3

from Nagstamon.config import conf

COOKIE_DB_FILE = 'cookies.db'
COOKIE_DB_FILE_PATH = Path(conf.configdir) / COOKIE_DB_FILE

def init_db():
    connection = sqlite3.connect(COOKIE_DB_FILE_PATH)
    cursor = connection.cursor()
    cursor.execute('''
                   CREATE TABLE IF NOT EXISTS cookies
                   (
                       cookey
                       TEXT
                       PRIMARY
                       KEY,
                       server
                       TEXT,
                       name
                       TEXT,
                       value
                       TEXT,
                       domain
                       TEXT,
                       path
                       TEXT,
                       expiration
                       INTEGER,
                       secure
                       INTEGER,
                       httponly
                       INTEGER
                   )
                   ''')
    # check if 'server' column exists, if not add it - will be kicked out later
    cursor.execute("PRAGMA table_info(cookies)")
    table_info = cursor.fetchall()
    columns = [info[1] for info in table_info]
    # only necessary for upgrade from 'older' versions
    if 'server' not in columns:
        cursor.execute('ALTER TABLE cookies ADD COLUMN server TEXT')
    connection.commit()
    connection.close()


def save_cookies(cookies):
    init_db()
    connection = sqlite3.connect(COOKIE_DB_FILE_PATH)
    cursor = connection.cursor()
    for cookey, cookie_data in cookies.items():
        cursor.execute('''
            INSERT OR REPLACE INTO cookies
            (cookey, server, name, value, domain, path, expiration, secure, httponly)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            cookey,
            cookie_data['server'],
            cookie_data['name'],
            cookie_data['value'],
            cookie_data['domain'],
            cookie_data['path'],
            cookie_data['expiration'],
            int(cookie_data['secure']),
            int(cookie_data['httponly'])
        ))
    connection.commit()
    connection.close()


def load_cookies():
    init_db()
    connection = sqlite3.connect(COOKIE_DB_FILE_PATH)
    cursor = connection.cursor()
    cursor.execute('SELECT cookey, server, name, value, domain, path, expiration, secure, httponly FROM cookies')
    rows = cursor.fetchall()
    connection.close()
    cookies = {}
    for row in rows:
        cookey = row[0]
        cookies[cookey] = {
            'server': row[1],
            'name': row[2],
            'value': row[3],
            'domain': row[4],
            'path': row[5],
            'expiration': row[6],
            'secure': bool(row[7]),
            'httponly': bool(row[8])
        }
    return cookies


def cookie_data_to_jar(server_name, cookie_data):
    jar = requests.cookies.RequestsCookieJar()
    for cookie in cookie_data.values():
        if cookie['server'] == server_name:
            jar.set(
                name=cookie['name'],
                value=cookie['value'],
                domain=cookie['domain'],
                path=cookie['path'],
                expires=cookie['expiration'],
                secure=cookie['secure'],
                rest={'HttpOnly': cookie['httponly']}
            )
    return jar


