﻿import csv
import datetime
import json
import logging
import os
import threading
import time
from functools import wraps

import requests
from bs4 import BeautifulSoup as bs
from telegram import ChatAction, ParseMode
from telegram.ext import Updater
from telegram.error import NetworkError

import vertretungsplan

path_to_sensible_data = "../Vertretungsplangak_Data/"
path_to_user_data = path_to_sensible_data + "userdata/"

updater = Updater(
    token=json.loads(open(path_to_sensible_data + "general_information.json", "r", encoding="utf-8").read())["token"],
    use_context=True)
command_to_function = {}

dispatcher = updater.dispatcher

# Enable logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    level=logging.INFO)

logger = logging.getLogger(__name__)

# indirect functions
def read_file(filename, path=path_to_sensible_data):
    print(f"Call to read {path + filename}")
    try:
        content = open(path + filename, "r", encoding="utf-8").read()
        if filename.endswith(".json"):
            return json.loads(content)
        if filename.endswith(".txt"):
            return str(content)
        else:
            return content
    except FileNotFoundError as e:
        if filename.endswith(".json"):
            return dict()
        elif filename.endswith(".txt"):
            return ""
        else:
            raise e


def write_file(filename, content, path=path_to_sensible_data):
    print(f"Call to write {content} to {path + filename}")
    assert filename, "No filename given"
    assert "." in filename, "Missing \".\" in filename"
    assert not filename.endswith("."), f"{filename} cannot end with \".\""
    if filename.endswith(".json"):
        assert type(content) == dict, "Content of .json file cannot be other than dict"
    if filename.endswith(".txt"):
        assert type(content) == str, "Content of .txt file cannot be other than string"
    if type(content) == dict:
        with open(path + filename, "w", encoding="utf-8") as file:
            file.write(json.dumps(content))
            file.close()
    elif type(content) == str:
        with open(path + filename, "w", encoding="utf-8") as file:
            file.write(content)
            file.close()
    return True


def get_command_description(command, detail="short"):
    print(f"Asking for {detail} description for {command} command")
    command_description = read_file("command_description.json")
    try:
        try:
            short = command_description[command]
            # CHECK for type (str/dict) and make dict {"short": "desc", "long": "desc"}
            # for compatibility with older versions
            if type(short) == str:
                command_description[command] = {"short": short, "long": ""}
                write_file("command_description.json", command_description)
        except KeyError:
            raise KeyError(f"Description for {command} does not exist.")
        try:
            return command_description[command][detail]
        except KeyError:
            raise KeyError(f"{detail} description for {command} does not exist.")
    except KeyError as e:
        try:
            return command_description["unspecific"]["missing_command_description"]
        except:
            return "There is no error message available yet"


def error(update, context):
    output = {}
    if isinstance(context.error, NetworkError):
        print("NetworkError -> restarting...")
        threading.Thread(target=stop, args=(updater,)).start()
        return
    print(context.error)
    try:
        """Log Errors caused by Updates."""
        logger.warning('Update "%s" caused error "%s"', update, context.error)
        context.bot.send_message(chat_id=update.message.chat_id,
                                 text="Es ist ein Fehler aufgetreten. Bitte versuche es erneut oder kontaktiere den Support mit /support.")
    except Exception as e:
        print(e)
    supporter = get_support()
    document = ""
    try:
        document = update.message.document.file_name
    except AttributeError:
        pass
    error_message = f"Error:\n{update.message.from_user['id']}:\" {update.message.text}\" " + document * bool(
        document) + f" caused:\n\"{context.error}\""
    print(error_message)
    context.bot.send_message(chat_id=supporter, text=error_message, disable_notification=True)
    return {}


def get_support(user_id=None):
    data = read_file("general_information.json")
    support_info = data["supporter"]
    least_clients = min([len(support_info[a]["clients"]) for a in support_info])
    supporter = ""
    client = user_id
    if str(client) in support_info:
        return client
    else:
        for sp in support_info:
            support_info[sp]["clients"] = [c for c in support_info[sp]["clients"] if not c in ("None", None)]
            if client in support_info[sp]["clients"]:
                supporter = sp
                break
        if not supporter:
            supporter = [a for a in support_info if len(support_info[a]["clients"]) <= least_clients][0]
            if user_id is not None:
                support_info[supporter]["clients"].append(user_id)
    data["supporter"] = support_info
    write_file("general_information.json", data)
    print(f"Support for {user_id} is {supporter}")
    return supporter


