import builtins
import json
import os

from dsbbot import DSBBot
from orgafunctions import get_support
import usercommands


class Test:
    database_name = "../Vertretungsplangak_Data/test_data.sqlite"

    def run(self):
        results = {}
        tests = [t for t in self.__dir__() if t.startswith("test_")]
        for test in tests:
            try:
                result = self.__getattribute__(test)()
                if result:
                    print(f"{test} returned {results}")
                os.remove(self.database_name)
            except Exception as e:
                results[test] = e
        yield f"Ran {len(tests)} test{'s' if len(tests) != 1 else ''}."
        if results:
            yield "\nFailed tests:"
            for i, result in enumerate(results):
                yield f"{i+1}. {result.lstrip('test')[1:]} ({type(results[result])}): {results[result]}"
        else:
            yield "\nThere were no tests encountering any errors. Add more tests to make sure your code works."

    def test_functions(self):
        def test(update_text, chat_id, database_name):
            return {chat_id: "Test"}
        bot = DSBBot(token=json.loads(open("../Vertretungsplangak_Data/general_information.json").read())["token"],
                     database_name=self.database_name,
                     uc_test=test)
        assert bot.uc_test("", 0, "") == {0: "Test"}, "Calling functions of a bot does not work."

    def test_functions_with_underscore_in_name(self):
        def test(update_text,
                 chat_id,
                 database_name):
            return {chat_id: "Test"}
        bot = DSBBot(token=json.loads(open("../Vertretungsplangak_Data/general_information.json").read())["token"],
                     database_name=self.database_name,
                     uc_test_something=test)
        assert bot.uc_test_something("", 0, "") == {0: "Test"}, "Having underscores in function names raises an error."

    def test_get_support(self):
        dsbbot = DSBBot(token=json.loads(open("../Vertretungsplangak_Data/general_information.json").read())["token"],
                        database_name=self.database_name,
                        uc_register=usercommands.Register())
        chat_1 = 1234
        dsbbot.uc_register(update_text="/register",
                           chat_id=chat_1,
                           database_name=self.database_name)
        supporter_1 = get_support(chat_1, self.database_name)
        assert supporter_1 == chat_1,\
            f"Assigning support to first chat does not work correctly ({chat_1} -> {supporter_1})"
        chat_2 = 5678
        dsbbot.uc_register(update_text="/register",
                           chat_id=chat_2,
                           database_name=self.database_name)
        supporter_2 = get_support(chat_2, self.database_name)
        assert supporter_2 == chat_1,\
            f"Assigning support to another chat does not work correctly ({chat_2} -> {supporter_1})"

    def test_add_and_view_lesson(self):
        dsbbot = DSBBot(token=json.loads(open("../Vertretungsplangak_Data/general_information.json").read())["token"],
                        database_name=self.database_name,
                        uc_register=usercommands.Register(),
                        uc_add_lesson=usercommands.AddLesson(),
                        uc_view_lessons=usercommands.ViewLessons())
        chat_id = 1234
        dsbbot.uc_register(update_text="/regster",
                           chat_id=chat_id,
                           database_name=self.database_name)
        lesson = "12 Mo 3 Bio Nm2"
        dsbbot.uc_add_lesson(update_text="/add_lesson " + lesson,
                             chat_id=chat_id,
                             database_name=self.database_name)
        print("Added lesson")
        response = dsbbot.uc_view_lessons(update_text="/view_lesson",
                                          chat_id=chat_id,
                                          database_name=self.database_name)
        assert lesson in response[chat_id]["text"], "Lessons are not stored correctly."


if __name__ == "__main__":
    tester = Test()
    print("Running tests")
    print("\n".join(tester.run()))
