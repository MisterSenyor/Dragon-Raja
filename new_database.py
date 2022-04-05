#from entities import Entity, Item
from settings import *
from settings import DATABASE_ERRORS
from my_server import Player
import json
import hashlib
import os


class database():

    ITEMS = dict(strength_pot='1', health_pot='2', speed_pot='3', usless_card='4')

    def __init__() -> None:
        try:
            file = open(USERS_FILE, 'a+')
            file.close()
            file = open(PLAYERS_FILE, 'a+')
            file.close
        except OSError as e:
            print(e)
            return DATABASE_ERRORS['Database_Error']


    def verify_user(username: str, password: str):
        try:
            with open(USERS_FILE, 'r') as file:
                file.seek(0)
                for line in file.readlines():
                    print(line)
                    data = json.loads(line)
                    if data['username'] == username:
                        if database.hash_password(password, data['salt'].encode()) == data['password']:
                            return data['id']
                        return DATABASE_ERRORS['Wrong_Password']
                return DATABASE_ERRORS['No_Such_User']
        except OSError or TypeError as e:
            print(e)
            return DATABASE_ERRORS['Database_Error']
                    
    
    def add_user(username: str, password: str, id: int):
        valid = database.username_exists(username)
        if type(valid) != type(bool()):
            return valid
        elif valid:
            return DATABASE_ERRORS['Username_Exists']
        salt = os.urandom(32)
        encrypted = database.hash_password(password, salt)
        data = {'username': username, 'password': encrypted, 'salt': str(salt), 'id': id}
        try:
            with open(USERS_FILE, 'a') as file:
                #print(json.dump(data, file))
                print(data)
                json.dump(data, file)
                file.write('\r\n')
        except TypeError or OSError as e:
            print(e)
            return DATABASE_ERRORS['Database_Error']
        return None


    def username_exists(username: str):
        try:
            with open(USERS_FILE, 'r') as file:
                #file.seek(0)
                for line in file.readlines():
                    print(line)
                    print(len(line))
                    if len(line) > 1:
                        if json.loads(line)['username'] == username:
                            return True
                return False
        except TypeError or OSError as e:
            print(e)
            return DATABASE_ERRORS['Database_Error']

    
    def hash_password(password: str, salt):
        key = hashlib.pbkdf2_hmac(
            'sha256', 
            password.encode(ENCODING), 
            salt, 
            100000 
        )
        return str(key)
            
    
    def store_player(player: Player):
        data = dict(id=player.id, start_pos=player.start_pos, health=player.health, items=player.items, t0=player.t0, username=player.username)
        try:
            with open(PLAYERS_FILE, 'a') as file:
                json.dump(data, file)
                file.write('\r\n')
                file.truncate()
        except TypeError or OSError as e:
            print(e)
            return DATABASE_ERRORS['Database_Error']
        return None


    def retrive_player(id: int):
        try:
            with open(PLAYERS_FILE, 'r') as file:
                file.seek(0)
                for line in file.readlines():
                    print(line)
                    data = json.loads(line)
                    if data['id'] == id:
                        return Player(id=data['id'], start_pos=data['start_pos'], t0=data['t0'], end_pos=None, health=data['health'], username=data['username'], items=data['items'])
        except TypeError or OSError as e:
            print(e)
            return DATABASE_ERRORS['Database_Error']


    def delete_player(id: int):
        with open(PLAYERS_FILE, "r+") as file:
            file.seek(0)
            for line in file.readlines:
                if json.loads(line)[id] != id:
                    file.write(line)
            file.truncate()        
                    

def main():
    database.__init__() 
    database.add_user(input('username: '), input('password: '), input('id: '))
    print(database.verify_user(input('username: '), input('password: ')))


if __name__ == '__main__':
    main()