def is_support(chat_id):
    return chat_id == get_support(chat_id)


def sort_timetable(timetable):
    sortable_timetable = timetable
    for entry in sortable_timetable:
        try:
            entry[1] = [vertretungsplan.wday[a] for a in vertretungsplan.wday if str(a) == str(entry[1])][0]
        except IndexError:
            pass
    # print("Prepared timetable for sorting.")
    # print(sortable_timetable)
    sorted_timetable = sorted(sortable_timetable)
    # print("Sorted timetable.")
    for entry in sorted_timetable:
        try:
            entry[1] = [a for a in vertretungsplan.wday if vertretungsplan.wday[a] == entry[1]][0]
        except IndexError:
            pass
    # print("Corrected timetable back to a more readable format.")
    # print(sorted_timetable)
    return sorted_timetable


def stop(process):
    process.stop()
    process.is_idle = False


# decorators
def send_typing_action(func):
    """Sends typing action while processing func command."""

    @wraps(func)
    def command_func(update, context, *args, **kwargs):
        context.bot.send_chat_action(chat_id=update.effective_message.chat_id, action=ChatAction.TYPING)
        return func(update, context, *args, **kwargs)

    return command_func


def detailed_help(func):
    """Calls the help text for a function"""

    @wraps(func)
    def command_func(update, context, *args, **kwargs):
        output = {}
        parameters = []
        try:
            if update.message.text:
                parameters = update.message.text.split(" ")[1:]
        except Exception as e:
            print(e)
        if parameters == ["help"]:
            command = update.message.text.split(" ")[0].replace("/", "")
            command_description = get_command_description(command, detail="long")
            if not get_command_description(command, detail="short").startswith("support_only") or is_support(
                    update.message.chat_id):
                message = "Nähere Beschreibung zu /" + command + ":\n" + str(command_description)
                output[str(update.message.chat_id)] = {"text": message}
            return output
        return {**func(update, context, *args, **kwargs), **output}

    return command_func


def support_only(func):
    """Restrict access to certain functions."""

    @wraps(func)
    def command_func(update, context, *args, **kwargs):
        info = read_file("general_information.json")
        if str(update.message.chat_id) in info["supporter"]:
            print(f"Granted access to {func} for {update.message.from_user}")
            return func(update, context, *args, **kwargs)
        else:
            print(f"Denied access to {func} for {update.message.from_user}")

    return command_func


# user commands
@detailed_help
@send_typing_action
def start(update, context):
    output = {str(update.message.chat_id): {"text": get_command_description("start", "long")}}
    return output


@detailed_help
@send_typing_action
def text(update, context):
    output = {}
    if update.message.chat.type == "private":
        output[str(update.message.chat_id)] = {"text": "Ich kann \"" + update.message.text + "\" nicht verstehen. Nutze /help, um eine Übersicht über die Befehle anzeigen zu lassen."}


