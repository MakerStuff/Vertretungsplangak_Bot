# ~ from dsbsession_web import DSBSession as DSBWeb
# ~ from dsbsession_android import DSBSession as DSBAndroid
from .dsbsession_web import DSBSession as DSBWeb
from .dsbsession_android import DSBSession as DSBAndroid

USER, PASS = "213061", "dsbgak"

def fetch_index(logger=None):
	index = DSBWeb.login(USER, PASS).fetch_data_json()
	if index["ResultStatusInfo"] == "Login fehlgeschlagen":
		if logger: logger.warning("DSB Web API failed! Trying Android API...")
		
		index = DSBAndroid.fetch_data_json(USER, PASS)
		if index["ResultStatusInfo"] == "Login fehlgeschlagen":
			raise Exception("Panic: both API's failed!")
	
	return index
