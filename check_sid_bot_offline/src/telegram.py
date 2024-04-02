import urllib.parse

import logging
import json

from js import Response, fetch, JSON

import messages


_TELEGRAM_URL = "https://api.telegram.org/bot{bot_token}/{method_name}"
_TELEGRAM_SECRET_HEADER = "X-Telegram-Bot-Api-Secret-Token"

logger = logging.getLogger(__name__)


def get_telegram_url(bot_token: str, method_name: str):
    return _TELEGRAM_URL.format(bot_token=bot_token, method_name=method_name)


def _js_json_to_json(js_value):
    json_str = JSON.stringify(js_value)
    return json.loads(json_str)


def _json_to_js_json(py_value):
    json_str = json.dumps(py_value)
    return JSON.parse(json_str)


def _user_id_from_request(request_json):
    if "message" in request_json:
        return request_json["message"]["from"]["id"]

    if "callback_query" in request_json:
        return request_json["callback_query"]["from"]["id"]

    raise ValueError(f"Invalid request JSON: {request_json}")


class Telegram:
    def __init__(
        self,
        token: str,
        webhook_secret: str,
        webhook_url: str,
    ):
        self._token = token
        self._webhook_secret = webhook_secret
        self._webhook_url = webhook_url

    async def _validate_response(self, response):
        logging.info(f"Got response: {response} ({type(response)})")

        if not response.ok:
            response_text = await response.text()
            raise ValueError(
                f"Got invalid response ({response.status} {response.statusText}): {response_text}"
            )

        json_py_value = _js_json_to_json(await response.json())

        if "ok" not in json_py_value or not json_py_value["ok"]:
            raise ValueError(f"Got exception from telegram: {json}")
        return json_py_value["result"]

    async def register_webhook(self):
        url = get_telegram_url(self._token, "setWebhook")
        params = {
            "url": self._webhook_url,
            "secret_token": self._webhook_secret,
        }
        url_params = urllib.parse.urlencode(params)
        url_with_params = f"{url}?{url_params}"
        fetch_response = await fetch(url_with_params)
        return await self._validate_response(fetch_response)

    async def unregister_webhook(self):
        url = get_telegram_url(self._token, "deleteWebhook")
        fetch_response = await fetch(url)
        return await self._validate_response(fetch_response)

    async def _verify_telegram_secret(self, request):
        request_headers = request.headers
        logger.info(f"Request headers: {request_headers}")

        telegram_header = request_headers.get(_TELEGRAM_SECRET_HEADER)
        if telegram_header == self._webhook_secret:
            # Everyhing is fine
            return

        logging.warning(f"Got invalid telegram header: {telegram_header}")
        return Response.new("Got invalid telegram header", status=403)

    async def _remove_keyboard_if_callback_query(self, request_json):
        if "callback_query" not in request_json:
            return

        logging.info("Removing keyboard from callback query")
        callback_query = request_json["callback_query"]
        message = callback_query.get("message", {})
        message_id = message.get("message_id")
        chat_id = message.get("chat", {}).get("id")

        if not message_id or not chat_id:
            logging.error(f"Got invalid inline request {request_json}")
            return

        url = get_telegram_url(self._token, "editMessageReplyMarkup")
        url_params = urllib.parse.urlencode(
            {
                "chat_id": chat_id,
                "message_id": message_id,
            }
        )
        url_with_params = f"{url}?{url_params}"
        await self._validate_response(await fetch(url_with_params))

    async def handle_request(self, request, env):
        if invalid_response := await self._verify_telegram_secret(request):
            return invalid_response

        request_json = _js_json_to_json(await request.json())
        logging.info(f"Request JSON: {request_json}")

        await self._remove_keyboard_if_callback_query(request_json)

        chat_id = _user_id_from_request(request_json)

        logging.info(f"Persisting user id in KV storage: {chat_id}")
        await env.TELEGRAM_USERS.put(chat_id, True)

        logging.info("Sending response")
        json_response = {
            "method": "sendMessage",
            "chat_id": chat_id,
            "text": messages.BOT_OFFLINE_MESSAGE,
        }

        return Response.json(_json_to_js_json(json_response))