@detailed_help
@send_typing_action
def add_lesson(update, context):
    output = {}
    user_id = update.message.from_user['id']
    parameters = update.message.text.split(" ")[1:]
    message = ""
    if "help" in parameters:
        output[str(update.message.chat_id)] = {"text": "Ein Eintrag für eine Stunde muss in einer der folgenden Formen angegeben werden:\n\nGib deine Klasse so an, wie sie auf dem Vertretungsplan angezeigt wird. Beispielsweise:\n05A\n10B\n\n ODER liste folgende Informationen durch ein Leerzeichen getrennt auf:\n - Klasse\n - Wochentag des Kurses (mo, di, mi, do, ...)\n - Stunde (Nur eine Stunde pro Eintrag)\n - Fach (Abgekürzt wie auf dem offiziellen Vertretungsplan)\n - Raum\n - (falls angegeben) Wochentyp (A oder B)\nBeispielsweise:\n/addlesson 05A mo 1 Deu 1.11\n/addlesson 12 mo 3-4 Deu 2.34"}
        return output
    parameters = [parameter.capitalize() for parameter in update.message.text.split(" ")[1:]]
    if not parameters:
        output[str(update.message.chat_id)] = {"text": "Nutze \"/addlesson help\" um zu lernen, wie du eine Stunde zu deinem Stundenplan hinzufügst."}
        return output
    elif len(parameters) in (1, 5, 6,):
        if len(parameters) == 1:
            try:
                user_info = json.loads(open(path_to_user_data + str(user_id) + ".json").read())
            except (FileNotFoundError, SyntaxError):
                user_info = {'Benutzername': 'Default',
                             'Passwort': 'Default',
                             'Stundenplan': []}
            lesson = parameters
            user_info["Stundenplan"].append(lesson)
            user_info['Stundenplan'] = sort_timetable(user_info['Stundenplan'])
            with open(path_to_user_data + str(user_id) + ".json", "w") as file:
                file.write(json.dumps(user_info))
                file.close()
        if len(parameters) != 1:
            stunden = [int(stunde) for stunde in parameters[2].split("-")]
            for stunde in range(min(stunden), max(stunden) + 1):
                try:
                    user_info = json.loads(open(path_to_user_data + str(user_id) + ".json").read())
                except (FileNotFoundError, SyntaxError):
                    user_info = {'Benutzername': 'Default',
                                 'Passwort': 'Default',
                                 'Stundenplan': []}
                print(user_info['Stundenplan'])
                lesson = parameters
                lesson[2] = str(stunde)
                print("This is the new lesson: " + str(lesson))
                print(lesson in user_info['Stundenplan'])
                user_info['Stundenplan'].append(lesson)
                user_info['Stundenplan'] = sort_timetable(user_info['Stundenplan'])
                print(user_info['Stundenplan'])
                with open(path_to_user_data + str(user_id) + ".json", "w") as file:
                    file.write(json.dumps(user_info))
                    file.close()
                message = message + str(lesson) + " wurde erfolgreich deinem Stundenplan hinzugefügt.\n"
        # print("Sorting timetable")
        # print(user_info['Stundenplan'])
        # print("Sorted timetable")
        # print(user_info['Stundenplan'])
        message = message + "\nBitte nutze /checktimetable um deinen aktualisierten Stundenplan zu überprüfen."
        output[str(update.message.chat_id)] = {"text": message}
    else:
        output[str(update.message.chat_id)] = {"text": "Unbekanntes Format. Nutze \"/addlesson help\" zur Hilfe."}


@detailed_help
@send_typing_action
def remove_lesson(update, context):
    output = {}
    user_id = update.message.from_user['id']
    parameters = update.message.text.split(" ")[1:]
    if not parameters:
        output[str(update.message.chat_id)] = {"text": "Bitte gib die Nummer deines Eintrags an. Du kannst mit /checktimetable sehen, welcher Stunde welche Nummer zugeordnet wurde."}
        return output
    user_info = json.loads(open(path_to_user_data + str(user_id) + ".json").read())
    del user_info['Stundenplan'][int(parameters[0]) - 1]
    with open(path_to_user_data + str(user_id) + ".json", "w") as file:
        file.write(json.dumps(user_info))
        file.close()
    output[str(update.message.chat_id)] = {"text": "Dein Stundenplan wurde bearbeitet. Nutze /checktimetable um ihn zu überprüfen."}


