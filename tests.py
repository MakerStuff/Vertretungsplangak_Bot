# coding: utf-8

import json
import os

import requests
import socket
import urllib3

import orgafunctions
import usercommands
import vertretungsplan
import config
from dsbbot import DSBBot


class DummyFunction(usercommands.UserCommand):
    short = "Dummy"
    detail = "Dummy function"
    msg = "dummy"

    def main(self,
             update_text: str,
             chat_id: int,
             database_name: str):
        output = {chat_id: {"text": self.msg}}
        return output


class Test:
    database_name = os.path.expanduser(config.data_location + "test_data.sqlite")
    token = json.loads(open(os.path.expanduser(config.data_location + "general_information.json")).read())["token"]

    def run(self):
        results = {}
        tests = [t for t in self.__dir__() if t.startswith("test_")]
        for test in tests:
            try:
                result = self.__getattribute__(test)()
                if result:
                    print(f"{test} returned {results}")
                if self.database_name.split("/")[-1] in os.listdir("/".join(self.database_name.split("/")[:-1])):
                    os.remove(self.database_name)
                else:
                    print(f"{self.database_name} not found.")
            except Exception as e:
                results[test] = e
        yield f"Ran {len(tests)} test{'s' if len(tests) != 1 else ''}."
        if results:
            yield "\nFailed tests:"
            for i, result in enumerate(results):
                yield f"{i + 1}. {result.lstrip('test')[1:]} ({type(results[result])}): {results[result]}"
        else:
            yield "\nThere were no tests encountering any errors. Add more tests to make sure your code works."

    def test_functions_with_underscore_in_name(self):
        bot = DSBBot(token=self.token,
                     database_name=self.database_name,
                     uc_test_it=DummyFunction)
        assert bot.uc_test_it("/test_it help", 0, self.database_name) == {0: {"text": DummyFunction.detail}}, \
            "Having underscores in function names raises error."

    def test_get_support(self):
        dsb_bot = DSBBot(token=self.token,
                         database_name=self.database_name,
                         uc_register=usercommands.Register)
        chat_1 = 1234
        dsb_bot.run_command(update_text="/register",
                            chat_id=chat_1,
                            database_name=self.database_name)
        supporter_1 = orgafunctions.get_support(chat_1, database_name=self.database_name)
        assert supporter_1 == chat_1, \
            f"Assigning support to first chat does not work correctly ({chat_1} -> {supporter_1})"
        chat_2 = 5678
        dsb_bot.run_command(update_text="/register",
                            chat_id=chat_2,
                            database_name=self.database_name)
        supporter_2 = orgafunctions.get_support(chat_2, self.database_name)
        assert supporter_2 == chat_1, \
            f"Assigning support to a second chat does not work correctly ({chat_2} -> {supporter_1})"

    def test_add_and_view_lesson(self):
        dsb_bot = DSBBot(token=self.token,
                         database_name=self.database_name,
                         uc_register=usercommands.Register,
                         uc_add_lesson=usercommands.AddLesson,
                         uc_view_lessons=usercommands.ViewLessons)
        chat_id = 1234
        dsb_bot.run_command(update_text="/register",
                            chat_id=chat_id,
                            database_name=self.database_name)
        lesson = "12 Montag 3 Bio Nm2"
        dsb_bot.run_command(update_text="/add_lesson " + lesson,
                            chat_id=chat_id,
                            database_name=self.database_name)
        response = dsb_bot.run_command(update_text="/view_lessons",
                                       chat_id=chat_id,
                                       database_name=self.database_name)
        assert lesson in response[chat_id]["text"], "Lessons are not stored correctly."

    def test_help_for_function(self):
        dsb_bot = DSBBot(token=self.token,
                         database_name=self.database_name,
                         uc_dummy=DummyFunction)
        chat_id = 0
        response = dsb_bot.run_command("/dummy help", chat_id, self.database_name)
        assert response == {chat_id: {"text": DummyFunction.detail}}, \
            "Asking for help of a function returned wrong content"

    def test_create_lesson_from_list(self):
        class_name = '05A'
        subject = 'Deu',
        room = '1.23'
        period = '1'
        week_day = 'Mo'
        week_type = 'A'
        lesson = vertretungsplan.Lesson('').from_list([class_name,
                                                       subject,
                                                       room,
                                                       period,
                                                       week_day,
                                                       week_type])
        try:
            assert lesson.class_name == class_name
            assert lesson.orig_subject == subject
            assert lesson.orig_room == room
            assert lesson.period == period
            assert lesson.week_day == week_day
            assert lesson.week_type == week_type
        except AssertionError as e:
            if not e.args:
                raise AssertionError("Lesson creation does not work")
            else:
                raise e

    def test_lesson_equals_vertretung(self):
        class_name = "05A"
        subject = "Deu"
        orig_subject = "Ma"
        room = "1.23"
        orig_room = "1.11"
        period = "1"
        week_day = "Mo"
        week_type = "A"
        vertretung = vertretungsplan.Vertretung(class_name=class_name,
                                                period=period,
                                                subject=subject,
                                                orig_subject=orig_subject,
                                                room=room,
                                                orig_room=orig_room,
                                                repl_from="---",
                                                repl_type="Entfall",
                                                desc="None",
                                                week_day=week_day,
                                                week_type=week_type)
        lesson = vertretungsplan.Lesson(class_name=class_name,
                                        period=period,
                                        subject=orig_subject,
                                        room=orig_room,
                                        week_day=week_day,
                                        week_type=week_type)
        assert lesson == vertretung, "Lesson and Vertretung are not equal"

    def test_detecting_lessons(self):
        try:
            username = "213061"
            password = "dsbgak"
            url = vertretungsplan.get_url(username=username,
                                          password=password)
            doc = vertretungsplan.get_doc(url=url)
            vertretungen = vertretungsplan.vertretungsplan(doc=doc)
            kursliste = [vertretungsplan.Lesson(class_name=vertretungen[0]["class_name"],
                                                subject=vertretungen[0]["subject"],
                                                room=vertretungen[0]["room"],
                                                period=vertretungen[0]["period"],
                                                week_day=vertretungen[0]["week_day"],
                                                week_type=vertretungen[0]["week_type"])]
            assert kursliste != [], "Kursliste ist leer"
            rel = vertretungsplan.get_relevant(kursliste=kursliste,
                                               vertretungs_plan=vertretungen)
            assert kursliste[0] in rel, "Kurs nicht unter relevanten Eintraegen"
        except requests.exceptions.ConnectionError:
            print("WARNING: Aborted due to network connection error.")
        except urllib3.exceptions.MaxRetryError:
            print("WARNING: Aborted due to max retry network error.")
        except urllib3.exceptions.NewConnectionError:
            print("WARNING: Aborted due to new connection network error.")
        except socket.gaierror:
            print("WARNING: Aborted due to temporary failure in name resolution.")
        except Exception as e:
            if "No login method worked properly" in e.args:
                print("WARNING: Aborted due to no login method worked properly.")

    def test_user_detecting_lessons(self):
        dsb_bot = DSBBot(token=self.token,
                         database_name=self.database_name,
                         uc_register=usercommands.Register,
                         uc_add_lesson=usercommands.AddLesson,
                         uc_information=usercommands.Information)
        chat_id = 0
        dsb_bot.run_command("/register", chat_id, self.database_name)
        dsb_bot.run_command("/add_lesson 05A Montag 1 Deu 1.23", chat_id=chat_id, database_name=self.database_name)
        result = dsb_bot.run_command("/information", chat_id=chat_id, database_name=self.database_name)
        assert dsb_bot.uc_information.no_relevants in result[chat_id]["text"]
        # TODO This test gatheres data from 21301/dsbgak to test if lessons are detected


if __name__ == "__main__":
    tester = Test()
    print("Running tests")
    print("\n".join(tester.run()))
