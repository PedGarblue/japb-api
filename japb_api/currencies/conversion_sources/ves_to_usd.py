import requests

class VesToUsd:
    def getLatestRate():
        url = "https://pydolarve.org/api/v1/dollar"
        params = {
            "page": "binance",
            "format_date": "iso",
            "rounded_price": "true",
        }
        headers = {"Content-Type": "application/json"}

        # EXPECTED RESPONSE:
        # {
        #     "datetime": {
        #         "date":
        #         "domingo, 12 de enero de 2025",
        #         "time":
        #         "2:56:17 p. m."
        #     },
        #     "monitors": {
        #         "enparalelovzla": {
        #             "change": 0.23,
        #             "color": "green",
        #             "image": "https://res.cloudinary.com/dcpyfqx87...",
        #             "last_update": "2025-01-10T13:32:56-04:00",
        #             "percent": 0.34,
        #             "price": 68.23,
        #             "price_old": 68,
        #             "symbol": "▲",
        #             "title": "EnParaleloVzla"
        #         }
        #     }
        # }

        response = requests.get(url, params=params, headers=headers)

        if response.status_code == 200:
            data = response.json()
            rate = data["monitors"]["binance"]["price"]
            return rate
        else:
            return None
