import builtins
import json

import vertretungsplan_bot


class Test:
    def run(self):
        results = {}
        for test in self.__dir__():
            if test.startswith("test"):
                try:
                    result = self.__getattribute__(test)()
                    if result:
                        print(f"{test} returned {results}")
                except Exception as e:
                    results[test] = e
        if results:
            yield "\nFailed tests:"
            for i, result in enumerate(results):
                yield f"{i+1}. ({result.lstrip('test')[1:]}): {results[result]}"
        else:
            yield "\nThere were no tests encountering any errors."

    def test_if_tests_work(self):
        for func in vertretungsplan_bot.__dir__():
            if func.startswith("uc") and func not in ["uc_test"]:
                assert callable(vertretungsplan_bot.__getattribute__(func)), f"{func} is not callable"

    def test_help(self):
        assert vertretungsplan_bot.uc_help_text(user_id=0, text="/help auskunft")

    def test_start(self):
        assert vertretungsplan_bot.uc_start(user_id=0)["0"], "start does not return expected content"

    def test_is_support(self):
        assert type(vertretungsplan_bot.is_support(user_id=0)) is bool, "is_support did not return bool"

    def test_sort_timetable(self):
        input = [["12", "Mo", "4", "bio", "nm2"], ["12", "Mo", "3", "Bio", "Nm2"]]
        answer = vertretungsplan_bot.sort_timetable(input)
        expected = [["12", "Mo", "3", "Bio", "Nm2"], ["12", "Mo", "4", "Bio", "Nm2"]]
        assert answer == expected, \
            f"Sorting returned wrong values: answer({answer}) is not expected result ({expected})"

    def test_checktimetable(self):
        vertretungsplan_bot.uc_add_lesson(user_id=0, text="/addlesson 05A")
        assert "5A" in str(vertretungsplan_bot.uc_check_timetable(user_id=0)["0"])
        vertretungsplan_bot.uc_clear_data(user_id=0)

    def test_get_command_description(self):
        answer = vertretungsplan_bot.get_command_description("help", "long")
        data = json.loads(open(vertretungsplan_bot.path_to_sensible_data + "command_description.json").read())
        expected = data["help"]["long"]
        assert answer == expected, f"help_text returned wrong value: {answer} != {expected}"

    def test_help_full(self):
        answer = vertretungsplan_bot.uc_help_text(user_id=0, text="/help help")["0"]["text"]
        expected = vertretungsplan_bot.get_command_description("help", "long")
        assert answer.endswith(expected), \
            f"help_text response does not end with expected value: {answer} does not end with {expected}"


if __name__ == "__main__":
    tester = Test()
    print("Running tests")
    print("\n".join(tester.run()))
