import requests
from html.parser import HTMLParser
import urllib3

# Disable SSL warnings for BCV site
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class _BcvEurParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self._in_euro_div = False
        self._in_strong = False
        self.value = None

    def handle_starttag(self, tag, attrs):
        if tag == "div":
            attrs_dict = dict(attrs)
            if attrs_dict.get("id") == "euro":
                self._in_euro_div = True
        elif tag == "strong" and self._in_euro_div:
            self._in_strong = True

    def handle_endtag(self, tag):
        if tag == "strong" and self._in_strong:
            self._in_strong = False

    def handle_data(self, data):
        if self._in_strong and self.value is None:
            stripped = data.strip()
            if stripped:
                self.value = stripped


class VesToEur:
    BCV_URL = "https://www.bcv.org.ve/"

    @staticmethod
    def getLatestRateBCV():
        try:
            response = requests.get(VesToEur.BCV_URL, timeout=10, verify=False)
        except requests.RequestException:
            return None

        if response.status_code != 200:
            return None

        parser = _BcvEurParser()
        parser.feed(response.text)

        if not parser.value:
            return None

        normalized_value = parser.value.replace(".", "").replace(",", ".")

        try:
            return float(normalized_value)
        except ValueError:
            return None
