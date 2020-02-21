import vertretungsplan
import sqlite3
from dsbbot import DSBBot

from orgafunctions import update_user_profile, get_support


class Start:
    short = "Starthilfe"
    msg = "Registriere dich mit /register"

    def __call__(self,
                 update_text: str,
                 chat_id: int,
                 database_name: str):
        return {chat_id: {"text": self.msg}}


class Register:
    short = "Registriere dich mit diesem Befehl."
    success = "Deine Registrierung war erfolgreich."
    already_registered = "Du hast dich bereits bei diesem Bot registriert."

    def __call__(self,
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


class UpdateProfile:
    short = "Bearbeite dein Profil."
    success = "Dein Profil wurde erfolgreich bearbeitet."

    def __call__(self,
                 update_text,
                 chat_id,
                 database_name):
        kwargs = {a.split("=")[0]: a.split("=")[1] for a in update_text.split(" ")[1:]
                  if len(a.split("=")) == 2
                  and not (a.startswith("=") or a.endswith("="))
                  and not a.split("=")[0] == "support"}
        update_user_profile(chat_id,
                            database_name,
                            kwargs)
        return {chat_id: {"text": self.success}}


class DeleteProfile:
    short = "Löscht alle Daten, die über dich bekannt sind."
    success = "Deine Daten wurden erfolgreich gelöscht."
    detail = """Dieser Befehl löscht alle Daten, die dem Bot über dich bekannt sind.
Um sicher zu gehen, dass du deine Daten wirklich löschen willst, schreibe \"ja wirklich\" dahinter.
bspw.: /delete_profile ja wirklich"""

    def __call__(self,
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
            return {chat_id: {"text": self.detail}}


class AddLesson:
    short = "Füge Stunden zu einem Stundenplan hinzu."
    success = "Stunden wurden erfolgreich deinem Stundenplan hinzugefügt."
    detail = f"""{short}

Gib folgende Daten an:
Klasse (bspw.: '05A', '12')
Wochentag (bspw.: 'Mo')
Stunde (bspw.: '1', '1-2')
Fach (bspw.: 'Deu')
Raum (bspw.: '1.23')
[Optional:] Wochentyp (bspw.: 'A')

Du kannst auch mehrere Stunden auf einmal eintragen, indem du jede Stunde in eine neue Zeile schreibst.

/add_lesson 12 Mo 3 Bio Nm2 
12 Mo 4 Bio Nm2 
12 Mo 7-8 Ma 1.46 B 
12 Mo 7-8 Phy Nm1 A"""

    def __call__(self,
                 update_text: str,
                 chat_id: int,
                 database_name: str):
        db = sqlite3.connect(database_name)
        columns = ["id INTEGER PRIMARY KEY AUTOINCREMENT",
                   "class",
                   "day",
                   "lesson_index",
                   "lesson_name",
                   "room",
                   "week_type varchar(255) DEFAULT ''"]
        if not str.join(" ", update_text.split(" ")[1:]):
            return {chat_id: {"text": self.detail}}
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
                cmd = f"INSERT INTO lessons_{chat_id}({str.join(', ', used_columns)}) VALUES({str.join(', ', used_values)});"
                print(cmd)
                db.execute(cmd)
        db.commit()
        db.close()
        return {chat_id: {"text": str(len(str.join(" ", update_text.split(" ")[1:]).split("\n"))) + " " + self.success}}


class ViewLessons:
    short = "Sieh dir deinen Stundenplan an."
    header = "Hier ist dein Stundenplan:"

    def __call__(self,
                 update_text: str,
                 chat_id: int,
                 database_name: str):
        msg = self.header + "\n" * 2
        db = sqlite3.connect(database_name)
        lessons = [x for x in db.execute(f"SELECT * FROM lessons_{chat_id};")]
        msg = msg + str.join("\n", [str.join(" ", [str(y) for y in x if y is not None])
                                    for x in lessons])
        return {chat_id: {"text": msg}}


class UpdateLesson:
    short = "Experimental: Update a lesson from your timetable."
    success = "Your timetable has been updated."

    def __call__(self,
                 update_text: str,
                 chat_id: int,
                 database_name: str,
                 *args, **kwargs):
        db = sqlite3.connect(database_name)
        for line in str.join(" ", update_text.split(" ")[1:]).split("\n"):
            cmd = f"UPDATE lessons_{chat_id} SET {str.join(', ', line.split(' ')[1:])} WHERE id={line.split(' ')[0]};"
            db.execute(cmd)
        return {chat_id: {"text": self.success}}


class RemoveLesson:
    short = "Entfernt eine Stunde von deinem Stundenplan."
    detail = """Löscht Einträge von deinem Stundenplan für jede Zahl, die du dahinter schreibst.
Nutze /view_lessons um die ID der Stunden zu sehen.

bspw.: /remove_lesson 1 5 13"""
    success = """Die Stunden wurden erfolgreich von deinem Stundenplan gelöscht. 
Nutze /view_lessons um deinen Stundenplan zu überprüfen."""

    def __call__(self,
                 update_text: str,
                 chat_id: int,
                 database_name: str):
        if not str.join(" ", update_text.split(" ")[1:]):
            return {chat_id: {"text": self.detail}}
        db = sqlite3.connect(database_name)
        for lesson_id in update_text.split(" ")[1:]:
            db.execute(f"DELETE FROM lessons_{chat_id} WHERE id={lesson_id};")
        db.commit()
        db.close()
        return {chat_id: {"text": self.success}}


class Information:
    short = "Listet deinen Vertretungsplan auf."
    msg = "Für dich relevante Einträge:"
    no_relevants = "Für deinen Stundenplan liegen keine Einträge vor."

    def __call__(self,
                 update_text,
                 chat_id: int,
                 database_name):
        db = sqlite3.connect(database_name)
        output = {}
        db_user = [x for x in db.execute(f"SELECT dsb_user, dsb_pswd FROM users WHERE chat_id={chat_id};")][0]
        list_lessons = [[str(y) for y in x] for x in db.execute(f"SELECT * FROM lessons_{chat_id};")]
        print(list_lessons)
        if list_lessons:
            relevant_entries = vertretungsplan.getRelevants(list_lessons, db_user[0], db_user[1])
            print(f"Relevant: {relevant_entries}")
            text = str.join('\n', [str.join(" ", e) for e in relevant_entries])
            return {chat_id: {"text": self.msg + "\n\n" + (text or self.no_relevants)}}
        else:
            return {chat_id: {"text": self.no_timetable}}


class Test:
    short = "Führt alle Tests des Bots durch."

    def __call__(self,
                 update_text,
                 chat_id: int,
                 database_name):
        from tests import Test
        return {chat_id: {'text': "\n".join(Test().run())}}


class UserInfo:
    short = "Zeigt die Informationen zu deinem Profil an."
    msg = "Die Folgenden Informationen sind dem Bot über dich bekannt."

    def __call__(self,
                 update_text,
                 chat_id,
                 database_name):
        db = sqlite3.connect(database_name)
        data = db.execute(f"SELECT {str.join(', ', [DSBBot.columns])} FROM users WHERE id={chat_id};")
        text = str.join('\n', [str.join(': ', [DSBBot[column], value]) for column, value in enumerate(data)
                               if column != "support"])
        return {chat_id: {"text": self.msg + "\n" * 2 + text}}


class Support:
    short = "Versendet eine Nachricht an den Support."

    def __call__(self,
                 update_text: str,
                 chat_id: int,
                 database_name: str):
        if str.join(", ", update_text.split(" ")):
            return {get_support(chat_id, database_name): {"text": " ".join(update_text.split(" ")[1:])}}
