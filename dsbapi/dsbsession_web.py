import requests, base64, gzip, json
from bs4 import BeautifulSoup

LOGIN_URL = "https://www.dsbmobile.de/Login.aspx"
DATA_URLS = [ # Liste von möglichen URLs (DSB ändert die gültige aus irgendeinem Grund immer wieder)
	"https://www.dsbmobile.de/jhw-1fd98248-440c-4283-bef6-dc82fe769b61.ashx/GetData",
	"https://www.dsbmobile.de/jhw-ecd92528-a4b9-425f-89ee-c7038c72b9a6.ashx/GetData",
]


class DSBSession:
	session = None
	
	def __init__(self, http_session):
		self.session = http_session
	
	# Construct a DSBSession by logging in with credentials
	def login(username, password):
		# Start a HTTP session
		session = requests.Session()

		# Get the login page
		r = session.get(LOGIN_URL)

		# From the login page, extract the hidden form inputs and insert
		# username and password
		page = BeautifulSoup(r.text, "html.parser")
		data = {
			"txtUser": username,
			"txtPass": password,
			"ctl03": "Anmelden",
		}
		fields = ["__LASTFOCUS", "__VIEWSTATE", "__VIEWSTATEGENERATOR",
				  "__EVENTTARGET", "__EVENTARGUMENT", "__EVENTVALIDATION"]
		for field in fields:
			element = page.find(id=field)
			if not element is None: data[field] = element.get("value")

		# Submit the form to log in
		session.post(LOGIN_URL, data)
		
		# Return the session
		return DSBSession(session)
	
	# Construct a DSBSession by providing the required "DSBmobile" and
	# "ASP.NET_SessionId" cookies.
	def from_cookies(session_id, dsbmobile_id):
		session = requests.Session()
		session.cookies.set("ASP.NET_SessionId", session_id)
		session.cookies.set("DSBmobile", dsbmobile_id)
		return DSBSession(session)
	
	def try_fetch_data_json(self, data_url):
		# Assemble the POST body for the data request
		params = {
			"UserId": "",
			"UserPw": "",
			"Abos": [],
			"AppVersion": "2.3",
			"Language": "de",
			"OsVersion": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/78.0.3904.70 Safari/537.36",
			"AppId": "",
			"Device": "WebApp",
			"PushId": "",
			"BundleId": "de.heinekingmedia.inhouse.dsbmobile.web",
			"Date": "2019-11-06T16:03:11.322Z",
			"LastUpdate": "2019-11-06T16:03:11.322Z"
		}
		# Convert params into the right format
		params_bytestring = json.dumps(params, separators=(',', ':')).encode("UTF-8")
		params_compressed = base64.b64encode(gzip.compress(params_bytestring)).decode("UTF-8")
		json_data = {"req": {"Data": params_compressed, "DataType": 1}}
		
		# Request data
		headers = {"Referer": "www.dsbmobile.de"}
		r = self.session.post(data_url, json=json_data, headers=headers)
		
		# Decompress the response to get the uncompressed data json
		data_compressed = json.loads(r.content)["d"]
		data = json.loads(gzip.decompress(base64.b64decode(data_compressed)))
		
		return data
	
	def fetch_data_json(self):
		for data_url in DATA_URLS:
			try:
				return self.try_fetch_data_json(data_url)
			except:
				# ~ logger.warning(f"Data url (...{data_url[-20:]}) failed, trying next one..")
				continue
		raise Exception("No data url has worked")
