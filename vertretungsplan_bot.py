import csv
import datetime
import json
import logging
import os
import threading
import time
from functools import wraps

import tests

import requests
from bs4 import BeautifulSoup as bs
from telegram import ChatAction, ParseMode, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Updater
from telegram.error import NetworkError

import vertretungsplan

path_to_sensible_data = "../Vertretungsplangak_Data/"
path_to_user_data = path_to_sensible_data + "userdata/"

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
        return write_file(filename, path=path, content=None)


def write_file(filename, content, path=path_to_sensible_data):
    print(f"Call to write {content} to {path + filename}")
    assert filename, "No filename given"
    assert "." in filename, "Missing \".\" in filename"
    assert not filename.endswith("."), f"{filename} cannot end with \".\""
    file_ending = filename.split(".")[-1]
    conv = {"json": (dict, json.dumps(content)),
            "txt": (str, str(content))}
    if content is None:
        content = conv[file_ending][0]()
    assert type(content) == conv[file_ending][0], \
        f"Content of .{file_ending} file must be {conv[file_ending][0]} instead of {type(content)}"
    with open(path + filename, "w", encoding="utf-8") as file:
        file.write(conv[file_ending][1])
        file.close()
    return content


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


def error(update=None, context=None, user_id=None):
    output = {}
    try:
        if isinstance(context.error, NetworkError):
            print("NetworkError -> restarting...")
            threading.Thread(target=stop, args=(updater,)).start()
            return
        print(context.error)
        try:
            """Log Errors caused by Updates."""
            logger.warning('Update "%s" caused error "%s"', update, context.error)
            output[str(update.message.chat_id)] = {"text": "Es ist ein Fehler aufgetreten. Bitte versuche es erneut oder kontaktiere den Support mit /support."}
        except Exception as e:
            print(e)
        supporter = get_support()
        document = ""
        try:
            document = update.message.document.file_name
        except AttributeError:
            pass
    except Exception as e:
        pass
    finally:
        if not "no-error-message" in update.message.text:
            error_message = f"Error:\n{update.message.chat_id}:\" {update.message.text}\" " + document * bool(
                document) + f" caused:\n\"{context.error}\""
            print(error_message)
            context.bot.send_message(chat_id=supporter, text=error_message, disable_notification=True)
        return output


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


def is_support(user_id):
    return user_id == get_support(user_id)


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
    def command_func(update=None, context=None, *args, **kwargs):
        if update is not None:
            context.bot.send_chat_action(chat_id=update.effective_message.chat_id, action=ChatAction.TYPING)
        return func(update, context, *args, **kwargs)

    return command_func


def detailed_help(func):
    """Calls the help text for a function"""

    @wraps(func)
    def command_func(update=None, context=None, *args, **kwargs):
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
    def command_func(update=None, context=None, *args, **kwargs):
        try:
            user_id = update.message.chat_id
        except AttributeError:
            pass
        info = read_file("general_information.json")
        if str(user_id) in info["supporter"]:
            print(f"Granted access to {func} for {user_id}")
            return func(update, context, *args, **kwargs)
        else:
            raise PermissionError(f"Denied access to {func} for {user_id}")

    return command_func


# user commands
@detailed_help
@send_typing_action
def uc_start(update=None, context=None, user_id=None):
    try:
        user_id = update.message.chat_id
    except AttributeError:
        pass
    output = {str(user_id): {"text": get_command_description("start", "long")}}
    return output


@detailed_help
@send_typing_action
def uc_text(update=None, context=None, user_id=None):
    output = {}
    if update.message.chat.type == "private":
        output[str(update.message.chat_id)] = {
            "text": "Ich kann \"" + update.message.text + "\" nicht verstehen. Nutze /help, um eine Übersicht über die Befehle anzeigen zu lassen."}
    return output


