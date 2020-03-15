import requests, base64, gzip, json, datetime, uuid
from bs4 import BeautifulSoup

DATA_URL = "https://app.dsbcontrol.de/JsonHandler.ashx/GetData"


class DSBSession:
    # Sends a data request to the server.
    # Returns the URL to the timetable HTML page
    def fetch_data_json(username, password):
        # Iso format is for example 2019-10-29T19:20:31.875466
        current_time = datetime.datetime.now().isoformat()
        # Cut off last 3 digits and add 'Z' to get correct format
        current_time = current_time[:-3] + "Z"
        
        # Parameters required for the server to accept our data request
        params = {
            "UserId": username,
            "UserPw": password,
            "AppVersion": "2.5.9",
            "Language": "de",
            "OsVersion": "28 9",
            "AppId": str(uuid.uuid4()),
            "Device": "SM-G935F",
            "BundleId": "de.heinekingmedia.dsbmobile",
            "Date": current_time,
            "LastUpdate": current_time
        }
        # Convert params into the right format
        params_bytestring = json.dumps(params).encode("UTF-8")
        params_compressed = base64.b64encode(gzip.compress(params_bytestring)).decode("UTF-8")
        
        # Send the request
        json_data = {"req": {"Data": params_compressed, "DataType": 1}}
        timetable_data = requests.post(DATA_URL, json = json_data)
        
        # Decompress response
        data_compressed = json.loads(timetable_data.content)["d"]
        data = json.loads(gzip.decompress(base64.b64decode(data_compressed)))
        
        return data