@detailed_help
@send_typing_action
def check_timetable(update, context):
    output = {}
    user_id = update.message.from_user['id']
    parameters = update.message.text.split(" ")[1:]
    try:
        user_info = json.loads(open(path_to_user_data + str(user_id) + ".json", encoding="utf-8").read())
        if "sort" in parameters:
            print("Sorting")
            user_info['Stundenplan'] = sort_timetable(user_info['Stundenplan'])
            print("Sorted")
            for a in range(len(user_info["Stundenplan"])):
                for b in range(len(user_info["Stundenplan"][a])):
                    print(f"updating {user_info['Stundenplan'][a][b]}")
                    print(f"to be {user_info['Stundenplan'][a][b].title()}")
                    user_info['Stundenplan'][a][b] = user_info['Stundenplan'][a][b].title()
            print("Writing to file")
            write_file(str(user_id) + ".json", user_info, path_to_user_data)
        if "csv" in parameters:
            if "help" in parameters:
                output[str(update.message.chat_id)] =  {"text":"Nutze folgende Beschreibung, um deinen Stundenplan in Excel anzusehen:\nÖffne Excel\nKlicke auf \"Daten/Externe Daten abrufen/Aus Text\" und wähle die Datei aus, die dir der Bot nach /checktimetable csv zugesendet hat.\nWähle \"Getrennt\" aus und drücke auf \"Weiter\"\nSetzt einen Haken bei \"Komma\" un drücke auf \"Weiter\"\nDrücke auf \"Fertig stellen\"\nDrücke auf \"OK\"\nBearbeite deine Daten wie es dir beliebt."}
            with open(str(user_id) + ".csv", "w", encoding='utf-8') as timetable:
                timetable_writer = csv.writer(timetable, delimiter=',', quotechar='"', quoting=csv.QUOTE_MINIMAL)

                weekdays = vertretungsplan.wday
                # timetable_writer.writerow(weekdays)

                for lesson in range(max([int(subject[2]) for subject in user_info['Stundenplan']])):
                    timetable_writer.writerow([" / ".join(
                        [" ".join([subject[a] for a in range(len(subject)) if not a in [1, 2, ]]) for subject in
                         user_info['Stundenplan'] if subject[1] == wday and int(subject[2]) == lesson + 1]) for wday in
                        weekdays])
            csv_doc = open(str(user_id) + ".csv", "rb")
            print("Read doc")
            output[str(update.message.chat_id)] = {"document": csv_doc}
            csv_doc.close()
            os.remove(str(user_id) + ".csv")
        else:
            timetable_txt = ""
            index = 1  # beginne bei 1 mit dem Zählen
            for note in user_info['Stundenplan']:
                timetable_txt = timetable_txt + str(index) + ". "
                for entry in note:
                    timetable_txt = timetable_txt + str(entry) + "\t"
                timetable_txt = timetable_txt + "\n"
                index += 1
            output[str(update.message.chat_id)] = {"text": "Hier ist dein " + "sortierter " * (
                    "sort" in update.message.text.split(" ")[1:]) + "Stundenplan:\n" + timetable_txt}
    except FileNotFoundError:
        output[str(update.message.chat_id)] = {"text": "Ich kann keine Daten zu deinem Stundenplan finden. Nutze \"addlesson help\" um zu lernen, wie du deinen Stundenplan erstellen kannst."}
    return output


@detailed_help
@send_typing_action
def create_timetable(update, context):
    # Dieser Befehl erlaubt es dem Nutzer, den eigenen Stundenplan mit einer CSV-Datei zu ersetzen
    user_id = update.message.from_user["id"]
    parameters = update.message.text.split(" ")[1:]
    if update.message.document:
        doc = update.message.document
        print(doc)


@detailed_help
@send_typing_action
def help_text(update, context):
    output = {}
    if not update.message.text.split(" ")[1:]:
        message = get_command_description("help", "long") + "\n"
        for command in command_to_function:
            try:
                command = command
                desc = get_command_description(command, "short")
                if desc == get_command_description("unspecific", "missing_command_description"):
                    notification = f"Short description for {command} equals missing_command_description."
                    context.bot.send_message(chat_id=get_support(), text=notification)
                if not desc.startswith("support_only") or is_support(update.message.chat_id):
                    message = message + "\n/" + command + " - " + desc
            except KeyError:
                support_list = read_file("general_information.json")["supporter"]
                if str(update.message.chat_id) == support_list:
                    message = message + "\n/" + command
                print("Missing description for \"" + command + "\"")
    else:
        topic = "Hier sind Details zu den gefragten Befehlen:\n"
        message = topic
        for command in update.message.text.split(" ")[1:]:
            if command in [cmd for cmd in command_to_function]:
                if (not get_command_description(command=command, detail="short").startswith("support_only")
                        or is_support(update.message.chat_id)):
                    message = message + "\n/" + command + " " + get_command_description(command, "long")
        if message == topic:
            message = message + "Der gefragte Befehl ist nicht verfügbar."
    output[str(update.message.chat_id)] = {"text": message}
    return output


