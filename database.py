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
        self.cursor.execute('CREATE DATABASE IF NOT EXISTS %s' % DATABASE_NAME)
        self.cursor.execute('USE %s' % DATABASE_NAME)
        self.cursor.execute(
            'CREATE TABLE IF NOT EXISTS users(username VARCHAR(256), hash VARCHAR(256), salt VARCHAR(256))')
        self.cursor.execute(
            'CREATE TABLE IF NOT EXISTS players(username VARCHAR(256), player VARCHAR(1024))',
            {'database': DATABASE_NAME}
        )

    def store_player(self, player: Player):
        self.cursor.execute("INSERT INTO players VALUES (%(username)s, %(player)s)",
                            {'username': player.username, 'player': json.dumps(player, cls=MyJSONEncoder)})
        self.connection.commit()

    def retrieve_player(self, username) -> Optional[Player]:
        self.cursor.execute('SELECT player FROM players WHERE username = %(username)s', {'username': username})
        result = self.cursor.fetchone()
        if result is None:
            return None
        return player_from_dict(json.loads(result[0]))

    def delete_player(self, username):
        self.cursor.execute('DELETE FROM players WHERE username = %(username)s', {'username': username})
        self.connection.commit()

    def verify_account(self, username, password):
        query = "SELECT hash, salt FROM users WHERE username = %(username)s"
        self.cursor.execute(query, {'username': username})
        result = self.cursor.fetchone()
        if result is None:
            return False
        hash_, salt = result
        return hash_password(password, bytes.fromhex(salt)) == bytes.fromhex(hash_)

    def add_account(self, username, password):
        salt = os.urandom(32)
        hash_ = hash_password(password, salt)
        query = "INSERT INTO users (username, hash, salt) VALUES (%s, %s, %s)"
        self.cursor.execute(query, (username, hash_.hex(), salt.hex()))
        self.connection.commit()

    def remove_account(self, username):
        self.cursor.execute("DELETE FROM users WHERE username = %(username)s", {'username': username})
        self.connection.commit()


def main():
    db = DBAPI(user=os.environ['MYSQL_USER'], password=os.environ['MYSQL_PASSWORD'], port=os.environ['MYSQL_PORT'])
    db.add_account(input('username: '), input('password: '))
    # print(db.add_account(input('username: '), input('password: ')))
    # print(db.verify_account(input('username: '), input('password: ')))
    # print(db.verify_account(input('username: '), input('password: ')))
    # items = {str(generate_id()): "speed_pot", str(generate_id()): "heal_pot"}
    # cooldowns = {'skill': Cooldown(duration=0, t0=0), 'projectile': Cooldown(duration=0, t0=0)}
    # player = MainPlayer(id=100, start_pos=(1400, 1360), end_pos=None,
    #                     health=100, items=items, t0=0, username='jack', effects=[], cooldowns=cooldowns)
    # db.store_player(player)


if __name__ == '__main__':
    main()
