import aiohttp
import asyncio
import logging
import platform
import sys
from datetime import datetime, timedelta

BASE_URL = "https://api.privatbank.ua/p24api/exchange_rates?json"
logging.basicConfig(level=logging.DEBUG, format="%(asctime)s - %(message)s")


class HTTPError(Exception):
    def __init__(self, message="Request error."):
        self.message = message
        super().__init__(self.message)


class CommandLineDaysError(Exception):
    def __init__(self, message="Number of days are more than 10."):
        self.message = message
        super().__init__(self.message)


def days_list(days):
    today = datetime.now()

    days_list = [
        (today - timedelta(days=day)).strftime("%d.%m.%Y")
        for day in reversed(range(0, int(days)))
    ]

    return days_list


async def data_parser(data, additional_currency):
    currencies = ["EUR", "USD"]

    exchange_data = data["date"]
    exchange_rate_list = {item["currency"]: item for item in data["exchangeRate"]}

    result_dict = {}

    if (
        additional_currency
        and additional_currency not in currencies
        and additional_currency in exchange_rate_list
    ):
        currencies.append(additional_currency)

    for currency in currencies:
        result_dict[currency] = {
            "sale": exchange_rate_list[currency]["saleRateNB"],
            "purchase": exchange_rate_list[currency]["purchaseRateNB"],
        }

    return {exchange_data: result_dict}


async def request(url, currency):
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url) as responce:
                if responce.status == 200:
                    result = await responce.json()
                    return await data_parser(result, currency)
                else:
                    raise HTTPError(f"Error status: {responce.status} for {url}")
        except aiohttp.ClientConnectionError as error:
            raise HTTPError(f"Connection error: {url} {error}")


async def main(days, currency=None):
    futures = [
        asyncio.create_task(request(url, currency))
        for url in [f"{BASE_URL}&date={day}" for day in days_list(days)]
    ]

    return await asyncio.gather(*futures)


if __name__ == "__main__":
    if platform.system() == "Windows":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    try:
        days_quantity = sys.argv[1]

        if int(days_quantity) > 10:
            raise CommandLineDaysError

        if len(sys.argv) > 2:
            additional_currency = sys.argv[2]

            r = asyncio.run(main(days_quantity, additional_currency))
        else:
            days_quantity = sys.argv[1]

            r = asyncio.run(main(days_quantity))
    except IndexError:
        logging.error("You have not pass all arguments")

    logging.info(r)