@detailed_help
@send_typing_action
def information(update, context):
    output = {}
    user_id = update.message.from_user['id']
    parameters = update.message.text.split(" ")[1:]
    reply = ""
    default_iterations = 3
    max_iterations = 7
    if not parameters:
        parameters = [default_iterations]
    try:
        parameters[0] = int(parameters[0])
    except (ValueError, IndexError):
        parameters[0] = default_iterations

    if parameters[0] > max_iterations:
        parameters[0] = max_iterations

    for a in range(int(parameters[0])):
        try:
            user_info = json.loads(open(path_to_user_data + str(user_id) + ".json", encoding="utf-8").read())
            user_info = json.loads(open("../Vertretungsplangak_Data/userdata/201176580.json").read())
        except FileNotFoundError:
            output[str(update.message.chat_id)] = {"text": "Ich habe keine Informationen über dich gespeichert. Bitte trage deinen Stundenplan mit /addlesson ein, damit ich dir helfen kann."}
            return output

        # Correct username and password
        username = user_info['Benutzername']
        password = user_info['Passwort']
        if username == "Default" == password:
            doc = bs(requests.get("http://www.gak-buchholz.de/unterricht/vertretungsplan/").text, "html.parser")
            username = [a.text.split(" ")[-1] for a in doc.find_all('strong') if "Benutzername: " in a.text][0]
            password = [a.text.split(" ")[-1] for a in doc.find_all('strong') if "Passwort: " in a.text][0]

        # restart for lessons
        message = ""
        kursliste = user_info['Stundenplan']
        for eintrag in vertretungsplan.getRelevants(kursliste, username, password, level=5):
            message = message + "\n" * (2 if eintrag[9] not in message else 1)
            message = message + str([a for a in vertretungsplan.wday if vertretungsplan.wday[a] == time.gmtime(
                datetime.datetime.strptime(eintrag[9], '%d.%m.%Y').timestamp() - time.altzone).tm_wday][
                                        0].capitalize()) + " " + eintrag[9] + " " + eintrag[1] + ": " + eintrag[
                          0] + " " + eintrag[3] + " " + eintrag[5] + " --> " + eintrag[7] + " " + eintrag[
                          2] + " in Raum " * bool(len(eintrag[4])) + eintrag[4] + ". Beschreibung: " * bool(
                len(eintrag[8])) + eintrag[8] + ". Vertretung von " * bool(len(eintrag[6])) + eintrag[6]
        if message != "":
            reply = reply + "Für dich relevante Einträge:" + message + "\n\n"
        else:
            reply = reply + "Aktuell liegen keine Einträge für dich vor." + "\n\n"

        # restart for news
        message = ""
        for b in vertretungsplan.getNews(username, password):
            message = message + "\n" + b[0] + ": " + b[1]
        if message != "":
            reply = reply + "Nachrichten zum Tag:" + message + "\n\n"

        # Last updated:
        message = ""
        try:
            doc = bs(requests.get(vertretungsplan.getURL(username, password)).text, "html.parser")
            last_update = [a.text for a in doc.find_all("p") if "Stand: " in a.text][0]
            message = message + "Stand: " + " ".join(last_update.split(" Stand: ")[-1].split(" ")[0:2])
            reply = reply + message + "\n"
        except Exception as e:
            print(e)
            pass
        reply_footer = "Bitte überprüfe die Einträge auf <a href=\"" + vertretungsplan.getURL(username, password) + "\">der offiziellen Darstellung des Vertretungsplans</a>."
        output[str(update.message.chat_id)] = {"text": (reply + reply_footer),
                                               "parse_mode": ParseMode.HTML}
        break
    return output


@detailed_help
@send_typing_action
def change_login(update, context):
    output = {}
    user_id = update.message.from_user['id']
    parameters = update.message.text.split(" ")[1:]
    if len(parameters) == 2:
        user_info = json.loads(open(path_to_user_data + str(user_id) + ".json", encoding="utf-8").read())
        user_info['Benutzername'] = parameters[0]
        user_info['Passwort'] = parameters[1]
        with open(path_to_user_data + str(user_id) + ".json", 'w') as file:
            file.write(str(user_info))
            file.close()
        output[str(update.message.chat_id)] = {"text": f"Dein Nutzerdaten wurden geändert zu\nBenutzername: {user_info['Benutzername']}\nPasswort: {user_info['Passwort']}"}
    else:
        output[str(update.message.chat_id)] = {"text": "Überprüfe bitte die Syntax deiner Angaben."}