@detailed_help
@send_typing_action
def uc_add_lesson(update=None, context=None, user_id=None, text=None):
    output = {}
    try:
        user_id = update.message.from_user['id']
    except AttributeError:
        pass
    try:
        user_id = update.message.chat_id
    except AttributeError:
        pass
    message = ""
    parameters = [parameter.title() for parameter in text.split(" ")[1:]]
    if "Help" in parameters:
        output[str(user_id)] = {
            "text": get_command_description("addlesson", "long")}
        return output
    if not parameters:
        output[str(user_id)] = {
            "text": get_command_description("addlesson", "short")}
        return output
    elif len(parameters) in (1, 5, 6,):
        if len(parameters) == 1:
            try:
                user_info = json.loads(open(path_to_user_data + str(user_id) + ".json").read())
            except FileNotFoundError:
                user_info = {'Benutzername': 'Default',
                             'Passwort': 'Default',
                             'Stundenplan': []}
            lesson = parameters
            user_info["Stundenplan"].append(lesson)
            user_info['Stundenplan'] = sort_timetable(user_info['Stundenplan'])
            write_file(path_to_user_data + str(user_id) + ".json", user_info)
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
                write_file(path_to_user_data + str(user_id) + ".json", user_info)
                message = message + str(lesson) + " wurde erfolgreich deinem Stundenplan hinzugefügt.\n"
        message = message + "\nBitte nutze /checktimetable um deinen aktualisierten Stundenplan zu überprüfen."
        output[str(user_id)] = {"text": message}
    else:
        output[str(user_id)] = {"text": "Unbekanntes Format. Nutze \"/addlesson help\" zur Hilfe."}
    return output


@detailed_help
@send_typing_action
def uc_remove_lesson(update=None, context=None, user_id=None, text=None):
    output = {}
    try:
        user_id = update.message.chat_id
    except AttributeError:
        pass
    try:
        text = update.message.text
    except AttributeError:
        pass
    parameters = text.split(" ")[1:]
    if not parameters:
        output[str(user_id)] = {
            "text": get_command_description("rmlesson", "long")}
        return output
    user_info = json.loads(open(path_to_user_data + str(user_id) + ".json").read())
    try:
        del user_info['Stundenplan'][int(parameters[0]) - 1]
        write_file(path_to_user_data + str(user_id) + ".json", user_info)
        output[str(user_id)] = {
            "text": "Dein Stundenplan wurde bearbeitet. Nutze /checktimetable um ihn zu überprüfen."}
    except IndexError:
        output[str(user_id)] = {"text": "Eintrag konnte nicht gelöscht werden."}
    return output


@detailed_help
@send_typing_action
def uc_check_timetable(update=None, context=None, user_id=None, text=None):
    output = {}
    try:
        user_id = update.message.chat_id
    except AttributeError:
        pass
    try:
        text = update.message.text
    except AttributeError:
        pass
    print("Getting parameters")
    parameters = text.split(" ")[1:]
    print("Got parameters")
    try:
        user_info = json.loads(open(path_to_user_data + str(user_id) + ".json", encoding="utf-8").read())
        if "sort" in parameters or "fix" in parameters or True:
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
                output[str(user_id)] = {
                    "text": get_command_description("checktimetable", "csv")}
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
            output[str(user_id)] = {"document": csv_doc}
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
            output[str(user_id)] = {"text": "Hier ist dein " + "sortierter " * (
                    "sort" in text.split(" ")[1:]) + "Stundenplan:\n" + timetable_txt}
    except FileNotFoundError:
        output[str(user_id)] = {
            "text": "Ich kann keine Daten zu deinem Stundenplan finden. Nutze \"addlesson help\" um zu lernen, wie du deinen Stundenplan erstellen kannst."}
    return output


@detailed_help
@send_typing_action
def uc_create_timetable(update=None, context=None, user_id=None, text=None):
    output = {}
    # Dieser Befehl erlaubt es dem Nutzer, den eigenen Stundenplan mit einer CSV-Datei zu ersetzen
    try:
        user_id = update.message.chat_id
    except AttributeError:
        pass
    try:
        text = update.message.text
    except AttributeError:
        pass
    parameters = text.split(" ")[1:]
    if update.message.document:
        doc = update.message.document
        print(doc)
    return output


