# coding: utf-8

import datetime
import json
import time
from typing import *
import logging
import requests
from bs4 import BeautifulSoup as bs

import dsbapi

logger = logging.getLogger()

wday = {'Mo': 0,
        'Di': 1,
        'Mi': 2,
        'Do': 3,
        'Fr': 4,
        'Sa': 5,
        'So': 6}
wtype = {'A': 0,
         'a': 0,
         'B': 1,
         'b': 1}


class Vertretung:
    def __init__(self,
                 class_name: str,
                 period: str,
                 subject: str,
                 orig_subject: str,
                 room: str,
                 orig_room: str,
                 repl_from: str,
                 repl_type: str,
                 desc: str,
                 week_day: str,
                 week_type: str):
        self.class_name = class_name
        self.period = period
        self.subject = subject
        self.orig_subject = orig_subject
        self.room = room
        self.orig_room = orig_room
        self.repl_from = repl_from
        self.repl_type = repl_type
        self.desc = desc
        self.week_day = week_day
        self.week_type = week_type

    def from_list(self, from_list: List):
        self.__init__(from_list[1],
                      from_list[2],
                      from_list[3],
                      from_list[4],
                      from_list[5],
                      from_list[6],
                      from_list[7],
                      from_list[8],
                      from_list[9],
                      from_list[10])
        return self

    def __repr__(self):
        description = ', '.join([x + "='" + self.__getattribute__(x) + "'"
                                 for x in self.__dir__()
                                 if not x.startswith("__")
                                 and self.__getattribute__(x)
                                 and "__call__" not in self.__getattribute__(x).__dir__()])
        return f"<{str(type(self)).strip('<>')}: {description}>"

    def __eq__(self, other):
        if type(other) == Vertretung:
            s_dict = {x: self.__dict__[x] for x in self.__dir__()}
            o_dict = {x: other.__dict__[x] for x in other.__dir__()}
            return s_dict == o_dict

    def __getitem__(self, item):
        if not item.startswith("__"):
            return self.__getattribute__(item)

    def __str__(self):
        class_name = ""\
                     + f"Klasse {self.class_name}" * bool(self.class_name)
        period = ""\
                 + f"{self.period}. Stunde" * bool(self.period)
        subject = ""\
                  + f"{self.subject}" \
                  + f" statt {self.orig_subject}" * bool(self.orig_subject)
        room = ""\
               + f"in {self.room or '<kein Raum>'}"\
               + f" statt {self.orig_room}" * bool(self.orig_room)
        week_day = f" am {self.week_day}" * bool(self.week_day)
        return " ".join([class_name,
                         period,
                         subject,
                         room,
                         week_day]).replace("  ", " ")


class Lesson(Vertretung):
    def __init__(self,
                 class_name: str,
                 subject: Optional[str] = None,
                 room: Optional[str] = None,
                 period: Optional[str] = None,
                 week_day: Optional[str] = None,
                 week_type: Optional[str] = None):
        self.class_name = class_name
        self.orig_subject = subject
        self.orig_room = room
        self.period = period
        self.week_day = week_day
        self.week_type = week_type

    def from_list(self, from_list: List):
        self.__init__(class_name=from_list[0],
                      subject=from_list[1],
                      room=from_list[2],
                      period=from_list[3],
                      week_day=from_list[4],
                      week_type=from_list[5])
        return self

    def __eq__(self, other):
        if type(other) == Vertretung:
            f = []
            for x in self.__dir__():
                if not x.startswith("__") and x != "from_list":
                    a = self.__getattribute__(x)
                    b = other.__getattribute__(x)
                    r = a == b
                    f.append(r)
            # print(f"\n{self} {'=' if not False in f else '!'}=\n{other}")
            return False not in f


class Vertretungsplanliste:
    vertretungen: List[Vertretung]

    def __init__(self, vertretungen: List[Vertretung]):
        self.vertretungen = vertretungen

    def __iter__(self):
        for a in self.vertretungen:
            yield a

    def __contains__(self, item):
        return item in self.vertretungen

    def __getitem__(self, item):
        return self.vertretungen[item]

    def __repr__(self):
        description = ', '.join([v.__repr__() for v in self.vertretungen]) or str(None)
        return f"<{type(self)}: [{description}]>"


def vertretungsplan(username: Optional[str] = None,
                    password: Optional[str] = None,
                    doc: Optional[str] = None,
                    save=True,
                    location="../Vertretungsplangak_Data/"):
    if not doc:
        doc = get_doc(username, password)
    entries = []
    body = doc.find_all('body')[1]
    for center in [c for c in body.find_all('center') if len(c.find_all('table')) >= 1]:
        weekday = center.find_all('div')[0].text.split(" ")[1].rstrip(",")
        weektype = center.find_all('div')[0].text.split(", Woche ")[-1].split(" ")[0]
        table = center.find_all('table')[-1]
        if table:
            for tr in table.find_all('tr')[1:]:
                entry = []
                for td in tr.find_all('td'):
                    entry.append(td.text.replace("\xa0", "").replace("---", ""))
                for period in entry[1].split(" - "):
                    for each_class in entry[0].split(", "):
                        repl = Vertretung(class_name=each_class,
                                          period=period,
                                          subject=entry[2],
                                          orig_subject=entry[3],
                                          room=entry[4],
                                          orig_room=entry[5],
                                          repl_from=entry[6],
                                          repl_type=entry[7],
                                          desc=entry[8],
                                          week_day=weekday,
                                          week_type=weektype)
                        entries.append(repl)
    return Vertretungsplanliste(entries)


