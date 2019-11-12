import csv
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

import vertretungsplan

path_to_sensible_data = "../Vertretungsplangak_Data/"
path_to_user_data = path_to_sensible_data + "userdata/"

updater = Updater(token=json.loads(open(path_to_sensible_data + "general_information.json", "r", encoding="utf-8").read())["token"], use_context=True)

dispatcher = updater.dispatcher

# Enable logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    level=logging.INFO)

logger = logging.getLogger(__name__)

def send_typing_action(func):
    """Sends typing action while processing func command."""

    @wraps(func)
    def command_func(update, context, *args, **kwargs):
        context.bot.send_chat_action(chat_id=update.effective_message.chat_id, action=ChatAction.TYPING)
        return func(update, context,  *args, **kwargs)

    return command_func

def start(update, context):
    context.bot.send_message(chat_id=update.message.chat_id, text="Nutze mich, um die den Vertretungsplan deiner Schule vereinfacht darzustellen. Der Autor des Bots übernimmt keine Haftung für die Richtigkeit der Daten.\nDieser Bot wurde programmiert um den Vertretungsplan des Gymnasiums am Kattenberge auszulesen. Andere Schulen funktionieren möglicherweise nicht.\n\nNutze \"/addlesson help\" um zu lernen, wie du deinen Stundenplan erstellen kannst, oder /help für eine Übersicht über alle Befehle.")

def text(update, context):
    if update.message.chat.type == "private":
        context.bot.send_message(chat_id=update.message.chat_id, text="Ich kann \"" + update.message.text + "\" nicht verstehen. Nutze /help, um eine Übersicht über die Befehle anzeigen zu lassen.")

def sort_timetable(timetable):
    sortable_timetable = timetable
    for entry in sortable_timetable:
        try:
            entry[1] = [vertretungsplan.wday[a] for a in vertretungsplan.wday if a.capitalize() == entry[1].capitalize()][0]
        except IndexError:
            pass
    sorted_timetable = sorted(sortable_timetable)
    for entry in sorted_timetable:
        try:
            entry[1] = [a for a in vertretungsplan.wday][entry[1]]
        except IndexError:
            pass
        try:
            entry[0] = entry[0].upper()
        except TypeError:
            pass
    return(sorted_timetable)

@send_typing_action
def addlesson(update, context):
    user_id = update.message.from_user['id']
    #print(user_id)
    #print(update.message.text)
    parameters = update.message.text.split(" ")[1:]
    user_info = {}
    #print(parameters)
    if not parameters:
        context.bot.send_message(chat_id = update.message.chat_id, text = "Nutze \"/addlesson help\" um zu lernen, wie du eine Stunde zu deinem Stundenplan hinzufügst.")
        return
    if parameters == ['help']:
        context.bot.send_message(chat_id=user_id, text="Ein Eintrag für eine Stunde muss in einer der folgenden Formen angegeben werden:\n\nGib deine Klasse so an, wie sie auf dem Vertretungsplan angezeigt wird. Beispielsweise:\n05A\n10B\n\n ODER liste folgende Informationen durch ein Leerzeichen getrennt auf:\n - Klasse\n - Wochentag des Kurses (mo, di, mi, do, ...)\n - Stunde (Nur eine Stunde pro Eintrag)\n - Fach (Abgekürzt wie auf dem offiziellen Vertretungsplan)\n - Raum\n - (falls angegeben) Wochentyp (A oder B)\nBeispielsweise:\n/addlesson 05A mo 1 Deu 1.11\n/addlesson 12 mo 3-4 Deu 2.34")
        return
    elif len(parameters) in (1, 5, 6,):
        try:
            user_info = json.loads(open(path_to_user_data + str(user_id) + ".json").read())
        except (FileNotFoundError, SyntaxError):
            user_info = {'Benutzername': 'Default',
                         'Passwort': 'Default',
                         'Stundenplan': []}
        parameters = [a.capitalize() for a in parameters]
        if len(parameters) == 1:
            parameters[0] = parameters[0].upper()
            lesson = parameters
            user_info["Stundenplan"].append(lesson)
        if len(parameters) != 1:
            for stunde in parameters[2].split("-"):
                lesson = parameters
                lesson[2] = stunde
                user_info['Stundenplan'].append(lesson)
        user_info['Stundenplan'] = sort_timetable(user_info['Stundenplan'])
        with open(path_to_user_data + str(user_id) + ".json", "w") as file:
            file.write(json.dumps(user_info))
            file.close()
        context.bot.send_message(chat_id = update.message.chat_id, text = str(parameters) + " wurde erfolgreich deinem Stundenplan hinzugefügt.")
    else:
        context.bot.send_message(chat_id = update.message.chat_id, text = "Unbekanntes Format. Nutze \"/addlesson help\" zur Hilfe.")

