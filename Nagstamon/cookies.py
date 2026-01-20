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

from cryptography.fernet import (Fernet,
                                 InvalidToken)

from Nagstamon.config import (conf,
                              OS,
                              OS_NON_LINUX)
if conf.is_keyring_available():
    import keyring
    encrypt_cookie = True
else:
    encrypt_cookie = False

COOKIE_DB_FILE = 'cookies.db'
COOKIE_DB_FILE_PATH = Path(conf.configdir) / COOKIE_DB_FILE

def init_db():
    """
    initialize the SQLite database for storing cookies
    """
    # make sure the config directory exists
    conf.save_config()
    # connect to the database file, which will be created if it does not exist
    connection = sqlite3.connect(COOKIE_DB_FILE_PATH)
    cursor = connection.cursor()
    # create cookies table with schema if it does not exist
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
                       INTEGER,
                       encrypted
                       INTEGER
                   )
                   ''')
    # check if 'server' and 'encrypted' columns exist, if not add them - will be kicked out later
    cursor.execute("PRAGMA table_info(cookies)")
    table_info = cursor.fetchall()
    columns = [info[1] for info in table_info]
    # only necessary for upgrade from 'older' versions
    if 'server' not in columns:
        cursor.execute('ALTER TABLE cookies ADD COLUMN server TEXT')
    if 'encrypted' not in columns:
        cursor.execute('ALTER TABLE cookies ADD COLUMN encrypted INTEGER DEFAULT 0')
    connection.commit()
    connection.close()


def get_encryption_key():
    """
    creates a key for encrypting the cookies in the database and stores it in the OS keyring.
    if there alread is a key stored, it is retrieved and returned.
    """
    encryption_key = keyring.get_password('Nagstamon', 'cookie_encryption_key')
    if not encryption_key:
        encryption_key = Fernet.generate_key()
        # Windows keyring stores bytes as strings like "b'keyvalue'" which confuses Fernet
        # macOS throws some pointer error, so it is happier with .decode() too
        if OS in OS_NON_LINUX:
            encryption_key = encryption_key.decode()
        keyring.set_password('Nagstamon', 'cookie_encryption_key', encryption_key)
    return encryption_key


def save_cookies(cookies):
    """
    save cookies to the SQLite database
    """
    # initialize database file for access
    init_db()
    connection = sqlite3.connect(COOKIE_DB_FILE_PATH)
    cursor = connection.cursor()
    # cookey is the unique key for each cookie
    for cookey, cookie_data in cookies.items():
        # newer cookies will be encrypted
        if encrypt_cookie:
            # get key from keyring
            encryption_key = get_encryption_key()
            fernet = Fernet(encryption_key)
            # convert value to be encrypted
            value_to_be_encrypted = cookie_data['value'].encode()
            value = fernet.encrypt(value_to_be_encrypted)
            encrypted = 1
        else:
            value = cookie_data['value']
            encrypted = 0

        cursor.execute('''
            INSERT OR REPLACE INTO cookies
            (cookey, server, name, value, domain, path, expiration, secure, httponly, encrypted)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            cookey,
            cookie_data['server'],
            cookie_data['name'],
            value,
            cookie_data['domain'],
            cookie_data['path'],
            cookie_data['expiration'],
            int(cookie_data['secure']),
            int(cookie_data['httponly']),
            encrypted
        ))
    connection.commit()
    connection.close()

def load_cookies():
    """
    load cookies from the SQLite database
    """
    # initialize database file for access
    init_db()
    connection = sqlite3.connect(COOKIE_DB_FILE_PATH)
    cursor = connection.cursor()
    cursor.execute('SELECT cookey, server, name, value, domain, path, expiration, secure, httponly, encrypted FROM cookies')
    rows = cursor.fetchall()
    connection.close()
    # initialize cookies dictionary
    cookies = {}
    # load cookies from database rows
    for row in rows:
        encrypted = bool(row[9])
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
        if encrypted:
            # get key from keyring
            encryption_key = get_encryption_key()
            fernet = Fernet(encryption_key)
            # decrypt cookie value
            value_to_be_decrypted = cookies[cookey]['value'].decode()
            # if decryption fails because of wrong key return empty string
            try:
                decrypted_value = fernet.decrypt(value_to_be_decrypted)
            except InvalidToken:
                decrypted_value = b''
            cookies[cookey]['value'] = decrypted_value.decode()
    return cookies

def purge_cookie_by_name_if_session(server_name: str, cookie_name: str):
    """
    Delete a specific cookie for a server from SQLite DB if it is a session cookie (expiration IS NULL).
    Intended to clean up persisted session cookies from older installations.
    """
    init_db()
    connection = sqlite3.connect(COOKIE_DB_FILE_PATH)
    cursor = connection.cursor()

    cursor.execute(
        'DELETE FROM cookies WHERE server = ? AND name = ? AND expiration IS NULL',
        (server_name, cookie_name)
    )

    connection.commit()
    connection.close()


def cookie_data_to_jar(server_name, cookie_data):
    """

    """
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

import time

def has_any_cookie(server_name: str, cookie_name: str) -> bool:
    cookies = load_cookies()
    for c in cookies.values():
        if c.get('server') == server_name and c.get('name') == cookie_name:
            return True
    return False

def has_valid_cookie(server_name: str, cookie_name: str, now: int | None = None, skew_seconds: int = 30) -> bool:
    """
    Return True if at least one cookie with given name has an expiration in the future.
    skew_seconds: small safety window to avoid edge cases at the boundary.
    """
    if now is None:
        now = int(time.time())

    cookies = load_cookies()
    for c in cookies.values():
        if c.get('server') != server_name:
            continue
        if c.get('name') != cookie_name:
            continue
        exp = c.get('expiration')
        if exp is None:
            continue
        if int(exp) > (now + skew_seconds):
            return True
    return False


def delete_cookie(server_name: str, cookie_name: str, domain: str | None = None, path: str | None = None) -> int:
    """
    Delete cookie rows from SQLite DB. Returns number of deleted rows.
    Optional domain/path narrow down the deletion.
    """
    init_db()
    connection = sqlite3.connect(COOKIE_DB_FILE_PATH)
    cursor = connection.cursor()

    sql = "DELETE FROM cookies WHERE server = ? AND name = ?"
    params = [server_name, cookie_name]

    if domain is not None:
        sql += " AND domain = ?"
        params.append(domain)

    if path is not None:
        sql += " AND path = ?"
        params.append(path)

    cursor.execute(sql, tuple(params))
    deleted = cursor.rowcount

    connection.commit()
    connection.close()
    return deleted


def server_has_domain_fragment(server_name: str, fragment: str) -> bool:
    """
    True if there is any cookie for server_name whose domain contains fragment.
    Used to detect whether Keycloak cookies exist at all (OIDC setup).
    """
    cookies = load_cookies()
    fragment = fragment.lower()
    for c in cookies.values():
        if c.get('server') != server_name:
            continue
        dom = (c.get('domain') or '').lower()
        if fragment in dom:
            return True
    return False
