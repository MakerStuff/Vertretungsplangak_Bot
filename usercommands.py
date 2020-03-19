# coding: uft-8

import vertretungsplan
import sqlite3
from dsbbot import DSBBot, UserCommand

from orgafunctions import update_user_profile, get_support


class Start(UserCommand):
    short = "Starthilfe"
    detail = "{usage_string} beschreibt den Bot und gibt Vorschlage, welche Befehle du als naechstes nutzen koenntest."
    msg = """Dieser Bot liest den Vertretungsplan deiner Schule aus und sucht dir deine relevanten Eintraege heraus.
Registriere dich mit /register oder lass dir eine Liste der verfuegbaren Befehle mit /help ausgeben."""

    def main(self,
             update_text: str,
             chat_id: int,
             database_name: str):
        return {chat_id: {"text": self.msg}}


class Register(UserCommand):
    short = "Registriere dich mit diesem Befehl."
    detail = "Mit {usage_string} kannst du dich fuer diesen Bot registrieren."
    success = "Deine Registrierung war erfolgreich."
    already_registered = "Du hast dich bereits bei diesem Bot registriert."

    def main(self,
             update_text: str,
             chat_id: int,
             database_name: str):
        db = sqlite3.connect(database_name)
        # Prepare database if it does not exist
        # db.execute(f"CREATE TABLE IF NOT EXISTS users({', '.join([x.split()[0] for x in DSBBot.columns])})")
        # Store user data
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

        # Create lessons table
        columns = DSBBot.columns_timetable
        columns_str = str.join(', ', columns)
        cmd = f"CREATE TABLE IF NOT EXISTS lessons_{chat_id}({columns_str});".replace("-", "u")
        db.execute(cmd)
        db.commit()

        # Set a supporter
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
    short = "Loescht alle Daten, die ueber dich bekannt sind."
    success = "Deine Daten wurden erfolgreich geloescht."
    detail = """{usage_string} loescht alle Daten, die dem Bot ueber dich bekannt sind.
Um sicher zu gehen, dass du deine Daten wirklich loeschen willst, schreibe \"ja wirklich\" dahinter.
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
            db.execute(f"DROP TABLE lessons_{chat_id};".replace("-", "u"))
            db.commit()
            db.close()
            return {chat_id: {"text": self.success}}
        else:
            return {chat_id: {"text": self.detail.replace("{usage_string}", self.usage_string)}}


class AddLesson(UserCommand):
    short = "Fuege Stunden zu deinem Stundenplan hinzu."
    success = "Stunden wurden erfolgreich deinem Stundenplan hinzugefuegt."
    detail = """{usage_string} fuegt Stunden zu deinem Stundenplan hinzu.

Gib folgende Daten an:
Klasse (bspw.: '05A', '12')
Wochentag (bspw.: 'Montag')
Stunde (bspw.: '1', '1-2')
Fach (bspw.: 'Deu')
Raum (bspw.: '1.23')
[Optional:] Wochentyp (bspw.: 'A', 'B')

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
        parameters = update_text.split(" ")[1:]
        if not parameters:
            return self.help(update_text=update_text,
                             chat_id=chat_id,
                             database_name=database_name)
        columns = DSBBot.columns_timetable
        for line in str.join(" ", update_text.split(" ")[1:]).split("\n"):
            used_values = line.split(" ")
            while len(used_values) < len(columns) - 1:
                used_values.append("")
            used_column = [x.split()[0] for x in columns[:-1]]
            while len(used_column) < len(columns) - 1:
                used_column.append("")
            for lesson in used_values[2].split("-"):
                used_values[2] = lesson
                used_values_str = ", ".join(["'" + str(x) + "'" for x in used_values])
                used_column_str = ", ".join(["'" + str(x) + "'" for x in used_column])
                cmd = f"INSERT INTO lessons_{chat_id}({used_column_str}) VALUES({used_values_str});".replace("-", "u")
                db.execute(cmd)
        db.commit()
        db.close()
        return {chat_id: {"text": str(len(str.join(" ", update_text.split(" ")[1:]).split("\n"))) + " " + self.success}}


class ViewLessons(UserCommand):
    short = "Sieh dir deinen Stundenplan an."
    detail = "{usage_string} gibt dir eine Liste der Stunden in deinem Stundenplan zurueck."
    header = "Hier ist dein Stundenplan:"

    def main(self,
             update_text: str,
             chat_id: int,
             database_name: str):
        msg = self.header + "\n" * 2
        db = sqlite3.connect(database_name)
        lessons = [x for x in db.execute(f"SELECT * FROM lessons_{chat_id};".replace("-", "u"))]
        msg = msg + str.join("\n", [str.join(" ", [str(y) for y in x if y is not None])
                                    for x in lessons])
        db.close()
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
            cmd = cmd.replace("-", "u")
            db.execute(cmd)
        return {chat_id: {"text": self.success}}