@detailed_help
@send_typing_action
def uc_help_text(update=None, context=None, user_id=None, text=None):
    output = {}
    try:
        user_id = update.message.chat_id
    except AttributeError:
        pass
    try:
        text = update.message.text
    except AttributeError:
        pass
    if not text.split(" ")[1:]:
        message = get_command_description("help", "long") + "\n"
        for command in command_to_function:
            try:
                command = command
                desc = get_command_description(command, "short")
                if desc == get_command_description("unspecific", "missing_command_description"):
                    notification = f"Short description for {command} equals missing_command_description."
                    context.bot.send_message(chat_id=get_support(), text=notification)
                if not desc.startswith("support_only") or is_support(user_id):
                    message = message + "\n/" + command + " - " + desc
            except KeyError:
                support_list = read_file("general_information.json")["supporter"]
                if str(user_id) == support_list:
                    message = message + "\n/" + command
                print("Missing description for \"" + command + "\"")
    else:
        topic = "Hier sind Details zu den gefragten Befehlen:\n"
        message = topic
        for command in text.split(" ")[1:]:
            if command in [cmd for cmd in command_to_function]:
                if (not get_command_description(command=command, detail="short").startswith("support_only")
                        or is_support(user_id)):
                    message = message + "\n/" + command + " " + get_command_description(command, "long")
        if message == topic:
            message = message + "Der gefragte Befehl ist nicht verfügbar."
    output[str(user_id)] = {"text": message}
    return output


@detailed_help
@send_typing_action
def uc_information(update=None, context=None, user_id=None, text=None):
    output = {}
    try:
        user_id = update.message.chat_id
    except AttributeError:
        pass
    try:
        text = update.message.text
    except AttributeError:
        pass
    parameters = text.split(" ")[1:]
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
        except FileNotFoundError:
            output[str(user_id)] = {"text": "Ich habe keine Informationen über dich gespeichert. Bitte trage deinen Stundenplan mit /addlesson ein, damit ich dir helfen kann."}
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
        relevants = vertretungsplan.getRelevants(kursliste, username, password, level=5)
        user_info["Relevant"] = relevants
        write_file(path_to_user_data + str(user_id) + ".json", user_info)
        for eintrag in relevants:
            message = message + "\n" * (2 if eintrag[9] not in message else 1)
            message = message + str([a for a in vertretungsplan.wday if vertretungsplan.wday[a] == time.gmtime(
                datetime.datetime.strptime(eintrag[9], '%d.%m.%Y').timestamp() - time.altzone).tm_wday][
                                        0].capitalize()) + " " + eintrag[9] + " " + eintrag[1] + ": " + eintrag[
                          0] + " " + eintrag[3] + " " + eintrag[5] + " --> " + eintrag[7] + " " + eintrag[
                          2] + " in Raum " * bool(len(eintrag[4])) + eintrag[4] + ". Beschreibung: " * bool(
                len(eintrag[8])) + eintrag[8] + ". Vertretung von " * bool(len(eintrag[6])) + eintrag[6]
        if message != "":
            reply = reply + f"{len(relevants)} für dich relevante Einträge:" + message + "\n\n"
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
        reply_footer = "Bitte überprüfe die Einträge auf <a href=\"" + vertretungsplan.getURL(username,
                                                                                              password) + "\">der offiziellen Darstellung des Vertretungsplans</a>."
        try:
            user_info["Notification"].title()
        except KeyError:
            user_info["Notification"] = "Silent"
        output[str(user_id)] = {"text": (reply + reply_footer),
                                "parse_mode": ParseMode.HTML,
                                "disable_notification": user_info["Notification"] == "Silent"}
        break
    return output


