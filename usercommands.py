import vertretungsplan
import sqlite3
from dsbbot import DSBBot

from orgafunctions import update_user_profile, get_support


class UserCommand:
    # usage_string represents the string a user has to enter to access that command eg.: /help
    usage_string = "/"
    no_main_function = "Für diesen Befehl wurde noch keine Funktion hinterlegt."
    no_detail_desc = "Für diesen Befehl wurde noch keine detaillierte Beschreibung hinterlegt."

    def __init__(self, string: str):
        if not string.startswith("/"):
            string = "/" + string
        self.usage_string = string
        self.detail = self.detail.replace("{usage_string}", self.usage_string)

    def __repr__(self):
        return "user command \"" + self.usage_string + "\""

    def __call__(self,
                 update_text: str,
                 chat_id: int,
                 database_name: str,
                 *args, **kwargs):
        if str.join(" ", update_text.split(" ")[1:]) == "help":
            try:
                return {chat_id: {"text": self.detail}}
            except AttributeError:
                return {chat_id: {"text": self.no_detail_desc},
                        get_support(chat_id, database_name): {"text": self.usage_string + ": " + self.no_detail_desc}}
        else:
            try:
                return self.main(update_text=update_text,
                                 chat_id=chat_id,
                                 database_name=database_name)
            except AttributeError:
                return {chat_id: {"text": self.no_main_function},
                        get_support(chat_id, database_name): {"text": self.usage_string + ": " + self.no_main_function}}


class Start(UserCommand):
    short = "Starthilfe"
    detail = "{usage_string} beschreibt den Bot und gibt Vorschlage, welche Befehle du als nächstes nutzen könntest."
    msg = """Dieser Bot liest den Vertretungsplan deiner Schule aus und sucht dir deine relevanten Einträge heraus.
Registriere dich mit /register oder lass dir eine Liste der verfügbaren Befehle mit /help ausgeben."""

    def main(self,
             update_text: str,
             chat_id: int,
             database_name: str):
        return {chat_id: {"text": self.msg}}


class Register(UserCommand):
    short = "Registriere dich mit diesem Befehl."
    detail = "Mit {usage_string} kannst du dich für diesen Bot registrieren."
    success = "Deine Registrierung war erfolgreich."
    already_registered = "Du hast dich bereits bei diesem Bot registriert."

    def main(self,
             update_text: str,
             chat_id: int,
             database_name: str):
        db = sqlite3.connect(database_name)
        kwargs = {a.split("=")[0]: a.split("=")[1] for a in update_text.split(" ")[1:]
                  if len(a.split("=")) == 2
                  and not (a.startswith("=") or a.endswith("="))}
        kwargs["chat_id"] = chat_id
        columns = str.join(', ', [str(x) for x in kwargs])
        values = str.join(', ', [str(kwargs[x]) for x in kwargs])
        try:
            db.execute(f"INSERT INTO users({columns}) VALUES({values});")
        except sqlite3.IntegrityError:
            return {chat_id: {"text": self.already_registered}}
        db.commit()
        get_support(chat_id, database_name)
        db.close()
        return {chat_id: {"text": self.success}}


class UpdateProfile(UserCommand):
    short = "Bearbeite dein Profil."
    detail = """Mit {usage_string} kannst du dein Profil bearbeiten.
bspw.: {usage_string} dsb_user=213061 dsb_pswd=dsbgak"""
    success = "Dein Profil wurde erfolgreich bearbeitet."

    def main(self,
             update_text: str,
             chat_id: int,
             database_name: str):
        kwargs = {a.split("=")[0]: a.split("=")[1] for a in update_text.split(" ")[1:]
                  if len(a.split("=")) == 2
                  and not (a.startswith("=") or a.endswith("="))
                  and not a.split("=")[0] == "support"
                  and not a.split("=")[0] == "chat_id"}
        update_user_profile(chat_id,
                            database_name,
                            kwargs)
        return {chat_id: {"text": self.success}}