@detailed_help
@send_typing_action
def user_data(update, context):
    output = {}
    user_id = update.message.from_user['id']
    try:
        file = path_to_user_data + str(user_id) + ".json"
        context.bot.send_document(chat_id=update.message.chat_id, document=open(file, 'rb'))
        output[str(update.message.chat_id)] = {"text": "Hier sind alle Daten, die dem System über dich bekannt sind."}
    except FileNotFoundError:
        output[str(update.message.chat_id)] = {"text": "Es liegen keine Daten zu deiner Nutzer-ID vor. Bitte nutze /addlesson um deinen Stundenplan einzurichten"}
    return output

@detailed_help
@send_typing_action
def clear_data(update, context):
    output = {}
    user_id = update.message.from_user['id']
    os.remove(path_to_user_data + str(user_id) + ".json")
    try:
        open(str(user_id) + ".json")
        print("Fehler beim Löschen der Daten eines Nutzers: Daten noch vorhanden:")
        output[str(update.message.chat_id)] = {"text": "Beim Löschen deiner Daten ist ein Fehler aufgetreten. Falls der Fehler weiterhin besteht, kontaktiere bitten den Host dieses Bots."}
    except FileNotFoundError:
        output[str(update.message.chat_id)] = {"text": "Deine Daten wurden erfolgreich gelöscht."}


@detailed_help
@send_typing_action
def relevant(update, context):
    output = {}
    # TODO Diese Funktion seigt die Unterrichtsstunden an, die heute und morgen für den Nutzer interessant sind.
    # Hierzu muss der gesamte Stundenplan hinterlegt sein.
    output[str(update.message.chat_id)] = {"text": "Diese Funktion befindet sich derzeit im Aufbau und steht nicht zur Verfügung."}


@detailed_help
@send_typing_action
def support(update, context):
    output = {}
    parameters = update.message.text.split(" ")[1:]
    if parameters and not update.message.from_user["is_bot"]:
        supporter = get_support(update.message.from_user['id'])
        meta = str(update.message.chat_id)
        problem = " ".join(parameters)
        context.bot.forward_message(chat_id=supporter, from_chat_id=update.message.chat_id,
                                    message_id=update.message.message_id,
                                    text=meta + " hat folgendes Problem mit dem Vertretungsplan_Bot:\n\n" + problem)
        output[str(update.message.chat_id)] = {"text": "Dein Anliegen wurde an deinen Supporter gesendet. Bitte nimm zur Kenntnis, dass dieses Projekt freiwillig betrieben wird und wir manchmal auch keine Zeit haben, um direkt zu antworten."}
    return output

@detailed_help
@send_typing_action
def status(update, context):
    output = {}
    # Make it possible for the support to change this message
    parameters = update.message.text.split(" ")[1:]
    if str(update.message.chat_id) in \
            read_file("general_information.json")["supporter"]:
        if parameters:
            info = read_file("general_information.json")
            info["status_message"] = " ".join(parameters)
            write_file("general_information.json", info)
    output[str(update.message.chat_id)] = {"text": str(json.loads(open(path_to_sensible_data + "general_information.json", encoding='utf-8').read())["status_message"])}
    return output
    # TODO Add broadcast with none, silent and normal option. Default is silent.


# Support only commands
@detailed_help
@support_only
@send_typing_action
def answer_support_question(update, context):
    reply_message = "Du hast eine Antwort vom Support erhalten:\n\n" + " ".join(update.message.text.split(" ")[1:])
    user = update.message.reply_to_message.forward_from
    supporter = update.message.chat_id
    if update.message.text.split(" ")[1:]:
        original_message = update.message.reply_to_message
        print(original_message)
        context.bot.send_message(chat_id=user["id"], text=reply_message)
        success_message = "Die Antwort wurde erfolgreich an " + str(user) + " gesendet."
        context.bot.send_message(chat_id=supporter, text=success_message)
    else:
        context.bot.send_message(chat_id=supporter,
                                 text="Die Nachricht muss Text enthalten.\n/answer_sq <Antwort-Text>")


@detailed_help
@support_only
@send_typing_action
def send_emergency_url(update, context):
    parameters = update.message.text.split(" ")[1:]
    info = read_file("general_information.json")
    if update.message.chat_id in info["supporter"]:
        info["emergency_url"] = parameters[0]
    with open(path_to_sensible_data + "general_information.json") as file:
        file.write(json.dumps(info))
        file.close()


