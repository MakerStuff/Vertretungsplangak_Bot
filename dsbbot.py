import sqlite3

from telegram.ext import Updater, MessageHandler
from telegram.error import BadRequest

from orgafunctions import get_support


class DSBBot:
    columns = ["chat_id INTEGER PRIMARY KEY",
               "dsb_user TEXT DEFAULT '213061'",
               "dsb_pswd TEXT DEFAULT 'dsbgak'",
               "last_notification TEXT",
               "support INTEGER DEFAULT 0"]

    def __init__(self,
                 token,
                 database_name: str = ":memory:",
                 updater_use_context=True,
                 **kwargs):
        # apply token
        self.token = token
        # set user commands
        self.__dict__.update({uc: kwargs[uc](str.join("", uc[3:])) for uc in kwargs})
        self.uc_help = self.Help(parent=self)
        self.updater = Updater(token=token, use_context=updater_use_context)
        # database needs to be sql like
        self.database_name = database_name
        database = sqlite3.connect(self.database_name)
        database.execute(f"CREATE TABLE IF NOT EXISTS users({str.join(', ', self.columns)})")
        database.commit()
        # create table for 
        self.updater.dispatcher.add_handler(MessageHandler(None, self.execute_user_command))
        self.updater.dispatcher.add_error_handler(self.Error(self))

    def execute_user_command(self, update, context, do_send=True):
        command_list = [str.join("", cmd[3:]) for cmd in self.__dir__() if cmd.startswith("uc_")]
        cmd = update.message.text.split(" ")[0].lstrip("/").split("@")[0]
        if cmd in command_list:
            result = self.run_command(update_text=update.message.text,
                                      chat_id=update.message.chat_id,
                                      database_name=self.database_name)
        else:
            result = {update.message.chat_id: {"text": self.Error.cmd_unavailable.replace("{cmd}", cmd)}}
        if do_send:
            for chat_id in result:
                try:
                    context.bot.send_message(chat_id=int(chat_id),
                                             text=str(result[chat_id]['text']))
                except BadRequest:
                    print(f"WARNING: BAD REQUEST with chat \"{chat_id}\".")
        return

    def run_command(self,
                    update_text: str,
                    chat_id: int,
                    database_name: str):
        function = self.__getattribute__(f"uc_{str.join('', update_text.split(' ')[0][1:])}")
        return function(update_text=update_text,
                        chat_id=chat_id,
                        database_name=database_name)

    class Help:
        short = "Listet alle verfügbaren Befehle auf."
        header = "Folgende Befehle stehen zur Verfügung:"

        def __init__(self, parent):
            self.parent = parent

        def __call__(self,
                     update_text: str,
                     chat_id: int,
                     database_name: str):
            if not update_text.split(" ")[1:]:
                command_list = ["/" + "".join(cmd[3:]) + " - " + self.parent.__getattribute__(cmd).short
                                for cmd in self.parent.__dir__() if cmd.startswith("uc_")]
                # do not sort command_list for better readability
                return {chat_id: {"text": self.header + "\n" * 2 + str.join("\n", command_list)}}

    class Error:
        cmd_unavailable = "Command \"/{cmd}\" not available"
        no_timetable = "Du hast noch keinen Stundenplan angegeben."

        def __init__(self, parent):
            self.parent = parent

        def __call__(self,
                     update,
                     context):
            return {update.message.chat_id: {"text": context.error},
                    get_support(update.message.chat_id, self.parent.database_name): {"text": context.error}}

    def run(self):
        self.updater.start_polling()
        self.updater.idle()
