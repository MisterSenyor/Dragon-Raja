import string
from unicodedata import decimal
from mysql.connector import connect, Error
from entities import Entity, Item
from settings import *
from settings import DATABASE_ERRORS
from my_server import Player


class database():

    ITEMS = dict(strength_pot='1', health_pot='2', speed_pot='3', usless_card='4')

    def __init__(self) -> None:
        self.user = 'root'
        self.password = 'Shmulik1sKing!'
        
    def create_database(self):
        with self.connect_database() as db:
            if db is None:
                return DATABASE_ERRORS['Connection_Error']
            

    def connect_database(self):  # connection must be closed after calling this function!
        try:
            connection = connect(
                host='localhost',  # 127.0.0.1
                user=self.user,  # Change to some sort of environment variable
                password=self.password,
                port=DATABASE_PORT,
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
            query = "INSERT INTO players VALUES ('%s', '%s', %s, %s, %s, %s, %s)" % (
            player.username, player.id, posX, posY, player.t0, items)
            try:
                with db.cursor() as cursor:
                    cursor.execute(query, multimode=True)
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


    def verify_account(self, username, password):
        with self.connect_database() as db:
            if db is None:
                return DATABASE_ERRORS['Connection_Error']
            query = "SELECT password, ID FROM users WHERE username = %(username)s"
            with db.cursor() as cursor:
                cursor.execute(query, {'username': username})
                result = cursor.fetchall()  # returns a list with a tuple inside [(password, ID)]
                if result is None or result == []:
                    return DATABASE_ERRORS['No_Such_User']
                passwd, ID = result[0]
                if password != passwd:  # add better checking function
                    return DATABASE_ERRORS['Wrong_Password']
        return ID


    def add_account(self, username, password, ID):
        with self.connect_database() as db:
            if db is None:
                return DATABASE_ERRORS['Connection_Error']
            if (self.username_exists(username)):
                return DATABASE_ERRORS['Username_Exists']
            query = "INSERT INTO users VALUES ('%s', '%s', '%s')" % (username, password, ID)  # check for sql injection
            with db.cursor() as cursor:
                try:
                    cursor.execute(query, multi=True)
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
            query = "DELETE FROM users WHERE ID = %(ID)s"  # check for sql injection
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


    def get_item(self, item_num):
        for item, num in database.ITEMS.items():
            if item_num == num:
                return item
        return DATABASE_ERRORS['Database_Error']


def main():
    db = database()
    print(db.add_account(input('username: '), input('password: '), input('ID: ')))
    print(db.verify_account(input('username: '), input('password: ')))


if __name__ == '__main__':
    main()
