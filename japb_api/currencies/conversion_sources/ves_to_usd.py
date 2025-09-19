import requests


class VesToUsd:
    def getLatestRate():
        # url = "https://pydolarve.org/api/v1/dollar"
        url = "https://ve.dolarapi.com/v1/dolares/paralelo"
        # params = {
        #     "page": "binance",
        #     "format_date": "iso",
        #     "rounded_price": "true",
        # }
        headers = {"Content-Type": "application/json"}

        # EXPECTED RESPONSE:
        # {
        #   "fuente": "paralelo",
        #   "nombre": "Paralelo",
        #   "compra": null,
        #   "venta": null,
        #   "promedio": 243.81,
        #   "fechaActualizacion": "2025-09-15T16:04:01.990Z"
        # }

        response = requests.get(url, headers=headers)

        if response.status_code == 200:
            data = response.json()
            rate = data["promedio"]
            return rate
        else:
            return None

    def getLatestRateBCV():
        url = "https://ve.dolarapi.com/v1/dolares/oficial"
        headers = {"Content-Type": "application/json"}
        response = requests.get(url, headers=headers)

        if response.status_code == 200:
            data = response.json()
            rate = data["promedio"]
            return rate
        else:
            return None
