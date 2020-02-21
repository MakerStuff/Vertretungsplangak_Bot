import json
import sqlite3

from dsbbot import DSBBot
import usercommands

import logging

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    level=logging.INFO)

logger = logging.getLogger(__name__)

if __name__ == "__main__":
    token = json.loads(open("../Vertretungsplangak_Data/general_information.json").read())["token"]
    my_bot = DSBBot(token=token,
                    database_name="../Vertretungsplangak_Data/user_data.sqlite",
                    uc_register=usercommands.Register,
                    uc_update_profile=usercommands.UpdateProfile,
                    uc_delete_profile=usercommands.DeleteProfile,
                    uc_information=usercommands.Information,
                    uc_test=usercommands.Test,
                    uc_user_info=usercommands.UserInfo,
                    uc_start=usercommands.Start,
                    uc_add_lesson=usercommands.AddLesson,
                    uc_update_lesson=usercommands.UpdateLesson,
                    uc_view_lessons=usercommands.ViewLessons,
                    uc_remove_lesson=usercommands.RemoveLesson,
                    uc_support=usercommands.Support)
    my_bot.run()
