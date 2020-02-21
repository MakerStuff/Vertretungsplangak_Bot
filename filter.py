import re
from typing import *


__author__ = "Fabian Becker <fab.becker@outlook.de>"


class Filter:
    def __init__(self, **kwargs):
        # any argument matching the pattern is accepted
        for attribute in kwargs:
            if not (re.match(r'\w+__\w+__$', attribute) or attribute == "operator"):
                raise ValueError(f"{attribute} does not match expected attribute format.")
        self.__dict__.update(kwargs)
        if "operator" not in self.__dir__():
            self.operator = "AND"

    def __eq__(self, other):
        # -> tested
        # check for all non hidden attributes of this class
        # if they are present in another object
        # and match the corresponding attributes of another object
        attributes = [attr for attr in self.__dir__() if not (attr.startswith("__") or attr == "operator")]
        checks = []
        try:
            for attr in attributes:
                attribute = "__".join(attr.split("__")[0:-2])
                magic_method = "__" + attr.split("__")[-2] + "__"
                value = self.__getattribute__(attr)
                other_value = other.__getattribute__(attribute)
                checks.append(value.__getattribute__(magic_method)(other_value))
        except AttributeError:
            # when attribute is not present in other object, abort
            return False
        # return true if
        # all attributes of this filter are present in the other object
        # and the values match the magic method
        return False not in checks

    def __str__(self, logical_condition: Optional[str] = None):
        # -> tested
        # Returns a string to be used for sql style databases
        attributes = [a for a in self.__dir__() if not (a.startswith("__") or a == "operator")]
        for attr in range(len(attributes)):
            a = attributes[attr] + str(self.__getattribute__(attributes[attr]))
            a = a.replace("__eq__", "=")
            a = a.replace("__ne__", "!=")
            a = a.replace("__lt__", "<")
            a = a.replace("__gt__", ">")
            a = a.replace("__lte__", "<=")
            a = a.replace("__gte__",  ">=")
            a = a.replace("__contains__", " BETWEEN ")
            attributes[attr] = a
        return str.join(f" {(logical_condition or self.operator).upper()} ", attributes)

    def __bool__(self):
        return bool(len([a for a in self.__dir__() if not (a.startswith("__") or a == "operator")]))


if __name__ == "__main__":
    import tests
    tests.run_tests()