@send_typing_action
def rmlesson(update, context):
    user_id = update.message.from_user['id']
    parameters = update.message.text.split(" ")[1:]
    if parameters == []:
        context.bot.send_message(chat_id = update.message.chat_id, text = "Bitte gib die Nummer deines Eintrags an. Du kannst mit /checktimetable sehen, welcher Stunde welche Nummer zugeordnet wurde.")
        return(None)
    user_info = json.loads(open(path_to_user_data + str(user_id) + ".json").read())
    del user_info['Stundenplan'][int(parameters[0])-1]
    with open(path_to_user_data + str(user_id) + ".json", "w") as file:
        file.write(json.loads(user_info))
        file.close()
    context.bot.send_message(chat_id = update.message.chat_id, text = "Dein Stundenplan wurde bearbeitet. Nutze /checktimetable um ihn zu überprüfen.")

@send_typing_action
def checktimetable(update, context):
    user_id = update.message.from_user['id']
    parameters = update.message.text.split(" ")[1:]
    try:
        user_info = json.loads(open(path_to_user_data + str(user_id) + ".json", encoding="utf-8").read())
        if "sort" in parameters:
            user_info['Stundenplan'] = sort_timetable(user_info['Stundenplan'])
            with open(path_to_user_data + str(user_id) + ".json", "w") as file:
                file.write(str(user_info))
                file.close()
        if "csv" in parameters:
            if "help" in parameters:
                context.bot.send_message(chat_id=update.message.chat_id, text="Nutze folgende Beschreibung, um deinen Stundenplan in Excel anzusehen:\nÖffne Excel\nKlicke auf \"Daten/Externe Daten abrufen/Aus Text\" und wähle die Datei aus, die dir der Bot nach /checktimetable csv zugesendet hat.\nWähle \"Getrennt\" aus und drücke auf \"Weiter\"\nSetzt einen Haken bei \"Komma\" un drücke auf \"Weiter\"\nDrücke auf \"Fertig stellen\"\nDrücke auf \"OK\"\nBearbeite deine Daten wie es dir beliebt.")
            with open(str(user_id)+".csv", "w", encoding='utf-8') as timetable:
                timetable_writer = csv.writer(timetable, delimiter=',', quotechar='"', quoting=csv.QUOTE_MINIMAL)

                weekdays = vertretungsplan.wday
                #timetable_writer.writerow(weekdays)

                for lesson in range(max([int(subject[2]) for subject in user_info['Stundenplan']])):
                    timetable_writer.writerow([" / ".join([" ".join([subject[a] for a in range(len(subject)) if not a in [1, 2, ]]) for subject in user_info['Stundenplan'] if subject[1] == wday and int(subject[2]) == lesson+1]) for wday in weekdays])
            csv_doc = open(str(user_id)+".csv", "rb")
            print("Read doc")
            context.bot.send_document(chat_id=update.message.chat_id, document=csv_doc)
            csv_doc.close()
            os.remove(str(user_id) + ".csv")
        else:
            timetable_txt = ""
            index = 1 # beginne bei 1 mit dem Zählen
            for note in user_info['Stundenplan']:
                timetable_txt = timetable_txt + str(index) + ". "
                for entry in note:
                    timetable_txt = timetable_txt + str(entry) + "\t"
                timetable_txt = timetable_txt + "\n"
                index += 1
            context.bot.send_message(chat_id=update.message.chat_id, text="Hier ist dein " + "sortierter " * ("sort" in update.message.text.split(" ")[1:]) + "Stundenplan:\n" + timetable_txt)
    except FileNotFoundError:
        context.bot.send_message(chat_id=update.message.chat_id, text="Ich kann keine Daten zu deinem Stundenplan finden. Nutze \"addlesson help\" um zu lernen, wie du deinen Stundenplan erstellen kannst.")

