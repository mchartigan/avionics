#! /usr/bin/python3.6
import json

from Mode import Mode
from RadioModule import Module


class Comm:
    __instance = None

    def __init__(self):
        if Comm.__instance is not None:
            raise Exception("Constructor should not be called")
        else:
            Comm.__instance = CommSingleton()

    def get_instance(self):
        print("get called")
        if Comm.__instance is None:
            print("first")
            Comm()
        else: print("not first")
        return Comm.__instance


class CommSingleton:
    def __init__(self):
        try:
            self.__radio = Module.get_instance(self)
        except Exception as e:
            print(e)
            
    def send(self, command, command_type):

        try:
            if not len(command) == 0:
                print(command)
                self.__radio.send(json.dumps(command))
        except Exception as e:
            print(e)

    def bind(self, queue):
        self.__radio.bind_queue(queue)