def get_doc(username: str = None,
            password: str = None,
            url: str = None):
    if not url:
        url = get_url(username, password)
    assert url, "No URL given."
    doc = bs(requests.get(url).text, "html.parser")
    try:
        assert "Untis" in doc.text, "\"Untis\" not in doc.text"
        assert "Stand: " in doc.text, "\"Stand: \" not in doc.text"
    except AssertionError as e:
        print(f"Content is not correct: {doc.text} <- End of content.")
        raise e
    return doc


# Parameter `tries` says how often to try requesting each API
def get_url(username, password, tries=5, data_location="../Vertretungsplangak_Data/"):
    for i in range(tries):
        try:
            index = dsbapi.fetch_index(logger,
                                       username=username,
                                       password=password)

            # Iterate through the three content tabs and find the plan-tab
            for tab in index["ResultMenuItems"][0]["Childs"]:
                if tab["Title"] == "Pl\u00e4ne":
                    table_url = tab["Root"]["Childs"][0]["Childs"][0]["Detail"]
                    return table_url

            raise Exception("Couldn't find relevant data in index")
        except Exception as e:
            logger.exception(e)
    # If we arrive at this point, the API's don't work.

    # Try the emergency-url as a last resort
    general_information = json.load(open(data_location + "general_information.json"))
    if "emergency_url" in general_information:
        return general_information["emergency_url"]
    else:
        raise Exception(f"No login method worked properly after {tries} tries")


def get_news(username: Optional[str] = None,
             password: Optional[str] = None,
             doc: Optional = None):
    if not doc:
        doc = get_doc(username, password)
    information = []
    for a in doc.find_all('td'):
        try:
            if "info" in a.attrs['class']:
                info = [a.parent.parent.parent.find_all()[0].text.split(" ")[0], a.text]
                if not info[1] in [b[1] for b in information]:
                    information.append(info)
        except KeyError:
            pass
    return information


def get_relevant(kursliste: list,
                 username: Optional[str] = None,
                 password: Optional[str] = None,
                 vertretungs_plan: Optional[Vertretungsplanliste] = None) -> list:
    assert kursliste, "Keine Kursliste verfügbar oder Kursliste leer"
    assert (username and password) or vertretungs_plan, "Neither login credentials nor vertretungsplan available."
    if not vertretungs_plan:
        vertretungs_plan = vertretungsplan(username, password)
    relevante_eintraege = []
    for kurs in kursliste:
        for repl in vertretungs_plan:
            if kurs == repl:
                relevante_eintraege.append(repl)
    return relevante_eintraege


def main():
    try:
        # get the password
        doc = bs(requests.get("http://www.gak-buchholz.de/unterricht/vertretungsplan/").text, "html.parser")
        username = [a.text.split(" ")[-1] for a in doc.find_all('strong') if "Benutzername: " in a.text][0]
        password = [a.text.split(" ")[-1] for a in doc.find_all('strong') if "Passwort: " in a.text][0]

        url = get_url(username=username,
                      password=password)
        doc = get_doc(url=url)
        print(
            "Der Autor dieser Software übernimmt keine Garantie für ihr richtiges Verhalten. Es bestehen keine Ansprüche auf Behebung eventueller Fehler oder sonstige Dienstleistungen. Der Autor übernimmt keine Haftung für den Inhalt der dargestellten Informationen.")
        for a in get_news(doc=doc):
            print(a[0] + ": " + a[1])
        try:
            kursliste = []
            vertretungen = vertretungsplan(doc=doc)
            for eintrag in get_relevant(kursliste=kursliste,
                                        vertretungs_plan=vertretungen):
                # 0: Klasse
                # 1: Stunde
                # 2: Fach
                # 3: eig. Fach
                # 4: Raum
                # 5: eig. Raum
                # 6: Vertr. von
                # 7: Art
                # 8: Text
                # 9: Datum
                # 10: Übereinstimmungslevel
                print(str([a for a in wday if wday[a] == time.gmtime(
                    datetime.datetime.strptime(eintrag[9], '%d.%m.%Y').timestamp() - time.altzone).tm_wday][
                              0].capitalize()) + " " + eintrag[9] + " " + eintrag[1] + ": " + eintrag[0] + " " +
                      eintrag[3] + " " + eintrag[5] + " --> "
                      + eintrag[7] + " " + eintrag[2]
                      + " in Raum " * bool(len(eintrag[4])) + eintrag[4]
                      + ". Beschreibung: " * bool(len(eintrag[8])) + eintrag[8]
                      + ". Vertretung von " * bool(len(eintrag[6])) + eintrag[6])
            print(f"{len(kursliste)} Kurse wurden überprüft.")
        except FileNotFoundError:
            print("Es liegt keine Kursliste vor.")
        print("\nDie Informationen sollten auf " + url + " überprüft werden!")
    except requests.exceptions.ConnectionError:
        print("Keine Verbindung möglich. Bitte überprüfe deine Internetverbindung.")
    input("Press Enter to continue...")


if __name__ == "__main__":
    main()