@detailed_help
@send_typing_action
def uc_change_login(update=None, context=None, user_id=None, text=None):
    output = {}
    try:
        user_id = update.message.chat_id
    except AttributeError:
        pass
    try:
        text = update.message.text
    except AttributeError:
        pass
    parameters = text.split(" ")[1:]
    if len(parameters) == 2:
        user_info = json.loads(open(path_to_user_data + str(user_id) + ".json", encoding="utf-8").read())
        user_info['Benutzername'] = parameters[0]
        user_info['Passwort'] = parameters[1]
        write_file(str(user_id) + ".json", user_info, path_to_user_data)
        output[str(user_id)] = {
            "text": f"Dein Nutzerdaten wurden geändert zu\nBenutzername: {user_info['Benutzername']}\nPasswort: {user_info['Passwort']}"}
    else:
        output[str(user_id)] = {"text": "Überprüfe bitte die Syntax deiner Angaben."}
    return output


@detailed_help
@send_typing_action
def uc_user_data(update=None, context=None, user_id=None, text=None):
    output = {}
    try:
        user_id = update.message.chat_id
    except AttributeError:
        pass
    try:
        text = update.message.text
    except AttributeError:
        pass
    try:
        file = path_to_user_data + str(user_id) + ".json"
        context.bot.send_document(chat_id=user_id, document=open(file, 'rb'))
        output[str(user_id)] = {"text": "Hier sind alle Daten, die dem System über dich bekannt sind."}
    except FileNotFoundError:
        output[str(user_id)] = {
            "text": "Es liegen keine Daten zu deiner Nutzer-ID vor. Bitte nutze /addlesson um deinen Stundenplan einzurichten"}
    return output


@detailed_help
@send_typing_action
def uc_clear_data(update=None, context=None, user_id=None, text=None):
    output = {}
    try:
        user_id = update.message.chat_id
    except AttributeError:
        pass
    try:
        text = update.message.text
    except AttributeError:
        pass
    os.remove(path_to_user_data + str(user_id) + ".json")
    try:
        open(str(user_id) + ".json")
        print("Fehler beim Löschen der Daten eines Nutzers: Daten noch vorhanden:")
        output[str(user_id)] = {
            "text": "Beim Löschen deiner Daten ist ein Fehler aufgetreten. Falls der Fehler weiterhin besteht, kontaktiere bitten den Host dieses Bots."}
    except FileNotFoundError:
        output[str(user_id)] = {"text": "Deine Daten wurden erfolgreich gelöscht."}
    return output


@detailed_help
@send_typing_action
def uc_relevant(update=None, context=None, user_id=None, text=None):
    try:
        user_id = update.message.chat_id
    except AttributeError:
        pass
    try:
        text = update.message.text
    except AttributeError:
        pass
    output = {str(user_id): {
        "text": "Diese Funktion befindet sich derzeit im Aufbau und steht nicht zur Verfügung."}}
    # TODO Diese Funktion zeigt die Unterrichtsstunden an, die heute und morgen für den Nutzer interessant sind.
    # Hierzu muss der gesamte Stundenplan hinterlegt sein.
    return output


@detailed_help
@send_typing_action
def uc_support(update=None, context=None, user_id=None, text=None):
    output = {}
    try:
        user_id = update.message.chat_id
    except AttributeError:
        pass
    try:
        text = update.message.text
    except AttributeError:
        pass
    parameters = text.split(" ")[1:]
    user_is_bot = False
    try:
        user_is_bot = update.message.from_user["is_bot"]
    except AttributeError:
        pass
    message_id = None
    try:
        message_id = update.message.message_id
    except AttributeError:
        pass
    if parameters and not user_is_bot:
        supporter = get_support(user_id)
        meta = str(user_id)
        problem = " ".join(parameters)
        context.bot.forward_message(chat_id=supporter, from_chat_id=user_id,
                                    message_id=message_id,
                                    text=meta + " hat folgendes Problem mit dem Vertretungsplan_Bot:\n\n" + problem)
        output[str(user_id)] = {
            "text": "Dein Anliegen wurde an deinen Supporter gesendet. Bitte nimm zur Kenntnis, dass dieses Projekt freiwillig betrieben wird und wir manchmal auch keine Zeit haben, um direkt zu antworten."}
    return output


