from mysql.connector import connect, Error
from entities import Entity
from settings import *
from settings import DATABASE_ERRORS
from my_server import Player

ITEMS = dict(strength_pot = 1, health_pot = 2, speed_pot = 4, usless_card = 8)

def connect_database():                                             # connection must be closed after calling this function!
    try:
        connection = connect(
            host='localhost',                                        # 127.0.0.1
            user='root',                                            # Change to some sort of environment variable 
            password='Shmulik1sKing!',
            port=DATABASE_PORT,
            database=DATABASE_NAME,
        )
        return connection
    except Error as e:
        print(e)
        return None                                                     # none (may change) means database error, needs to be handled after every call

def store_player(player: Player):   # I'm unsure about how to check this function
    with connect_database() as db:
        if db is None:
            return DATABASE_ERRORS['Connection_Error']
        posX, posY = player.start_pos
        items: int
        for item in player.items:
            items += ITEMS[str(item)]
        query = "INSERT INTO players VALUES ('%s', '%s', '%s', '%s', '%s', '%s', '%s')"%(player.username, player.id, posX, posY, player.t0, items)
        try:
            with db.cursor() as cursor:
                cursor.execute(query, multimode = True)
                db.commit()
        except Error as e:
            print(e)
            return(DATABASE_ERRORS['Database_Error'])
    return None

def retrive_player(id):
    with connect_database() as db:
        if db is None:
            return DATABASE_ERRORS['Connection_Error']
        query = "SELECT * FROM users WHERE ID = %(ID)s"
        try:
            with db.cursor() as cursor:
                cursor.execute(query, {'ID': id})
                result = cursor.fetchall() 
                if result is None or result == []:
                    return DATABASE_ERRORS['No_Such_Player']
        except Error as e:
            print(e)
            return DATABASE_ERRORS['Database_Error']
        delete_player(id)
        return result[0]            # temporary, needs to return new instance of player. returns now tuple (username, ID, posX, posY, t0, health, items(in binary form))                     

def delete_player(id):
    with connect_database() as db:
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

def verify_account(username, password):
    with connect_database() as db:
        if db is None:
            return DATABASE_ERRORS['Connection_Error']
        query = "SELECT password, ID FROM users WHERE username = %(username)s" 
        with db.cursor() as cursor:
            cursor.execute(query, {'username': username})
            result = cursor.fetchall()                                          # returns a list with a tuple inside [(password, ID)]                                         
            if result is None or result == []:
                return DATABASE_ERRORS['No_Such_User']
            passwd, ID = result[0]
            if password != passwd:                                              # add better checking function
                return DATABASE_ERRORS['Wrong_Password'] 
    return ID

def add_account(username, password, ID):
    with connect_database() as db:
        if db is None:
            return DATABASE_ERRORS['Connection_Error']
        if(username_exists(username)):
            return DATABASE_ERRORS['Username_Exists']
        query = "INSERT INTO users VALUES ('%s', '%s', '%s')"%(username, password, ID)          # check for sql injection
        with db.cursor() as cursor:
            try:
                cursor.execute(query, multi = True)
                db.commit()
                print(query)
            except Error as e:
                print(e)
                return DATABASE_ERRORS['Database_Error']
    return None                                                                          # None means it was succeseful

def remove_account(id):
    with connect_database() as db:
        if db is None:
            return DATABASE_ERRORS['Connection_Error']
        query = "DELETE FROM users WHERE ID = %(ID)s"          # check for sql injection
        with db.cursor() as cursor:
            try:
                cursor.execute(query, {'ID': id})
                db.commit()
            except Error as e:
                print(e)
                return DATABASE_ERRORS['Database_Error']
    return None                                                                          # None means it was succeseful

def username_exists(username):
    with connect_database() as db:
        if db is None:
            return DATABASE_ERRORS['Connection_Error']
        query = "SELECT username FROM users WHERE EXISTS (SELECT * FROM users WHERE username = %(username)s)"       # check if username exists
        with db.cursor() as cursor:
            cursor.execute(query, {'username': username})
            result = cursor.fetchall()                                         # returns a list with a tuple inside [(password, ID)]                                         
            if result:
                return True
    return False


def main():
    print(add_account(input('username: '), input('password: '), input('ID: ')))
    print(verify_account(input('username: '), input('password: ')))


if __name__ == '__main__':
    main()