@send_typing_action
def createtimetable(update, context):
    # Dieser Befehl erlaubt es dem Nutzer, den eigenen Stundenplan mit einer CSV-Datei zu ersetzen
    user_id = update.message.from_user["id"]
    parameters = update.message.text.split(" ")[1:]
    if "help" in parameters:
        context.bot.send_message(chat_id=update.message.chat_id, text="Wenn du dir unsicher bist, wie deine CSV-Tabelle aussehen soll, erstelle einige Einträge mit /addlesson und sieh dir die Datei mit \"/checktimetable csv\" an.")
        return
    if update.message.document:
        doc = update.message.document
        print(doc)

@send_typing_action
def help(update, context):
    command_description = json.loads(open(path_to_sensible_data + "command_description.json", "r", encoding="utf-8").read())
    if not update.message.text.split(" ")[1:]:
        message = "Die folgenden Befehle stehen zur Verfügung:\n"
        for a in dispatcher.handlers[0]:
            if type(a) == CommandHandler:
                try:
                    message = message + "\n/" + a.command[0] + " - " + command_description[a.command[0]]
                except KeyError:
                    if str(update.message.chat_id) in json.loads(open(path_to_sensible_data + "general_information.json", encoding="utf-8").read())["supporter"]:
                        message = message + "\n/" + a.command[0]
                    print("Es gibt (noch) keine Erklärung für \"" + a.command[0] + "\"")
    else:
        message = "Hier sind Details zu den gefragten Befehlen:\n"
        for command in update.message.text.split(" ")[1:]:
            if command in [a.command[0] for a in dispatcher.handlers[0] if type(a) == CommandHandler]:
                message = message + "\n/" + command + " " + command_description[command]
    context.bot.send_message(chat_id=update.message.chat_id, text=message)