@detailed_help
@send_typing_action
def uc_status(update=None, context=None, user_id=None, text=None):
    output = {}
    try:
        user_id = update.message.chat_id
    except AttributeError:
        pass
    try:
        text = update.message.text
    except AttributeError:
        pass
    # Make it possible for the support to change this message
    parameters = text.split(" ")[1:]
    if str(user_id) in \
            read_file("general_information.json")["supporter"]:
        if parameters:
            info = read_file("general_information.json")
            info["status_message"] = " ".join(parameters)
            write_file("general_information.json", info)
    output[str(user_id)] = {"text": str(
        json.loads(open(path_to_sensible_data + "general_information.json", encoding='utf-8').read())[
            "status_message"])}
    return output
    # TODO Add broadcast with none, silent and normal option. Default is silent.


# Support only commands
@detailed_help
@support_only
@send_typing_action
def uc_answer_support_question(update=None, context=None, user_id=None, text=None):
    output = {}
    try:
        user_id = update.message.chat_id
    except AttributeError:
        pass
    reply_message = "Du hast eine Antwort vom Support erhalten:\n\n" + " ".join(text.split(" ")[1:])
    user = update.message.reply_to_message.forward_from
    supporter = update.message.chat_id
    if update.message.text.split(" ")[1:]:
        original_message = update.message.reply_to_message
        print(original_message)
        context.bot.send_message(chat_id=user["id"], text=reply_message)
        success_message = "Die Antwort wurde erfolgreich an " + str(user) + " gesendet."
        output[str(supporter)] = {"text": success_message}
    else:
        output[str(supporter)] = {"text": "Die Nachricht muss Text enthalten.\n/answer_sq <Antwort-Text>"}
    return output


@detailed_help
@support_only
@send_typing_action
def uc_send_emergency_url(update=None, context=None, user_id=None):
    output = {}
    try:
        user_id = update.message.chat_id
    except AttributeError:
        pass
    try:
        text = update.message.text
    except AttributeError:
        pass
    parameters = text.split(" ")[1:]
    info = read_file("general_information.json")
    if user_id in info["supporter"]:
        info["emergency_url"] = parameters[0]
    write_file(path_to_sensible_data + "general_information.json", info)
    return output


@detailed_help
@support_only
@send_typing_action
def uc_set_command_description(update=None, context=None, user_id=None, text=None):
    output = {}
    try:
        user_id = update.message.chat_id
    except AttributeError:
        pass
    try:
        text = update.message.text
    except:
        pass
    command_description = read_file("command_description.json")
    parameters = text.split(" ")[1:]
    command = parameters[0]
    detail = parameters[1]
    description = " ".join(parameters[2:])
    try:
        command_description[command][detail] = description
    except KeyError as e:
        command_description[command] = {detail: description}
    write_file("command_description.json", command_description)
    output[str(user_id)] = {
        "text": f"{detail} description of {command} has been changed to {description}"}
    return output


@detailed_help
@support_only
@send_typing_action
def uc_stop_bot(update=None, context=None, user_id=None, text=None):
    output = dict()
    try:
        user_id = update.message.chat_id
    except AttributeError:
        pass
    try:
        text = update.message.text
    except AttributeError:
        pass
    output[str(user_id)] = {"text": "Stopping bot", "disable_notification": True}
    threading.Thread(target=stop, args=(updater,)).start()
    return output


@detailed_help
@support_only
@send_typing_action
def uc_test(update=None, context=None, user_id=None, text=None):
    try:
        user_id = update.message.chat_id
    except AttributeError:
        pass
    try:
        text = update.message.text
    except AttributeError:
        pass
    assert update
    output = {str(user_id): {"text": "\n".join(tests.Test().run())}}
    return output


@detailed_help
def uc_handle_document(update=None, context=None, user_id=None):
    file = update.message.document
    file_id = file.file_id
    try:
        assert file.file_name.endswith(".json"), "File format is not .json"
        assert is_support(update.message.chat_id), "Chat is not support"
        assert update.message.caption == "store", "No store command"
        content = json.loads(requests.get(context.bot.uc_get_file(file_id).to_dict()["file_path"]).text)
        write_file(file.file_name, content)
        context.bot.send_message(chat_id=update.message.chat_id, text=f"Stored {file.file_name}")
    except AssertionError as e:
        raise e
        pass


