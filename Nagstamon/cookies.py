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

from ansible_collections.community.network.plugins.modules.cv_server_provision import connect

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
    connection.commit()
    connection.close()


def save_cookies(cookies):
    init_db()
    connection = sqlite3.connect(COOKIE_DB_FILE_PATH)
    cursor = connection.cursor()
    for cookey, cookie_data in cookies.items():
        cursor.execute('''
            INSERT OR REPLACE INTO cookies
            (cookey, name, value, domain, path, expiration, secure, httponly)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            cookey,
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
    cursor.execute('SELECT * FROM cookies')
    rows = cursor.fetchall()
    connection.close()
    cookies = {}
    for row in rows:
        cookey = row[0]
        cookies[cookey] = {
            'name': row[1],
            'value': row[2],
            'domain': row[3],
            'path': row[4],
            'expiration': row[5],
            'secure': bool(row[6]),
            'httponly': bool(row[7])
        }
    return cookies


def cookie_data_to_jar(cookie_data):
    jar = requests.cookies.RequestsCookieJar()
    print(cookie_data)
    for cookie in cookie_data.values():
        jar.set(
            name=cookie['name'],
            value=cookie['value'],
            domain=cookie['domain'],
            path=cookie['path'],
            expires=cookie['expiration'],
            secure=cookie['secure'],
            rest={'HttpOnly': cookie['httponly']}
        )
    print(jar)
    return jar


def handle_cookie_added(cookie):
    # Lädt bestehende Cookies aus der Datei
    cookies = load_cookies()
    # Extrahiert relevante Cookie-Daten als Dictionary
    cookie_data = {
        'name': cookie.name().data().decode(),
        'value': cookie.value().data().decode(),
        'domain': cookie.domain(),
        'path': cookie.path(),
        'expiration': cookie.expirationDate().toSecsSinceEpoch() if cookie.expirationDate().isValid() else None,
        'secure': cookie.isSecure(),
        'httponly': cookie.isHttpOnly(),
    }
    # Fügt das Cookie nur hinzu, wenn es noch nicht gespeichert wurde
    cookey = f"{cookie_data['domain']}+{cookie_data['path']}+{cookie_data['name']}"
    if cookie_data not in cookies.values():
        cookies[cookey] = cookie_data
        save_cookies(cookies)


