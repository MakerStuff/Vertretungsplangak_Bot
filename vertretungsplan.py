import datetime
import json
import time

import base64
import gzip
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


def vertretungsplan(username, password, save=True, location="../Vertretungsplangak_Data/"):
    doc = getDoc(username, password)
    einträge = []
    print(f"Checking {len(doc.find_all('center'))} times center")
    for center in doc.find_all('center'):
        try:
            print("Checking center")
            header = ["" for i in range(10)]
            now = time.gmtime(time.time())
            datum = f"{now.tm_mday}.{now.tm_mon}.{now.tm_year}"
            try:
                datum = center.find_all('div')[0].text.split(" ")[0]
            except IndexError:
                pass
            print(datum)
            '''
            try:
                
                header_line = center.find_all('p')[0].find_all('table')[0].find_all('tr')[0]
                header = []
                for th in header_line.find_all('th'):
                    header.append(th.text.title())
                header.append(datum)
                print(f"\tHeader: {header}")
                assert len(header) == len(header_line.find_all('th')) + 1
            except AttributeError as e:
                print(e)
            '''

            table = center.find_all('table')[-1]
            print("\tFound table")
            print(f"\tChecking {len(table.find_all('tr')[1:])} times tr")
            for tr in center.find_all('table')[-1].find_all('tr'):
                if len(tr.find_all('th')) == 0 and len(tr.find_all('td')) == len(header)-1:
                    if tr.text != "":
                        eintrag = [c.text.strip(" *-*(\xa0)*(*)*").title() for c in tr.find_all('td')]
                        eintrag.append(datum)
                        for stunde in eintrag[1].replace(" ", "").split("-"):
                            eintrag[1] = stunde
                            print(f"Eintrag: {eintrag}")
                            assert len(eintrag) == len(header)
                            einträge.append(eintrag.copy())
                    else:
                        print("Table is empty")
        except IndexError as e:
            print(e)
            pass
        except AttributeError as e:
            print(e)
            pass
    if save:
        with open(location + f"{username}_buffer.json", "w") as file:
            file.write(json.dumps(einträge))
            file.close()
    return einträge

def getDoc(username, password):
    url = getURL(username, password)
    print(f"This is the url to be checked: {url}")
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
def getURL(username, password, tries=5, location="../Vertretungsplangak_Data/"):
    for i in range(tries):
        try:
            index = dsbapi.fetch_index(logger)
            
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
    general_information = json.load(open(location + "general_information.json"))
    if "emergency_url" in general_information:
        return general_information["emergency_url"]
    else:
        raise Exception(f"No login method worked properly after {tries} tries")


def getNews(username, password, doc=None):
    if not doc:
        doc = getDoc(username, password)
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


def getRelevants(kursliste: list,
                 username: str = None,
                 password: str = None,
                 vertretungs_plan: list = [],
                 level: int = 0) -> list:
    assert kursliste, "Keine Kursliste verfügbar"
    assert (username and password) or vertretungs_plan, "Neither login credentials nor vertretungsplan available."
    if not vertretungs_plan:
        eintraege = vertretungsplan(username, password)
    else:
        eintraege = vertretungs_plan
    relevante_eintraege = []
    eintrag: []
    print(f"Einträge({len(eintraege)}): {eintraege}")
    for eintrag in eintraege:
        for kurs in kursliste:
            for a in kurs:
                a = a.title()
            try:
                if len(kurs) == 1:
                    if eintrag[0].lstrip("0").title() == kurs[0].lstrip("0").title():
                        relevante_eintraege.append(eintrag)
                else:
                    match = [False for a in range(6)]
                    if kurs[0].lstrip("0").title() in eintrag[0].lstrip("0").title():  # class
                        match[0] = True
                    # else:
                    #    continue
                    if wday[kurs[1]] == time.gmtime(datetime.datetime.strptime(eintrag[9], '%d.%m.%Y').timestamp() - time.altzone).tm_wday:  # week day
                        match[1] = True
                    if kurs[2] in eintrag[1]:  # lesson
                        match[2] = True
                    if kurs[3] == eintrag[3]:  # subject
                        match[3] = True
                    if kurs[4] == eintrag[5]:  # room
                        match[4] = True
                    if len(kurs) == 6 and int((time.gmtime(datetime.datetime.strptime(eintrag[9],
                                                                                      '%d.%m.%Y').timestamp() - time.altzone).tm_yday / 7) % len(
                            wtype)) == wtype[kurs[-1]]:  # week type
                        match[5] = True
                    if len([a for a in match if a == True]) >= level:
                        # print(str(eintrag) + " für Kurs " + str(kurs) + " hat " + str(len([a for a in match if a == True])) + " Übereinstimmungen.")
                        if not eintrag in relevante_eintraege:
                            relevante_eintraege.append(eintrag)
            except KeyError:
                pass
    # for a in relevante_einträge:
    # print(a[9] + ": " + a[1] + ", " + a[2] + " --> " + a[7])
    return relevante_eintraege


if __name__ == "__main__":
    try:
        # get the password
        doc = bs(requests.get("http://www.gak-buchholz.de/unterricht/vertretungsplan/").text, "html.parser")
        username = [a.text.split(" ")[-1] for a in doc.find_all('strong') if "Benutzername: " in a.text][0]
        password = [a.text.split(" ")[-1] for a in doc.find_all('strong') if "Passwort: " in a.text][0]
        # print(f"Login-Daten für Gymnasium am Kattenberge:\n\tBenutzername: {username}\n\tPasswort: {password}")
        print(
            "Der Autor dieser Software übernimmt keine Garantie für ihr richtiges Verhalten. Es bestehen keine Ansprüche auf Behebung eventueller Fehler oder sonstige Dienstleistungen. Der Autor übernimmt keine Haftung für den Inhalt der dargestellten Informationen.")
        print()
        for a in getNews(username, password):
            print(a[0] + ": " + a[1])
        print()
        try:
            kursliste = json.loads(open("../Vertretungsplangak_Data/userdata/201176580.json").read())["Stundenplan"]
            for eintrag in getRelevants(kursliste, username, password, level=5):
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
        print("\nDie Informationen sollten auf " + getURL(username, password) + " überprüft werden!")
    except requests.exceptions.ConnectionError:
        print("Keine Verbindung möglich. Bitte überprüfe deine Internetverbindung.")
    input("Press Enter to continue...")