@support_only
@send_typing_action
def uc_get_file(update=None, context=None, user_id=None):
    output = {}
    parameters = update.message.text.split(" ")[1:]
    assert not parameters[0].startswith(".."), "Path must not begin with .."
    file = path_to_sensible_data + parameters[0]
    try:
        output[str(update.message.chat_id)] = {"document": open(file, 'rb')}
    except FileNotFoundError:
        output[str(update.message.chat_id)] = {"text": "Die Datei wurde nicht gefunden."}
    return output


@send_typing_action
def uc_choose_notification_level(update=None, context=None, user_id=None):
    output = {}
    keyboard = [[InlineKeyboardButton("Keine", callback_data=f'Ringer-{update.message.from_user["id"]}-None')],
                [InlineKeyboardButton("Leise", callback_data=f'Ringer-{update.message.from_user["id"]}-Silent')],
                [InlineKeyboardButton("Laut", callback_data=f'Ringer-{update.message.from_user["id"]}-Loud')]]

    reply_markup = InlineKeyboardMarkup(keyboard)

    user_info = read_file(path_to_user_data + str(update.message.from_user["id"]) + ".json")

    update.message.reply_text("Bitte Lautstärke wählen (" + str(user_info["Notification"]) + "):",
                              reply_markup=reply_markup)
    return output


def uc_callback(update=None, context=None, user_id=None):
    assert update.callback_query, "No callback given"
    query = update.callback_query
    answer = query.data
    if answer.split("-")[0] == "Ringer":
        user_info = read_file(path_to_user_data + answer.split("-")[1] + ".json")
        user_info["Notification"] = answer.split("-")[2]
        write_file(path_to_user_data + answer.split("-")[1] + ".json", user_info)
        query.edit_message_text(text="Neuer Benachrichtigungston: {}".format(answer.split("-")[2]))
    else:
        update.message.reply_text("Antwort konnte nicht verarbeitet werden")


updater = Updater(
    token=read_file("general_information.json")["token"],
    use_context=True)
command_to_function = {}

dispatcher = updater.dispatcher

command_to_function = {"auskunft": uc_information,
                       "help": uc_help_text,
                       "start": uc_start,
                       "status": uc_status,
                       "addlesson": uc_add_lesson,
                       "rmlesson": uc_remove_lesson,
                       "checktimetable": uc_check_timetable,
                       "changelogin": uc_change_login,
                       "userdata": uc_user_data,
                       "cleardata": uc_clear_data,
                       "benachrichtigungston": uc_choose_notification_level,
                       "support": uc_support,
                       "test": uc_test,
                       "answer_sq": uc_answer_support_question,
                       "send_emergency_url": uc_send_emergency_url,
                       "stop_bot": uc_stop_bot,
                       "set_command_description": uc_set_command_description,
                       "get_file": uc_get_file}


def uc_command(update=None, context=None, user_command=None, user=None, send=True):
    assert update or (user_command and user)
    try:
        user_command = update.message.text.split(" ")[0].split("@")[0].lstrip("/")
    except AttributeError:
        assert user_command, "No command given"
    user_command = user_command.lstrip("/")
    print(f"command is {user_command}")
    results = {}
    if not user_command:
        pass
    else:
        print("Getting results")
        results = command_to_function[user_command](update, context, user_id=user).copy()
        print(f"results: {results}")
        for chat_id in results:
            relevant_keys = {"text",
                             "document",
                             "disable_notification",
                             "parse_mode",
                             "reply_markup"}
            for key in relevant_keys:
                try:
                    results[chat_id][key]
                except KeyError:
                    results[chat_id][key] = None
            if send:
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
        return results


