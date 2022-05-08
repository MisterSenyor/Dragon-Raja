import hashlib
import os

from mysql.connector import connect

from my_server import *


def hash_password(password: str, salt):
    key = hashlib.pbkdf2_hmac(
        'sha256',
        password.encode(ENCODING),
        salt,
        100000
    )
    return key


class DBAPI:
    def __init__(self, user, password, port):
        self.connection = connect(
            host='localhost',
            user=user,
            password=password,
            port=port,
        )
        self.cursor = self.connection.cursor()
        self.create_db()
        logging.debug('database is running')

    def create_db(self):
        try:
            self.cursor.execute('CREATE DATABASE IF NOT EXISTS %s' % DATABASE_NAME)
            self.cursor.execute('USE %s' % DATABASE_NAME)
            self.cursor.execute(
                'CREATE TABLE IF NOT EXISTS users(username VARCHAR(256), hash VARCHAR(256), salt VARCHAR(256))')
            self.cursor.execute(
                'CREATE TABLE IF NOT EXISTS players(username VARCHAR(256), player VARCHAR(1024))',
                {'database': DATABASE_NAME}
            )
        except Exception:
            logging.exception('db exception')
            self.close()

    def store_player(self, player):
        try:
            username = player.username if isinstance(player, Player) else player['username']
            player_data = json_encode(player, items=True)
            self.cursor.execute("INSERT INTO players VALUES (%(username)s, %(player)s)",
                                {'username': username, 'player': player_data})
            self.connection.commit()
        except Exception:
            logging.exception('db exception')
            self.close()

    def update_players(self, players):
        try:
            self.cursor.executemany(
                'UPDATE players SET player = %(player)s WHERE username = %(username)s',
                [{
                    'username': player.username if isinstance(player, Player) else player['username'],
                    'player': json_encode(player)
                } for player in players]
            )
            self.connection.commit()
        except Exception:
            logging.exception('db exception')
            self.close()

    def retrieve_player(self, username) -> Optional[Player]:
        try:
            self.cursor.execute('SELECT player FROM players WHERE username = %(username)s', {'username': username})
            result = self.cursor.fetchone()
            if result is None:
                return None
            return player_from_dict(json.loads(result[0]))
        except Exception:
            logging.exception('db exception')
            self.close()

    def delete_player(self, username):
        try:
            self.cursor.execute('DELETE FROM players WHERE username = %(username)s', {'username': username})
            self.connection.commit()
        except Exception:
            logging.exception('db exception')
            self.close()

    def verify_account(self, username, password):
        try:
            query = "SELECT hash, salt FROM users WHERE username = %(username)s"
            self.cursor.execute(query, {'username': username})
            result = self.cursor.fetchone()
            if result is None:
                return False
            hash_, salt = result
            return hash_password(password, bytes.fromhex(salt)) == bytes.fromhex(hash_)
        except Exception:
            logging.exception('db exception')
            self.close()

    def add_account(self, username, password):
        try:
            salt = os.urandom(32)
            hash_ = hash_password(password, salt)
            query = "INSERT INTO users (username, hash, salt) VALUES (%s, %s, %s)"
            self.cursor.execute(query, (username, hash_.hex(), salt.hex()))
            self.connection.commit()
        except Exception:
            logging.exception('db exception')
            self.close()

    def remove_account(self, username):
        try:
            self.cursor.execute("DELETE FROM users WHERE username = %(username)s", {'username': username})
            self.connection.commit()
        except Exception:
            logging.exception('db exception')
            self.close()

    def check_account_exists(self, username):
        try:
            self.cursor.execute('SELECT * FROM USERS WHERE username = %(username)s', {'username': username})
            result = self.cursor.fetchone()
            return result is not None
        except Exception:
            logging.exception('db exception')
            self.close()

    def close(self):
        self.cursor.close()
        self.connection.close()