@send_typing_action
def auskunft(update, context):
    user_id = update.message.from_user['id']
    parameters = update.message.text.split(" ")[1:]
    reply = ""
    default_iterations = 3
    max_iterations = 7
    if parameters == []:
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
            context.bot.send_message(chat_id=update.message.chat_id, text="Ich habe keine Informationen über dich gespeichert. Bitte trage deinen Stundenplan mit /addlesson ein, damit ich dir helfen kann.")
            return

        # Correct username and password
        username = user_info['Benutzername']
        password = user_info['Passwort']
        if username == "Default" == password:
            doc = bs(requests.get("http://www.gak-buchholz.de/unterricht/vertretungsplan/").text, "html.parser")
            username = [a.text.split(" ")[-1] for a in doc.find_all('strong') if "Benutzername: " in a.text][0]
            password = [a.text.split(" ")[-1] for a in doc.find_all('strong') if "Passwort: " in a.text][0]

        message = ""
        for a in vertretungsplan.getNews(username, password):
            message = message + "\n" + a[0] + ": " + a[1]
        if message != "":
            reply = reply + "Nachrichten zum Tag:" + message + "\n\n"

        # restart for lessons
        message = ""
        kursliste = user_info['Stundenplan']
        for eintrag in vertretungsplan.getRelevants(kursliste, username, password, 5):
            if not eintrag[9] in message:
                message = message + "\n"
                message = message + str([a for a in vertretungsplan.wday if vertretungsplan.wday[a] == time.gmtime(datetime.datetime.strptime(eintrag[9], '%d.%m.%Y').timestamp()-time.altzone).tm_wday][0].capitalize()) + " " + eintrag[9] + " " + eintrag[1] + ": " + eintrag[0] + " " + eintrag[3] + " " + eintrag[5] + " --> " + eintrag[7] + " " + eintrag[2] + " in Raum " * bool(len(eintrag[4])) + eintrag[4] + ". Beschreibung: " * bool(len(eintrag[8])) + eintrag[8] + ". Vertretung von " * bool(len(eintrag[6])) + eintrag[6]
        if message != "":
            reply = reply + "Für dich relevante Einträge:" + message + "\n\n"
        else:
            reply = reply + "Aktuell liegen keine Einträge für dich vor." + "\n\n"

        # Last updated:
        message = ""
        try:
            doc = bs(requests.get(vertretungsplan.getURL(username, password)).text, "html.parser")
            last_update = [a.text for a in doc.find_all("p") if "Stand: " in a.text][0]
            #for a in last_update.split("  "):
            #    if not len([b for b in a if " " in b]) == 0:
            #        message = message + a + "\n"
            message = message + "Stand: " + " ".join(last_update.split(" Stand: ")[-1].split(" ")[0:2])
            reply = reply + message + "\n"
        except Exception as e:
            print(e)
            pass
        reply_footer =  "Bitte überprüfe die Einträge auf <a href=\"" + vertretungsplan.getURL(username, password) + "\">der offiziellen Darstellung des Vertretungsplans</a>."
        context.bot.send_message(chat_id=update.message.chat_id,
                                 text=reply + reply_footer,
                                 parse_mode=ParseMode.HTML)
        break

@send_typing_action
def changelogin(update, context):
    user_id = update.message.from_user['id']
    parameters = update.message.text.split(" ")[1:]
    if len(parameters) == 2:
        user_info = json.loads(open(path_to_user_data + str(user_id) + ".json", encoding="utf-8").read())
        user_info['Benutzername'] = parameters[0]
        user_info['Passwort'] = parameters[1]
        with open(path_to_user_data + str(user_id) + ".json", 'w') as file:
            file.write(str(user_info))
            file.close()
        context.bot.send_message(chat_id=update.message.chat_id, text=f"Dein Nutzerdaten wurden geändert zu\nBenutzername: {user_info['Benutzername']}\nPasswort: {user_info['Passwort']}")
    else:
        context.bot.send_message(chat_id=update.message.chat_id, text="Überprüfe bitte die Syntax deiner Angaben.")

@send_typing_action
def user_data(update, context):
    user_id = update.message.from_user['id']
    try:
        file = path_to_user_data + str(user_id) + ".json"
        user_info = json.loads(open(file, "r", encoding="utf-8").read())
        context.bot.send_document(chat_id=update.message.chat_id, document=open(file, 'rb'))
        context.bot.send_message(chat_id=update.message.chat_id, text="Hier sind alle Daten, die dem System über dich bekannt sind.")
    except FileNotFoundError:
        context.bot.send_message(chat_id=update.message.chat_id, text="Es liegen keine Daten zu deiner Nutzer-ID vor. Bitte nutze /addlesson um deinen Stundenplan einzurichten")

@send_typing_action
def clear_data(update, context):
    user_id = update.message.from_user['id']
    os.remove(path_to_user_data + str(user_id) + ".json")
    try:
        open(str(user_id)+".json")
        print("Fehler beim Löschen der Daten eines Nutzers: Daten noch vorhanden:")
        context.bot.send_message(chat_id=update.message.chat_id, text="Beim Löschen deiner Daten ist ein Fehler aufgetreten. Falls der Fehler weiterhin besteht, kontaktiere bitten den Host dieses Bots.")
    except FileNotFoundError:
        context.bot.send_message(chat_id=update.message.chat_id, text="Deine Daten wurden erfolgreich gelöscht.")

