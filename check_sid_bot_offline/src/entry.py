import enum
import urllib.parse
import logging
import sys

from js import Response

import telegram

logger = logging.getLogger(__name__)

logging.basicConfig(stream=sys.stderr, level=logging.INFO)


def check_webhook_access_token(request, env):
    parsed_url = urllib.parse.urlparse(request.url)
    url_params = urllib.parse.parse_qs(parsed_url.query)

    token = url_params.get("token", [None])[0]
    logging.info(f"Got token: {token}")
    if token == env.WEBHOOK_ACCESS_TOKEN:
        return

    logging.warning(f"Got invlaid access at request URL: {request.url}")
    return Response.new("Got invalid access token", status=403)


class Method(enum.Enum):
    INDEX = "/"
    REGISTER_WEBHOOK = "/register_webhook"
    UNREGISTER_WEBHOOK = "/unregister_webhook"
    WEBHOOK = "/webhook"


def _get_telegram(request, env) -> telegram.Telegram:
    request_url = request.url
    parsed_url = urllib.parse.urlparse(request_url)
    return telegram.Telegram(
        token=env.TELEGRAM_BOT_TOKEN,
        webhook_secret=env.WEBHOOK_SECRET,
        webhook_url=parsed_url.scheme
        + "://"
        + parsed_url.netloc
        + Method.WEBHOOK.value,
    )


async def on_register_webhook(request, env):
    logger.info("Registering webhook")
    if response := check_webhook_access_token(request, env):
        return response

    telegram = _get_telegram(request, env)
    response = await telegram.register_webhook()
    logger.info(f"Webhook registered, response: {response}")
    return Response.new(f"Webhook registered, response: {response}")


async def on_unregister_webhook(request, env):
    print("Unregistering webhook")
    if response := check_webhook_access_token(request, env):
        return response
    telegram = _get_telegram(request, env)
    response = await telegram.unregister_webhook()
    logger.info(f"Webhook unregistered, response: {response}")
    return Response.new("Webhook unregistered")


async def on_webhook(request, env):
    logging.info("Webhook received")
    return await _get_telegram(request, env).handle_request(request, env)


async def on_index(request, env):
    del request
    del env
    return Response.new("Nothing to see here")


_METHOD_TO_HANDLER = {
    Method.INDEX: on_index,
    Method.REGISTER_WEBHOOK: on_register_webhook,
    Method.UNREGISTER_WEBHOOK: on_unregister_webhook,
    Method.WEBHOOK: on_webhook,
}


async def handle_method(request, env) -> Response:
    url = request.url
    method_str = urllib.parse.urlparse(url).path
    method = Method(method_str)
    return await _METHOD_TO_HANDLER[method](request, env)


async def on_fetch(request, env):
    logging.info(f"Got request: {request.url}")
    response = await handle_method(request, env)
    logging.info(f"Returning response: {await response.clone().text()}")
    return response