class DeleteProfile(UserCommand):
    short = "Löscht alle Daten, die über dich bekannt sind."
    success = "Deine Daten wurden erfolgreich gelöscht."
    detail = """{usage_string} löscht alle Daten, die dem Bot über dich bekannt sind.
Um sicher zu gehen, dass du deine Daten wirklich löschen willst, schreibe \"ja wirklich\" dahinter.
bspw.: {usage_string} ja wirklich"""

    def main(self,
             update_text: str,
             chat_id: int,
             database_name: str,
             *args, **kwargs):
        if str.join(" ", update_text.split(" ")[1:]) == "ja wirklich":
            db = sqlite3.connect(database_name)
            # Delete from users table
            db.execute(f"DELETE FROM users WHERE chat_id={chat_id};")
            # Delete individual timetable table
            db.execute(f"DROP TABLE lessons_{chat_id};")
            db.commit()
            db.close()
            return {chat_id: {"text": self.success}}
        else:
            return {chat_id: {"text": self.detail.replace("{usage_string}", self.usage_string)}}


class AddLesson(UserCommand):
    short = "Füge Stunden zu deinem Stundenplan hinzu."
    success = "Stunden wurden erfolgreich deinem Stundenplan hinzugefügt."
    detail = """{usage_string} fügt Stunden zu deinem Stundenplan hinzu.

Gib folgende Daten an:
Klasse (bspw.: '05A', '12')
Wochentag (bspw.: 'Mo')
Stunde (bspw.: '1', '1-2')
Fach (bspw.: 'Deu')
Raum (bspw.: '1.23')
[Optional:] Wochentyp (bspw.: 'A')

Du kannst auch mehrere Stunden auf einmal eintragen, indem du jede Stunde in eine neue Zeile schreibst.

{usage_string} 12 Mo 3 Bio Nm2 
12 Mo 4 Bio Nm2 
12 Mo 7-8 Ma 1.46 B 
12 Mo 7-8 Phy Nm1 A"""

    def main(self,
             update_text: str,
             chat_id: int,
             database_name: str):
        db = sqlite3.connect(database_name)
        columns = ["id INTEGER PRIMARY KEY AUTOINCREMENT",
                   "class",
                   "day",
                   "lesson",
                   "subject",
                   "room",
                   "week_type varchar(255) DEFAULT ''"]
        if not str.join(" ", update_text.split(" ")[1:]):
            return {chat_id: {"text": self.detail.replace("{usage_string}", self.usage_string)}}
        db.execute(f"CREATE TABLE IF NOT EXISTS lessons_{chat_id}({str.join(', ', columns)})")
        for line in str.join(" ", update_text.split(" ")[1:]).split("\n"):
            l_ind = 2
            for lx in line.split(" ")[l_ind].split("-"):
                used_columns = []
                used_values = []
                for i, x in enumerate(line.split(" ")):
                    if x:
                        used_columns.append(columns[i+1].split(" ")[0])
                        used_values.append(f"'{x.title() if i != l_ind else lx.title()}'")
                used_columns_string = str.join(', ', used_columns)
                used_values_string = str.join(', ', used_values)
                cmd = f"INSERT INTO lessons_{chat_id}({used_columns_string}) VALUES({used_values_string});"
                db.execute(cmd)
        db.commit()
        db.close()
        return {chat_id: {"text": str(len(str.join(" ", update_text.split(" ")[1:]).split("\n"))) + " " + self.success}}


class ViewLessons(UserCommand):
    short = "Sieh dir deinen Stundenplan an."
    detail = "{usage_string} gibt dir eine Liste der Stunden in deinem Stundenplan zurück."
    header = "Hier ist dein Stundenplan:"

    def main(self,
             update_text: str,
             chat_id: int,
             database_name: str):
        msg = self.header + "\n" * 2
        db = sqlite3.connect(database_name)
        lessons = [x for x in db.execute(f"SELECT * FROM lessons_{chat_id};")]
        msg = msg + str.join("\n", [str.join(" ", [str(y) for y in x if y is not None])
                                    for x in lessons])
        return {chat_id: {"text": msg}}


class UpdateLesson(UserCommand):
    short = "Experimental: Update a lesson from your timetable."
    detail = """{usage_string} allows you to update a lesson in your timetable.
eg.: {usage_string} 1 room='1.23' subject='Bio'"""
    success = "Your timetable has been updated."

    def main(self,
             update_text: str,
             chat_id: int,
             database_name: str,
             *args, **kwargs):
        db = sqlite3.connect(database_name)
        for line in str.join(" ", update_text.split(" ")[1:]).split("\n"):
            cmd = f"UPDATE lessons_{chat_id} SET {str.join(', ', line.split(' ')[1:])} WHERE id={line.split(' ')[0]};"
            db.execute(cmd)
        return {chat_id: {"text": self.success}}