@detailed_help
@support_only
@send_typing_action
def set_command_description(update, context):
    output = {}
    command_description = read_file("command_description.json")
    parameters = update.message.text.split(" ")[1:]
    command = parameters[0]
    detail = parameters[1]
    description = " ".join(parameters[2:])
    try:
        command_description[command][detail] = description
    except KeyError as e:
        command_description[command] = {detail: description}
    write_file("command_description.json", command_description)
    output[str(update.message.chat_id)] = {"text": f"{detail} description of {command} has been changed to {description}"}
    return output


@detailed_help
@support_only
@send_typing_action
def stop_bot(update, context):
    output = {}
    output[str(update.message.chat_id)] = {"text": "Stopping bot", "disable_notification": True}
    threading.Thread(target=stop, args=(updater,)).start()
    return output


@detailed_help
@support_only
@send_typing_action
def test(update, context):
    output = {str(update.message.chat_id): {"document": open("README.md", 'rb')}}
    return output


@detailed_help
def handle_document(update, context):
    file = update.message.document
    file_id = file.file_id
    try:
        assert file.file_name.endswith(".json"), "File format is not .json"
        assert is_support(update.message.chat_id), "Chat is not support"
        assert update.message.caption == "store", "No store command"
        content = json.loads(requests.get(context.bot.get_file(file_id).to_dict()["file_path"]).text)
        write_file(file.file_name, content)
        context.bot.send_message(chat_id=update.message.chat_id, text=f"Stored {file.file_name}")
    except AssertionError as e:
        raise e
        pass


@support_only
@send_typing_action
def get_file(update, context):
    parameters = update.message.text.split(" ")[1:]
    assert not parameters[0].startswith(".."), "Path must not begin with .."
    file = path_to_sensible_data + parameters[0]
    try:
        return {str(update.message.chat_id): {"document": open(file, 'rb')}}
    except FileNotFoundError:
        return {str(update.message.chat_id): {"text": "Die Datei wurde nicht gefunden."}}


command_to_function = {"auskunft": information,
                       "help": help_text,
                       "start": start,
                       "status": status,
                       "addlesson": add_lesson,
                       "rmlesson": remove_lesson,
                       "checktimetable": check_timetable,
                       "changelogin": change_login,
                       "userdata": user_data,
                       "cleardata": clear_data,
                       "support": support,
                       "test": test,
                       "answer_sq": answer_support_question,
                       "send_emergency_url": send_emergency_url,
                       "stop_bot": stop_bot,
                       "set_command_description": set_command_description,
                       "get_file": get_file}


def command(update, context):
    assert update.message.text.startswith("/"), "Message is not a command!"
    user_command = update.message.text.split(" ")[0].split("@")[0].lstrip("/")
    print(f"command is {user_command}")
    if not user_command:
        pass
    else:
        print("Getting results")
        results = command_to_function[user_command](update, context)
        print(f"results: {results}")
        for chat_id in results:
            relevant_keys = {"text",
                             "document",
                             "disable_notification",
                             "parse_mode"}
            for key in relevant_keys:
                try:
                    results[chat_id][key]
                except KeyError:
                    results[chat_id][key] = None
            if results[chat_id]["document"] is not None:
                print(f"Document is {results[chat_id]['document']}")
                print("Sending document")
                context.bot.send_document(chat_id=int(chat_id),
                                          document=results[chat_id]["document"],
                                          caption=results[chat_id]["text"],
                                          disable_notification=results[chat_id]["disable_notification"])
                print("Sent document")
            else:
                context.bot.send_message(chat_id=int(chat_id),
                                         text=results[chat_id]["text"],
                                         parse_mode=results[chat_id]["parse_mode"],
                                         disable_notification=results[chat_id]["disable_notification"])


print("Hello World!")
print("Running as " + str(__name__))
if __name__ == "__main__":
    from telegram.ext import CommandHandler, MessageHandler, Filters

    dispatcher.add_handler(MessageHandler(Filters.command, command))
    dispatcher.add_handler(MessageHandler(Filters.text, text))
    dispatcher.add_handler(MessageHandler(Filters.document, handle_document))

    dispatcher.add_error_handler(error)

    updater.start_polling()
    print("Program is running...")
    updater.idle()
    print("Program has stopped.")