def uc_dsb_changed(context):
    output = {}
    try:
        unterrichtszeiten = []
        doc = bs(requests.get("http://www.gak-buchholz.de/unterricht/unterrichtszeiten/").text, "html.parser")
        for table in doc.find_all('table'):
            if table.attrs == {'style': 'font-weight: 400; margin-left: auto; margin-right: auto;'}:
                td = [element for element in table.find_all("td") if element.attrs == {'width': '220'}]
                # assert len(td) % 2 == 0, "Uneven amount of timestamps"
                year = time.gmtime(time.time()).tm_year
                month = time.gmtime(time.time()).tm_mon
                day = time.gmtime(time.time()).tm_mday
                while len(td):
                    begin = datetime.datetime.strptime(f'{year}-{month}-{day} {td.pop(0).text.rstrip(" h")}',
                                                       '%Y-%m-%d %H.%M').timestamp()
                    end = datetime.datetime.strptime(f'{year}-{month}-{day} {td.pop(0).text.rstrip(" h")}',
                                                     '%Y-%m-%d %H.%M').timestamp()
                    unterrichtszeiten.append([begin, end].copy())
    except IndexError:
        pass
    for block in unterrichtszeiten:
        if block[0] < time.time() < block[1]:
            print(f"Unterricht findet zwischen {time.ctime(block[0])} und {time.ctime(block[1])} statt.")
            return
        else:
            print(f"Aktuell findet kein Unterricht zwischen {time.ctime(block[0])} und {time.ctime(block[1])} statt.")
            pass
    for user in [".".join(file.split(".")[:-1]) for file in os.listdir(path_to_user_data) if file.endswith(".json")]:
        print(user)
        assert type(user) == str, "user is not string"
        user_info = read_file(path_to_user_data + str(user) + ".json").copy()

        try:
            notification_level = user_info["Notification"]
        except KeyError:
            user_info["Notification"] = "Silent"
            write_file(path_to_user_data + str(user) + ".json", user_info)
            notification_level = user_info["Notification"]

        try:
            user_info["Relevant"].__dir__()
        except KeyError:
            user_info["Relevant"] = []
            write_file(path_to_user_data + str(user) + ".json", user_info)

        if notification_level != "None":
            # Correct username and password
            username = user_info['Benutzername']
            password = user_info['Passwort']
            if username == "Default" == password:
                doc = bs(requests.get("http://www.gak-buchholz.de/unterricht/vertretungsplan/").text, "html.parser")
                username = [a.text.split(" ")[-1] for a in doc.find_all('strong') if "Benutzername: " in a.text][0]
                password = [a.text.split(" ")[-1] for a in doc.find_all('strong') if "Passwort: " in a.text][0]

            kursliste = user_info['Stundenplan']
            new_relevants = vertretungsplan.getRelevants(kursliste, username, password, level=5).copy()
            if new_relevants != user_info["Relevant"]:
                print(f"{user} is not up to date!")
                uc_command(context=context, user_command="/auskunft", user=int(user))
                print(f"{user} has been sent the latest news.")
            else:
                print(f"{user} is up to date.")


print("Running as " + str(__name__))
if __name__ == "__main__":
    print("Running bot")
    from telegram.ext import MessageHandler, Filters, CallbackQueryHandler

    general_information = read_file(path_to_sensible_data + "general_information.json")
    try:
        interval = general_information["refresh_interval"]
    except KeyError:
        general_information["refresh_interval"] = 600
        write_file(path_to_sensible_data + "general_information.json", general_information)
        interval = general_information["refresh_interval"]
    dispatcher.add_handler(MessageHandler(Filters.command, uc_command))
    dispatcher.add_handler(MessageHandler(Filters.text, uc_text))
    dispatcher.add_handler(MessageHandler(Filters.document, uc_handle_document))
    updater.job_queue.run_repeating(uc_dsb_changed,
                                    interval=interval,
                                    first=interval - time.time() % interval)
    updater.dispatcher.add_handler(CallbackQueryHandler(uc_callback))

    dispatcher.add_error_handler(error)

    updater.start_polling()
    print("Program is running...")
    updater.idle()
    print("Program has stopped.")
