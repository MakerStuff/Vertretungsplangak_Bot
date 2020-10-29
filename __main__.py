import json
import config

from dsbbot import DSBBot
import usercommands

import logging
import os

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    level=logging.INFO)

logger = logging.getLogger(__name__)

if __name__ == "__main__":
    directory = os.path.expanduser(config.data_location)
    general_information = "general_information.json"
    database = "user_data.sqlite"
    if not os.path.exists(directory):
        os.mkdir(directory)
    if not os.path.exists(directory + general_information):
        with open(directory + general_information, "w") as f:
            f.write(json.dumps({
                "token": input("Enter your token: ")
            }))
            f.close()
        print(f"token has been saved to {directory + general_information}")
    token = json.loads(open(directory + general_information).read())["token"]
    my_bot = DSBBot(token=token,
                    database_name=directory + database,
                    uc_start=usercommands.Start,
                    uc_register=usercommands.Register,
                    uc_update_profile=usercommands.UpdateProfile,
                    uc_delete_profile=usercommands.DeleteProfile,
                    uc_user_info=usercommands.UserInfo,
                    uc_add_lesson=usercommands.AddLesson,
                    uc_remove_lesson=usercommands.RemoveLesson,
                    uc_update_lesson=usercommands.UpdateLesson,
                    uc_view_lessons=usercommands.ViewLessons,
                    uc_information=usercommands.Information,
                    uc_support=usercommands.Support,
                    uc_test=usercommands.Test)
    my_bot.run()
