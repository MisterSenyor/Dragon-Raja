from unittest import result
from xmlrpc.client import ProtocolError
from mysql.connector import connect, Error
from settings import *
from settings import DATABASE_ERRORS
from my_server import Player
import hashlib
import os


class database():

    ITEMS = dict(strength_pot='1', health_pot='2', speed_pot='3', usless_card='4')

    def __init__(self, user='root', password='Shmulik1sKing!', port=3060 ) -> None:
        self.user = user
        self.password = password
        self.port = port
        self.create_database()

        
    def create_database(self):
        db = self.database_exists()
        if db == DATABASE_ERRORS['Connection_Error']:
            return db
        elif db:
            return
        print(db)
        try:
            with connect(
                host='localhost',  # 127.0.0.1
                user=self.user,  
                password=self.password,
                port=self.port,
                auth_plugin='mysql_native_password',
            ) as server:
                with server.cursor() as cursor:
                    cursor.execute('CREATE DATABASE %s' % (DATABASE_NAME))
                return self.create_tables()
        except Error as e:
            print(e)
            return DATABASE_ERRORS['Connection_Error']


    def database_exists(self):
        try:
            with connect(
                host='localhost',  # 127.0.0.1
                user=self.user,  
                password=self.password,
                port=self.port,
                auth_plugin='mysql_native_password',
            ) as server:
                cursor = server.cursor()
                cursor.execute('SHOW DATABASES')
                for dbname in cursor:
                    print(dbname[0])
                    if dbname[0] == DATABASE_NAME:
                        cursor.fetchall()
                        cursor.close()
                        with self.connect_database() as db:
                            if db is None:
                                return DATABASE_ERRORS['Connection_Error']
                            cursor = db.cursor()
                            cursor.execute('SHOW TABLES')
                            tablenames = cursor.fetchall()
                            print(tablenames)
                            if tablenames == [('players',), ('users',)]:
                                cursor.fetchall()
                                cursor.close()
                                return True
                            cursor.fetchall()
                            cursor.close()
                            cursor = db.cursor()
                            cursor.execute('DROP DATABASE %s' % (DATABASE_NAME))
                            cursor.fetchall()
                            cursor.close()
                            break
            return False
        except Error as e:
            print(e)
            return DATABASE_ERRORS['Connection_Error']

    
    def create_tables(self):
        with self.connect_database() as db:
            if db is None:
                return DATABASE_ERRORS['Connection_Error']
            query = 'CREATE TABLE Users(ID INT AUTO_INCREMENT, username VARCHAR(256), hash VARBINARY(256), salt VARBINARY(256), PRIMARY KEY (ID)); create table players(username varchar(256), ID INT(255), posX INT(255), posY INT(255), t0 INT(255), health smallint(255), items VARCHAR(15))'
            try:
                with db.cursor() as cursor:
                    cursor.execute(query, multi=True)
            except Error as e:
                print(e)
                return DATABASE_ERRORS['Database_Error']
        return None    


    def connect_database(self):  # connection must be closed after calling this function!
        try:
            connection = connect(
                host='localhost',  # 127.0.0.1
                user=self.user,  
                password=self.password,
                port=self.port,
                database=DATABASE_NAME,
            )
            return connection
        except Error as e:
            print(e)
            return None  # none (may change) means database error, needs to be handled after every call


    def store_player(self, player: Player):  
        with self.connect_database() as db:
            if db is None:
                return DATABASE_ERRORS['Connection_Error']
            posX, posY = player.start_pos
            items = '0000000000000000'
            i = 0
            for item in player.items:
                items[i] = database.ITEMS[str(item)]
                i += 1
            items = int(items, base=10)
            query = "INSERT INTO players VALUES ('%s', %s, %s, %s, %s, %s, %s)" % (
            player.username, player.id, posX, posY, player.t0, player.health, items)
            try:
                with db.cursor() as cursor:
                    cursor.execute(query)
                    db.commit()
            except Error as e:
                print(e)
                return (DATABASE_ERRORS['Database_Error'])
        return None


    def retrive_player(self, id):
        with self.connect_database() as db:
            if db is None:
                return DATABASE_ERRORS['Connection_Error']
            query = "SELECT * FROM users WHERE ID = %(ID)s"
            try:
                with db.cursor() as cursor:
                    cursor.execute(query, {'ID': id})
                    result = cursor.fetchall()
                    if result is None or result == []:
                        return DATABASE_ERRORS['No_Such_Player']
                    self.delete_player(id)
                    id, username, posX, posY, health, t0, item_num = result[0]
                    items = [str, str]
                    slot = 0
                    for num in str(item_num):
                        items.append(str(slot), self.get_item(num))
                        slot += 1
                    player = Player(id=id, start_pos=(posX, posY), t0=t0, end_pos=None, health=health, username=username, items=items)
                    return player
            except Error as e:
                print(e)
                return DATABASE_ERRORS['Database_Error']


    def delete_player(self, id):
        with self.connect_database() as db:
            if db is None:
                return DATABASE_ERRORS['Connection_Error']
            query = "DELETE FROM users WHERE ID = %(ID)s"
            try:
                with db.cursor() as cursor:
                    cursor.execute(query, {'ID': id})
                    db.commit()
            except Error as e:
                print(e)
                return DATABASE_ERRORS['Database_Error']
        return None


    def get_item(self, item_num):
        for item, num in database.ITEMS.items():
            if item_num == num:
                return item
        return DATABASE_ERRORS['Database_Error']


    def verify_account(self, username, password):
        with self.connect_database() as db:
            if db is None:
                return DATABASE_ERRORS['Connection_Error']
            query = "SELECT id, hash, salt FROM users WHERE username = %(username)s"
            with db.cursor() as cursor:
                cursor.execute(query, {'username': username})
                result = cursor.fetchall()  # returns a list with a tuple inside [(id, hash, salt)]
                if result is None or result == []:
                    return DATABASE_ERRORS['No_Such_User']
                id, hash, salt = result[0]
                print(bytes(salt))
                inhash = self.hash_password(password, bytes(salt))
                if inhash != bytes(hash):  
                    return DATABASE_ERRORS['Wrong_Password']
        return id


    def add_account(self, username, password):
        with self.connect_database() as db:
            if db is None:
                return DATABASE_ERRORS['Connection_Error']
            if (self.username_exists(username)):
                return DATABASE_ERRORS['Username_Exists']
            salt = os.urandom(32)
            print(salt)
            hash = self.hash_password(password, salt)
            print(hash)
            query = "INSERT INTO users (username, hash, salt) VALUES ('%s', 0x%s, 0x%s)" % (username, hash.hex(), salt.hex())  # check for sql injection
            print(query)
            with db.cursor() as cursor:
                try:
                    cursor.execute(query)
                    db.commit()
                    print(query)
                except Error as e:
                    print(e)
                    return DATABASE_ERRORS['Database_Error']
        return None  # None means it was succeseful


    def remove_account(self, id):
        with self.connect_database() as db:
            if db is None:
                return DATABASE_ERRORS['Connection_Error']
            query = "DELETE FROM users WHERE id = %(ID)s"  # check for sql injection
            with db.cursor() as cursor:
                try:
                    cursor.execute(query, {'ID': id})
                    db.commit()
                except Error as e:
                    print(e)
                    return DATABASE_ERRORS['Database_Error']
        return None  # None means it was succeseful


    def username_exists(self, username):
        with self.connect_database() as db:
            if db is None:
                return DATABASE_ERRORS['Connection_Error']
            query = "SELECT username FROM users WHERE EXISTS (SELECT * FROM users WHERE username = %(username)s)"  # check if username exists
            with db.cursor() as cursor:
                cursor.execute(query, {'username': username})
                result = cursor.fetchall()  # returns a list with a tuple inside [(password, ID)]
                if result:
                    return True
        return False


    def hash_password(self, password: str, salt):
        key = hashlib.pbkdf2_hmac(
            'sha256', 
            password.encode(ENCODING), 
            salt, 
            100000 
        )
        return key


def main():
    db = database()
    #print(db.add_account(input('username: '), input('password: ')))
    #print(db.add_account(input('username: '), input('password: ')))
    print(db.verify_account(input('username: '), input('password: ')))
    print(db.verify_account(input('username: '), input('password: ')))



if __name__ == '__main__':
    main()