class RemoveLesson(UserCommand):
    short = "Entfernt eine Stunde von deinem Stundenplan."
    detail = """{usage_string} löscht Einträge von deinem Stundenplan für jede Zahl, die du dahinter schreibst.
Nutze {usage_string} um die ID der Stunden zu sehen.

bspw.: /remove_lesson 1 5 13"""
    success = """Die Stunden wurden erfolgreich von deinem Stundenplan gelöscht. 
Nutze /view_lessons um deinen Stundenplan zu überprüfen."""

    def main(self,
             update_text: str,
             chat_id: int,
             database_name: str):
        if not str.join(" ", update_text.split(" ")[1:]):
            return {chat_id: {"text": self.detail.replace("{usage_string}", self.usage_string)}}
        db = sqlite3.connect(database_name)
        for lesson_id in update_text.split(" ")[1:]:
            db.execute(f"DELETE FROM lessons_{chat_id} WHERE id={lesson_id};")
        db.commit()
        db.close()
        return {chat_id: {"text": self.success}}


class Information(UserCommand):
    short = "Listet deinen Vertretungsplan auf."
    detail = "{usage_string} sucht dir die für dich relevanten Einträge aus deinem Vertretungsplan heraus."
    msg_relevant = "Für dich relevante Einträge:"
    msg_news_for_today = "Folgende Nachrichten liegen für heute vor:"
    no_relevants = "Für deinen Stundenplan liegen keine Einträge vor."
    no_news_for_today = "Es liegen heute keine Nachrichten zum Tag vor."
    no_timetable = "Du hast noch keinen Stundenplan eingerichtet."

    def main(self,
             update_text,
             chat_id: int,
             database_name):
        db = sqlite3.connect(database_name)
        db_user = [x for x in db.execute(f"SELECT dsb_user, dsb_pswd FROM users WHERE chat_id={chat_id};")][0]
        list_lessons = [[str(y) for y in x] for x in db.execute(f"SELECT * FROM lessons_{chat_id};")]
        if list_lessons:
            relevant_entries = vertretungsplan.getRelevants(list_lessons, db_user[0], db_user[1])
            print(relevant_entries)
            news_for_today = [str.join(": ", [d, t]) for d, t in vertretungsplan.getNews(db_user[0], db_user[1])]
            print(news_for_today)
            text_rel = str.join('\n', [str.join(" ", e) for e in relevant_entries]) or self.no_relevants
            text_mft = str.join('\n', news_for_today) or self.no_news_for_today
            return {chat_id: {"text": str.join("\n", [self.msg_relevant,
                                                      text_rel,
                                                      '',
                                                      self.msg_news_for_today,
                                                      text_mft])}}
        else:
            return {chat_id: {"text": self.no_timetable}}


class Test(UserCommand):
    short = "Führt alle Tests des Bots durch."
    detail = "{usage_string} führt alle Tests durch, die für diesen Bot geschrieben wurden."

    def main(self,
             update_text,
             chat_id: int,
             database_name):
        from tests import Test
        return {chat_id: {'text': "\n".join(Test().run())}}


class UserInfo(UserCommand):
    short = "Zeigt die Informationen zu deinem Profil an."
    detail = "{usage_string} zeigt alle Informationen an, die der Bot über dich gespeichert hat."
    msg = "Die Folgenden Informationen sind dem Bot über dich bekannt."

    def main(self,
             update_text,
             chat_id,
             database_name):
        db = sqlite3.connect(database_name)
        data = db.execute(f"SELECT {str.join(', ', [DSBBot.columns])} FROM users WHERE id={chat_id};")
        text = str.join('\n', [str.join(': ', [DSBBot[column], value]) for column, value in enumerate(data)
                               if column != "support"])
        return {chat_id: {"text": self.msg + "\n" * 2 + text}}


class Support(UserCommand):
    short = "Versendet eine Nachricht an den Support."
    detail = """{usage_string} versendet eine Nachricht an den Support.
Bisher ist keine Funktion implementiert, die es dem Support erlaubt, zu antworten. Drücke dich also präzise aus.

bspw.: {usage_string} Hallo Welt!"""

    def main(self,
             update_text: str,
             chat_id: int,
             database_name: str):
        if str.join(", ", update_text.split(" ")):
            return {get_support(chat_id, database_name): {"text": " ".join(update_text.split(" ")[1:])}}