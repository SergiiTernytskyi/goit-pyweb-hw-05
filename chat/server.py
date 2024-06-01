import aiohttp
import asyncio
import json
import logging
import names
import websockets
import aiofile
from aiopath import AsyncPath
from datetime import datetime, timedelta
from websockets import WebSocketServerProtocol
from websockets.exceptions import ConnectionClosedOK

BASE_URL = "https://api.privatbank.ua/p24api/exchange_rates?json"
logging.basicConfig(level=logging.INFO)


class HTTPError(Exception):
    def __init__(self, message="Request error."):
        self.message = message
        super().__init__(self.message)


async def data_parser(data):
    currencies = ["EUR", "USD"]

    exchange_data = data["date"]
    exchange_rate_list = {item["currency"]: item for item in data["exchangeRate"]}

    result_dict = {}

    for currency in currencies:
        result_dict[currency] = {
            "sale": exchange_rate_list[currency]["saleRateNB"],
            "purchase": exchange_rate_list[currency]["purchaseRateNB"],
        }

    return {exchange_data: result_dict}


async def request(url):
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url) as responce:
                if responce.status == 200:
                    result = await responce.json()
                    return await data_parser(result)
                else:
                    raise HTTPError(f"Error status: {responce.status} for {url}")
        except aiohttp.ClientConnectionError as error:
            raise HTTPError(f"Connection error: {url} {error}")


async def get_exchange(days):
    futures = [
        asyncio.create_task(request(url))
        for url in [
            f"{BASE_URL}&date={day}"
            for day in [
                (datetime.now() - timedelta(days=day)).strftime("%d.%m.%Y")
                for day in reversed(range(0, int(days)))
            ]
        ]
    ]

    return await asyncio.gather(*futures)


class Server:
    clients = set()

    async def register(self, ws: WebSocketServerProtocol):
        ws.name = names.get_full_name()
        self.clients.add(ws)
        logging.info(f"{ws.remote_address} connects")

    async def unregister(self, ws: WebSocketServerProtocol):
        self.clients.remove(ws)
        logging.info(f"{ws.remote_address} disconnects")

    async def send_to_clients(self, message: str):
        if self.clients:
            [await client.send(message) for client in self.clients]

    async def ws_handler(self, ws: WebSocketServerProtocol):
        await self.register(ws)
        try:
            await self.distrubute(ws)
        except ConnectionClosedOK:
            pass
        except Exception as e:
            logging.error(f"Error in WebSocket handler: {e}")
        finally:
            await self.unregister(ws)

    async def log_command(self, command):
        log_path = AsyncPath("chat/exchange_commands.log")
        async with aiofile.async_open(log_path, "a", encoding="utf-8") as log:
            await log.write(f"{datetime.now()}: {command}\n")

    async def distrubute(self, ws: WebSocketServerProtocol):
        async for message in ws:
            params = message.split(" ")
            if params[0] == "exchange":
                days = int(params[1]) if len(params) > 1 else 1
                self.log_command(message)

                try:
                    exchange_rates = await get_exchange(days)
                    response = json.dumps(exchange_rates, ensure_ascii=False)
                    await self.send_to_clients(response)
                except Exception as err:
                    await ws.send(f"An error occurred: {str(err)}")
            elif message == "Hello server":
                await self.send_to_clients("Привіт мої карапузи!")
            else:
                await self.send_to_clients(f"{ws.name}: {message}")


async def main():
    server = Server()
    async with websockets.serve(server.ws_handler, "localhost", 8080):
        await asyncio.Future()


if __name__ == "__main__":
    asyncio.run(main())
