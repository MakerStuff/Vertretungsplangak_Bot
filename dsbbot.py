import sqlite3

from telegram.ext import Updater, MessageHandler
from telegram.error import BadRequest
from telegram import ChatAction

from orgafunctions import get_support


class UserCommand:
    # usage_string represents the string a user has to enter to access that command eg.: /help
    usage_string = "/"
    no_main_function = "Für diesen Befehl wurde noch keine Funktion hinterlegt."
    no_detail_desc = "Für diesen Befehl wurde noch keine detaillierte Beschreibung hinterlegt."

    def main(self,
             update_text: str,
             chat_id: int,
             database_name: str):
        return {chat_id: {"text": f"Reacting on \"{update_text}\" on {database_name}"}}

    def __init__(self, string: str):
        if not string.startswith("/"):
            string = "/" + string
        self.usage_string = string
        self.detail = self.detail.replace("{usage_string}", self.usage_string)

    def __repr__(self):
        return "<user command \"" + self.usage_string + "\">"

    def __call__(self,
                 update_text: str,
                 chat_id: int,
                 database_name: str,
                 *args, **kwargs):
        if str.join(" ", update_text.split(" ")[1:]) == "help":
            return self.help(update_text=update_text,
                             chat_id=chat_id,
                             database_name=database_name)
        else:
            try:
                return self.main(update_text=update_text,
                                 chat_id=chat_id,
                                 database_name=database_name)
            except AttributeError as e:
                print(e.args)
                return {chat_id: {"text": self.no_main_function},
                        get_support(chat_id, database_name): {"text": self.usage_string
                                                                      + ": "
                                                                      + self.no_main_function + "\n"
                                                                      + str(e.args)}}

    def help(self,
             update_text: str,
             chat_id: int,
             database_name: str):
        if "help" not in update_text.lower():
            print("WANRING: \"help\" not in update_text!")
        try:
            return {chat_id: {"text": self.detail.replace("{usage_string}", self.usage_string)}}
        except AttributeError:
            return {chat_id: {"text": self.no_detail_desc},
                    get_support(chat_id, database_name): {"text": self.usage_string + ": " + self.no_detail_desc}}


class TelegramBot:
    columns = []

    def __init__(self,
                 token,
                 database_name: str = ":memory:",
                 updater_use_context=True,
                 **kwargs):
        # apply token
        self.updater = Updater(token=token, use_context=updater_use_context)

        # set user commands
        self.__dict__.update({uc: kwargs[uc](str.join("", uc[3:])) for uc in kwargs})
        self.uc_help = self.Help(parent=self)

        # Prepare sql like database
        self.database_name = database_name
        database = sqlite3.connect(self.database_name)
        # Create table with user data
        cmd = f"CREATE TABLE IF NOT EXISTS users({str.join(', ', self.columns)})"
        database.execute(cmd)
        database.commit()

        # Add command handlers
        self.updater.dispatcher.add_handler(MessageHandler(None, self.execute_user_command))
        self.updater.dispatcher.add_error_handler(self.Error(self).__call__)

    def execute_user_command(self, update, context, do_send=True):
        context.bot.send_chat_action(chat_id=update.message.chat_id, action=ChatAction.TYPING)
        command_list = [str.join("", cmd[3:]).split("@")[0] for cmd in self.__dir__() if cmd.startswith("uc_")]
        cmd = update.message.text.lstrip("/").split(" ")[0].split("@")[0]
        result = None
        if cmd in command_list:
            result = self.run_command(update_text=update.message.text,
                                      chat_id=update.message.chat_id,
                                      database_name=self.database_name)
        else:
            try:
                result = {update.message.chat_id: {"text": self.Error.cmd_unavailable.replace("{cmd}", cmd)}}
            except AttributeError as e:
                print(f"Error: {e}")
        if do_send and result:
            for chat_id in result:
                try:
                    context.bot.send_message(chat_id=chat_id,
                                             text=str(result[chat_id]['text']))
                except BadRequest:
                    print(f"WARNING: BAD REQUEST with chat \"{chat_id}\".")
            return
        else:
            return result

    def run_command(self,
                    update_text: str,
                    chat_id: int,
                    database_name: str):
        function = self.__getattribute__(f"uc_{str.join('', update_text.split(' ')[0][1:]).split('@')[0]}")
        response = function.__call__(update_text=update_text,
                                     chat_id=chat_id,
                                     database_name=database_name)
        return response

    class Help(UserCommand):
        short = "Listet alle verfügbaren Befehle auf."
        header = "Folgende Befehle stehen zur Verfügung:"
        detail = short

        def __init__(self,
                     parent):
            super().__init__(string="/help")
            self.parent = parent

        def main(self,
                 update_text: str,
                 chat_id: int,
                 database_name: str):
            command_list = ["/" + "".join(cmd[3:]) + " - " + self.parent.__getattribute__(cmd).short
                            for cmd in self.parent.__dir__()
                            if cmd.startswith("uc_")
                            and (cmd in update_text.split(" ")[1:]
                                 or not update_text.split(" ")[1:])]
            # do not sort command_list for better readability
            return {chat_id: {"text": self.header + "\n" * 2 + str.join("\n", command_list)}}

    class Error(UserCommand):
        cmd_unavailable = "Command \"/{cmd}\" not available"
        no_timetable = "Du hast noch keinen Stundenplan angegeben."
        detail = "Used for error handling"

        def __init__(self, parent):
            super().__init__(string="error")
            self.parent = parent

        def __call__(self,
                     update,
                     context):
            print(context.error)
            return {update.message.chat_id: {"text": context.error},
                    get_support(update.message.chat_id, self.parent.database_name): {"text": context.error}}

    def run(self):
        self.updater.start_polling()
        self.updater.idle()


class DSBBot(TelegramBot):
    columns = ["chat_id INTEGER PRIMARY KEY",
               "dsb_user TEXT DEFAULT '213061'",
               "dsb_pswd TEXT DEFAULT 'dsbgak'",
               "last_notification TEXT",
               "support INTEGER DEFAULT 0"]
    columns_timetable = ["ClassName varchar(3)",
                         "WeekDay varchar(10)",
                         "Period varchar(2)",
                         "Subject varchar(3)",
                         "Room varchar(4)",
                         "WeekType varchar(1)",
                         "id INTEGER PRIMARY KEY AUTOINCREMENT"]