@send_typing_action
def aktuell(update, context):
    # Diese Funktion seigt die Unterrichtsstunden an, die heute und morgen für den Nutzer interessant sind.
    # Hierzu muss der gesamte Stundenplan hinterlegt sein.
    context.bot.send_message(chat_id=update.message.chat_id, text="Diese Funktion befindet sich derzeit im Aufbau und steht nicht zur Verfügung.")

@send_typing_action
def support(update, context):
    parameters = update.message.text.split(" ")[1:]
    if parameters and not update.message.from_user["is_bot"]:
        data = json.loads(open(path_to_sensible_data + "general_information.json", encoding="utf-8").read())
        support_info = data["supporter"]
        least_clients = min([len(support_info[a]["clients"]) for a in support_info])
        supporter = ""
        client = update.message.from_user["id"]
        for support in support_info:
            if client in support_info[support]["clients"]:
                supporter = int(support)
                break
        if not supporter:
            supporter = [a for a in support_info if len(support_info[a]["clients"]) <= least_clients][0]
            data["supporter"][str(supporter)]["clients"].append(client)
        with open(path_to_sensible_data + "general_information.json", "w", encoding="utf-8") as file:
            data["supporter"] = support_info
            file.write(json.dumps(data))
            file.close()
        meta = str(update.message.chat_id)
        problem = " ".join(parameters)
        context.bot.forward_message(chat_id=supporter, from_chat_id=update.message.chat_id, message_id=update.message.message_id, text=meta + " hat folgendes Problem mit dem Vertretungsplan_Bot:\n\n" + problem)
        context.bot.send_message(chat_id=update.message.from_user["id"], text="Dein Anliegen wurde an deinen Supporter gesendet. Bitte nimm zur Kenntnis, dass dieses Projekt freiwillig betrieben wird und wir manchmal auch keine Zeit haben, um direkt zu antworten.")

@send_typing_action
def answer_support_question(update, context):
    if str(update.message.chat_id) in json.loads(open(path_to_sensible_data + "general_information.json", encoding="utf-8").read())["supporter"]:
        reply_message = "Du hast eine Antwort vom Support erhalten:\n\n" + " ".join(update.message.text.split(" ")[1:])
        user = update.message.reply_to_message.forward_from
        supporter = update.message.chat_id
        if reply_message:
            original_message = update.message.reply_to_message
            print(original_message)
            context.bot.send_message(chat_id=user["id"], text=reply_message)
            success_message = "Die Antwort wurde erfolgreich an " + str(user) + " gesendet."
            context.bot.send_message(chat_id=supporter, text=success_message)
        else:
            context.bot.send_message(chat_id=supporter, text="Die Nachricht muss Text enthalten.\n/answer_sq <Antwort-Text>")
    else:
        print(f"Unautorisierter Zugriff auf answer_service_qestion durch {update.message.from_user}")

@send_typing_action
def send_emergency_url(update, context):
    parameters = update.message.text.split(" ")[1:]
    info = json.loads(open(path_to_sensible_data + "general_information.json", "r", encoding="utf-8").read())
    if update.message.chat_id in info["supporter"]:
        info["emergency_url"] = parameters[0]
    with open(path_to_sensible_data + "general_information.json") as file:
        file.write(json.dumps(info))
        file.close()