class RemoveLesson(UserCommand):
    short = "Entfernt eine Stunde von deinem Stundenplan."
    detail = """{usage_string} loescht Eintraege von deinem Stundenplan fuer jede Zahl, die du dahinter schreibst.
Nutze {usage_string} um die ID der Stunden zu sehen.

bspw.: /remove_lesson 1 5 13"""
    success = """Die Stunden wurden erfolgreich von deinem Stundenplan geloescht. 
Nutze /view_lessons um deinen Stundenplan zu ueberpruefen."""

    def main(self,
             update_text: str,
             chat_id: int,
             database_name: str):
        if not str.join(" ", update_text.split(" ")[1:]):
            return {chat_id: {"text": self.detail.replace("{usage_string}", self.usage_string)}}
        db = sqlite3.connect(database_name)
        for lesson_id in update_text.split(" ")[1:]:
            db.execute(f"DELETE FROM lessons_{chat_id} WHERE id={lesson_id};".replace("-", "u"))
        db.commit()
        db.close()
        return {chat_id: {"text": self.success}}


class Information(UserCommand):
    short = "Listet deinen Vertretungsplan auf."
    detail = "{usage_string} sucht dir die fuer dich relevanten Eintraege aus deinem Vertretungsplan heraus."
    msg_relevant = "Fuer dich relevante Eintraege:"
    msg_news_for_today = "Folgende Nachrichten liegen fuer heute vor:"
    no_relevants = "Fuer deinen Stundenplan liegen keine Eintraege vor."
    no_news_for_today = "Es liegen heute keine Nachrichten zum Tag vor."
    no_timetable = "Du hast noch keinen Stundenplan eingerichtet."

    def main(self,
             update_text,
             chat_id: int,
             database_name):
        output = {chat_id: {"text": ""}}
        db = sqlite3.connect(database_name)
        db_user = [x for x in db.execute(f"SELECT dsb_user, dsb_pswd FROM users WHERE chat_id={chat_id};")][0]
        columns = [x.split()[0] for x in DSBBot.columns_timetable[:-1]]
        list_lessons = [vertretungsplan.Lesson('').from_list([str(y) for y in x])
                        for x in db.execute(f"SELECT {', '.join(columns)} FROM lessons_{chat_id};".replace("-", "u"))]
        week_day_abbreviations = {"Mo": "Montag",
                                  "Di": "Dienstag",
                                  "Mi": "Mittwoch",
                                  "Do": "Donnerstag",
                                  "Fr": "Freitag"}
        for abbr in week_day_abbreviations:
            for lesson in list_lessons:
                lesson.week_day = lesson.week_day.replace(abbr, week_day_abbreviations[abbr])
        username = db_user[0]
        password = db_user[1]
        url = vertretungsplan.get_url(username=username,
                                      password=password)
        doc = vertretungsplan.get_doc(url=url)
        if list_lessons:
            vertretungen = vertretungsplan.vertretungsplan(doc=doc)
            relevant_entries = vertretungsplan.get_relevant(kursliste=list_lessons,
                                                            vertretungs_plan=vertretungen)
            text_rel = str.join('\n', [str.join(" ", e) for e in relevant_entries]) or self.no_relevants
            output[chat_id]["text"] = output[chat_id]["text"] + "\n" + text_rel
        else:
            output[chat_id]["text"] = output[chat_id]["text"] + "\n" + self.no_timetable
        news_for_today = [str.join(": ", [d, t]) for d, t in vertretungsplan.get_news(doc=doc)]
        text_mft = str.join('\n', news_for_today) or self.no_news_for_today
        output[chat_id]["text"] = output[chat_id]["text"] + "\n" + str.join("\n", [self.msg_news_for_today,
                                                                                   text_mft])
        db.execute(f"UPDATE users SET last_notification='{output[chat_id]['text']}'".replace("-", "u"))
        db.commit()
        db.close()
        return output


class Test(UserCommand):
    short = "Fuehrt alle Tests des Bots durch."
    detail = "{usage_string} fuehrt alle Tests durch, die fuer diesen Bot geschrieben wurden."

    def main(self,
             update_text,
             chat_id: int,
             database_name):
        from tests import Test
        return {chat_id: {'text': "\n".join(Test().run())}}


class UserInfo(UserCommand):
    short = "Zeigt die Informationen zu deinem Profil an."
    detail = "{usage_string} zeigt alle Informationen an, die der Bot ueber dich gespeichert hat."
    msg = "Die Folgenden Informationen sind dem Bot ueber dich bekannt."

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
Bisher ist keine Funktion implementiert, die es dem Support erlaubt, zu antworten. Druecke dich also praezise aus.

bspw.: {usage_string} Hallo Welt!"""
    success = "Dein Anliegen wurde an den Support versendet."

    def main(self,
             update_text: str,
             chat_id: int,
             database_name: str):
        if str.join(", ", update_text.split(" ")):
            return {chat_id: {"text": self.success},
                    get_support(chat_id, database_name): {"text": "Support: " + " ".join(update_text.split(" ")[1:])}}
