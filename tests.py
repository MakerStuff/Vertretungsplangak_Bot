import builtins
import json
import os

from dsbbot import DSBBot
from orgafunctions import get_support
import usercommands


class DummyFunction(usercommands.UserCommand):
    short = "Dummy"
    detail = "Dummy function"
    msg = "dummy"

    def main(self,
             update_text: str,
             chat_id: int,
             database_name: str):
        return {chat_id: {"text": self.msg}}


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

    def test_functions_with_underscore_in_name(self):
        bot = DSBBot(token=json.loads(open("../Vertretungsplangak_Data/general_information.json").read())["token"],
                     database_name=self.database_name,
                     uc_test_it=DummyFunction)
        assert bot.uc_test_it("/test_it help", 0, self.database_name) == {0: {"text": DummyFunction.detail}}, \
            "Having underscores in function names raises error."

    def test_get_support(self):
        dsb_bot = DSBBot(token=json.loads(open("../Vertretungsplangak_Data/general_information.json").read())["token"],
                         database_name=self.database_name,
                         uc_register=usercommands.Register)
        chat_1 = 1234
        dsb_bot.run_command(update_text="/register",
                            chat_id=chat_1,
                            database_name=self.database_name)
        supporter_1 = get_support(chat_1, self.database_name)
        assert supporter_1 == chat_1, \
            f"Assigning support to first chat does not work correctly ({chat_1} -> {supporter_1})"
        chat_2 = 5678
        dsb_bot.run_command(update_text="/register",
                            chat_id=chat_2,
                            database_name=self.database_name)
        supporter_2 = get_support(chat_2, self.database_name)
        assert supporter_2 == chat_1, \
            f"Assigning support to another chat does not work correctly ({chat_2} -> {supporter_1})"

    def test_add_and_view_lesson(self):
        dsb_bot = DSBBot(token=json.loads(open("../Vertretungsplangak_Data/general_information.json").read())["token"],
                         database_name=self.database_name,
                         uc_register=usercommands.Register,
                         uc_add_lesson=usercommands.AddLesson,
                         uc_view_lessons=usercommands.ViewLessons)
        chat_id = 1234
        dsb_bot.run_command(update_text="/register",
                            chat_id=chat_id,
                            database_name=self.database_name)
        lesson = "12 Mo 3 Bio Nm2"
        dsb_bot.run_command(update_text="/add_lesson " + lesson,
                            chat_id=chat_id,
                            database_name=self.database_name)
        print("Added lesson")
        response = dsb_bot.run_command(update_text="/view_lessons",
                                       chat_id=chat_id,
                                       database_name=self.database_name)
        assert lesson in response[chat_id]["text"], "Lessons are not stored correctly."

    def test_help_for_function(self):
        dsb_bot = DSBBot(token=json.loads(open("../Vertretungsplangak_Data/general_information.json").read())["token"],
                         database_name=self.database_name,
                         uc_dummy=DummyFunction)
        chat_id = 0
        response = dsb_bot.run_command("/dummy help", chat_id, self.database_name)
        assert response == {chat_id: {"text": DummyFunction.detail}},\
            "Asking for help of a function returned wrong content"


if __name__ == "__main__":
    tester = Test()
    print("Running tests")
    print("\n".join(tester.run()))