@send_typing_action
def error(update, context):
    update_text = ""
    context_error_text = ""
    try:
        update_text = str(update)
    except:
        pass
    try:
        context_error_text = str(context.error)
    except:
        pass
    try:
        """Log Errors caused by Updates."""
        logger.warning('Update "%s" caused error "%s"', update, context.error)
        context.bot.send_message(chat_id=update.message.chat_id, text="Es ist ein Fehler aufgetreten. Bitte versuche es erneut oder kontaktiere den Support mit /support.")
    except Exception as e:
        print(e)
    data = json.loads(open(path_to_sensible_data + "general_information.json", encoding="utf-8").read())
    support_info = data["supporter"]
    least_clients = min([len(support_info[a]["clients"]) for a in support_info])
    supporter = ""
    client = update.message.from_user["id"]
    for support in support_info:
        if client in support_info[support]["clients"]:
            supporter = int(support)
            break
    if not supporter:
        supporter = [a for a in support_info if len(support_info[a]["clients"]) <= least_clients][0]
        data["supporter"][str(supporter)]["clients"].append(client)
    with open(path_to_sensible_data + "general_information.json", "w", encoding="utf-8") as file:
        data["supporter"] = support_info
        file.write(json.dumps(data))
        file.close()
    error_message = f"Fehler:\n\"{update_text}\" caused:\n\"{context_error_text}\""
    context.bot.send_message(chat_id=supporter, text=error_message, disable_notification=True)

@send_typing_action
def report_error(update, context):
    impossible_message = update.message.reply_to_message
    try:
        True
    except:
        pass

@send_typing_action
def status(update, context):
    # Make it possible for the support to change this message
    parameters = update.message.text.split(" ")[1:]
    if str(update.message.chat_id) in json.loads(open(path_to_sensible_data + "general_information.json", encoding="utf-8").read())["supporter"]:
        if parameters:
            info = json.loads(open(path_to_sensible_data + "general_information.json", "r", encoding="utf-8").read())
            info["status_message"] = " ".join(parameters)
            with open(path_to_sensible_data + "general_information.json", "w", encoding="utf-8") as file:
                file.write(json.dumps(info))
                file.close()
    context.bot.send_message(chat_id=update.message.chat_id, text=str(json.loads(open(path_to_sensible_data + "general_information.json", encoding='utf-8').read())["status_message"]))

@send_typing_action
def test(update, context):
    raise(Exception("Dieser Fehler ist Absicht!"))

def stop(updater):
    updater.stop()
    updater.is_idle = False

def stop_bot(update, context):
    if str(update.message.chat_id) in json.loads(open(path_to_sensible_data + "general_information.json").read())["supporter"]:
        threading.Thread(target=stop, args=(updater,)).start()

print("Hello World!")
print("Running as " + str(__name__))
if __name__ == "__main__":
    from telegram.ext import CommandHandler
    dispatcher.add_handler(CommandHandler('help', help))
    dispatcher.add_handler(CommandHandler('start', start))
    dispatcher.add_handler(CommandHandler('status', status))
    dispatcher.add_handler(CommandHandler('addlesson', addlesson))
    dispatcher.add_handler(CommandHandler('rmlesson', rmlesson))
    dispatcher.add_handler(CommandHandler('checktimetable', checktimetable))
    dispatcher.add_handler(CommandHandler('auskunft', auskunft))
    dispatcher.add_handler(CommandHandler('support', support))
    dispatcher.add_handler(CommandHandler('changelogin', changelogin))
    dispatcher.add_handler(CommandHandler('userdata', user_data))
    dispatcher.add_handler(CommandHandler('cleardata', clear_data))
    dispatcher.add_handler(CommandHandler('answer_sq', answer_support_question))
    dispatcher.add_handler(CommandHandler('test', test))
    dispatcher.add_handler(CommandHandler('send_emergency_url', send_emergency_url))
    dispatcher.add_handler(CommandHandler('stop_bot', stop_bot))
    #dispatcher.add_handler(CommandHandler('meineinfos', getRelevant))

    from telegram.ext import MessageHandler, Filters
    dispatcher.add_handler(MessageHandler(Filters.text, text))

    dispatcher.add_error_handler(error)

    updater.start_polling()
    print("Program is running...")
    updater.idle()
    print("Program has stopped.")
