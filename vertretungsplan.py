from typing import List, Any

import requests, logging, base64, gzip, json
from bs4 import BeautifulSoup as bs
import time, datetime
import json
import dsbapi

logger = logging.getLogger()

wday = {'Mo':0,
        'Di':1,
        'Mi':2,
        'Do':3,
        'Fr':4,
        'Sa':5,
        'So':6}
wtype = {'A':0,
        'a':0,
        'B':1,
        'b':1}

def update(username, password, save = True):
    doc = getDoc(username, password)
    einträge = []
    for a in doc.find_all('center'):
        try:
            datum = a.find_all('div')[0].text.split(" ")[0]
            for b in a.find_all('tr'):
                if b.text != "":
                    eintrag = [c.text.replace(" - ", ", ").replace("-","").replace("\xa0","").replace("(","").replace(")","") for c in b.find_all('td')]
                    eintrag.append(datum)
                    if len(eintrag) == 10:
                        einträge.append(eintrag)
        except IndexError:
            pass
    if save:
        with open(f"{username}_buffer.json", "w") as file:
            file.write(json.dumps(einträge))
            file.close()
    return(einträge)

def getDoc(username, password):
    url = getURL(username, password)
    if url == '':
        raise(ValueError("No URL given."))
    return(bs(requests.get(url).text, "html.parser"))

def getURL(username, password):
    try:
        print("Trying login via Desktop API...")
        LOGIN_URL = "https://www.dsbmobile.de/Login.aspx"
        DATA_URL = "https://www.dsbmobile.de/jhw-ecd92528-a4b9-425f-89ee-c7038c72b9a6.ashx/GetData"

        session = requests.Session()

        r = session.get(LOGIN_URL)

        page = bs(r.text, "html.parser")
        data = {
            "txtUser": username,
            "txtPass": password,
            "ctl03": "Anmelden",
        }
        fields = ["__LASTFOCUS", "__VIEWSTATE", "__VIEWSTATEGENERATOR",
            "__EVENTTARGET", "__EVENTARGUMENT", "__EVENTVALIDATION"]
        for field in fields:
            element = page.find(id=field)
            if not element is None: data[field] = element.get("value")
        
        session.post(LOGIN_URL, data)
        
        params = {
            "UserId": "",
            "UserPw": "",
            "Abos": [],
            "AppVersion": "2.3",
            "Language": "de",
            "OsVersion": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/78.0.3904.70 Safari/537.36",
            "AppId": "",
            "Device": "WebApp",
            "PushId": "",
            "BundleId": "de.heinekingmedia.inhouse.dsbmobile.web",
            "Date": "2019-11-06T16:03:11.322Z",
            "LastUpdate": "2019-11-06T16:03:11.322Z"
        }
        # Convert params into the right format
        params_bytestring = json.dumps(params, separators=(',', ':')).encode("UTF-8")
        params_compressed = base64.b64encode(gzip.compress(params_bytestring)).decode("UTF-8")
        json_data = {"req": {"Data": params_compressed, "DataType": 1}}

        headers = {"Referer": "www.dsbmobile.de"}
        r = session.post(DATA_URL, json=json_data, headers=headers)

        data_compressed = json.loads(r.content)["d"]
        data = json.loads(gzip.decompress(base64.b64decode(data_compressed)))

        table_url = data["ResultMenuItems"][0]["Childs"][2]["Root"]["Childs"][0]["Childs"][0]["Detail"]
        print(table_url)
        return(table_url)
    except Exception as e_desktop:
        logger.exception("Login/GetData via Desktop API failed, trying Android API...")
        try:
            myDSB = dsbapi.DSBApi(username, password)
            return(myDSB.fetch_entries())
        except Exception as e_android:
            print("Android login failed too")
            raise e_android

def getNews(username, password):
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
    return(information)

def getRelevants(kursliste, username, password, level = 0):
    #doc = bs(doc, 'html.parser')
    einträge = update(username, password)
    relevante_einträge = []
    eintrag: []
    for eintrag in einträge:
        for kurs in kursliste:
            try:
                if len(kurs) == 1:
                    if eintrag[0] == kurs[0]:
                        relevante_einträge.append(eintrag)
                else:
                    match = [False for a in range(6)]
                    if kurs[0] in eintrag[0]: # class
                        match[0] = True
                    #else:
                    #    continue
                    if wday[kurs[1].capitalize()] == time.gmtime(datetime.datetime.strptime(eintrag[9], '%d.%m.%Y').timestamp()-time.altzone).tm_wday: # week day
                        match[1] = True
                    if kurs[2] in eintrag[1]: # lesson
                        match[2] = True
                    if kurs[3] == eintrag[3]: # subject
                        match[3] = True
                    if kurs[4] == eintrag[5]: # room
                        match[4] = True
                    if len(kurs) == 6 and int((time.gmtime(datetime.datetime.strptime(eintrag[9], '%d.%m.%Y').timestamp()-time.altzone).tm_yday / 7) % len(wtype)) == wtype[kurs[-1]]:# week type
                        match[5] = True
                    if len([a for a in match if a == True]) >= level:
                        #print(str(eintrag) + " für Kurs " + str(kurs) + " hat " + str(len([a for a in match if a == True])) + " Übereinstimmungen.")
                        if not eintrag in relevante_einträge:
                            relevante_einträge.append(eintrag)
            except KeyError:
                pass
    #for a in relevante_einträge:
        #print(a[9] + ": " + a[1] + ", " + a[2] + " --> " + a[7])
    return(relevante_einträge)

if __name__ == "__main__":
    try:
        # get the password
        doc = bs(requests.get("http://www.gak-buchholz.de/unterricht/vertretungsplan/").text, "html.parser")
        username = [a.text.split(" ")[-1] for a in doc.find_all('strong') if "Benutzername: " in a.text][0]
        password = [a.text.split(" ")[-1] for a in doc.find_all('strong') if "Passwort: " in a.text][0]
        #print(f"Login-Daten für Gymnasium am Kattenberge:\n\tBenutzername: {username}\n\tPasswort: {password}")
        print("Der Autor dieser Software übernimmt keine Garantie für ihr richtiges Verhalten. Es bestehen keine Ansprüche auf Behebung eventueller Fehler oder sonstige Dienstleistungen. Der Autor übernimmt keine Haftung für den Inhalt der dargestellten Informationen.")
        print()
        for a in getNews(username, password):
            print(a[0] + ": " + a[1])
        print()
        try:
            kursliste = eval(open("kursliste.txt").read())
            for eintrag in getRelevants(kursliste, username, password, 5):
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
                print(str([a for a in wday if wday[a] == time.gmtime(datetime.datetime.strptime(eintrag[9], '%d.%m.%Y').timestamp()-time.altzone).tm_wday][0].capitalize()) + " " + eintrag[9] + " " + eintrag[1] + ": " + eintrag[0] + " " + eintrag[3] + " " + eintrag[5] + " --> "
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
