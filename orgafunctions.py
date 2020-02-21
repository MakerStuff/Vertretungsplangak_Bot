import json
import sqlite3


def get_support(chat_id: int,
                database_name: str):
    db = sqlite3.connect(database_name)
    supporter = [x for x in db.execute(f"SELECT support FROM users WHERE chat_id={chat_id};")][0][0]
    if not supporter:
        try:
            supporter = [x for x in db.execute("SELECT chat_id FROM users WHERE support = chat_id;")][0][0]
        except IndexError:
            update_user_profile(chat_id,
                                database_name,
                                support=chat_id)
            supporter = get_support(chat_id,
                                    database_name)
    db.close()
    return supporter


def update_user_profile(chat_id: int,
                        database_name: str,
                        **kwargs):
    parameters = kwargs
    variables = [str.join('=', [x, str(parameters[x])]) for x in parameters]
    columns = str.join(', ', variables)
    db = sqlite3.connect(database_name)
    db.execute(f"UPDATE users SET {columns} WHERE chat_id={chat_id};")
    db.commit()
    db.close()
