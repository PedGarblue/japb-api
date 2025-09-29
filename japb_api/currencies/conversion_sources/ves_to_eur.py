import requests
from html.parser import HTMLParser


class _BcvEurParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self._target_depth = 0
        self._in_strong = False
        self.value = None

    def handle_starttag(self, tag, attrs):
        if tag == "div":
            attrs_dict = dict(attrs)
            if attrs_dict.get("id") == "euro":
                self._target_depth = 1
            elif self._target_depth:
                self._target_depth += 1
        elif tag == "strong" and self._target_depth:
            self._in_strong = True

    def handle_endtag(self, tag):
        if tag == "div" and self._target_depth:
            self._target_depth -= 1
        elif tag == "strong" and self._in_strong:
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
            response = requests.get(VesToEur.BCV_URL, timeout=10)
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
