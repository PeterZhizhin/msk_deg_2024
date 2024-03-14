from collections.abc import Sequence
import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ConversationHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

import config
import database_fns
import photos

logger = logging.getLogger(__name__)

# Set the logging level to DEBUG
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

# Define conversation states
MENU, TOPIC_A, TOPIC_B, TOPIC_C, TOPIC_D = range(5)


async def photo_message_handler(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    if update.effective_chat.id not in config.REPLY_WITH_PHOTO_ID_USER_IDS:
        logger.info(
            "Unauthorized user attempted to send a photo: "
            f"{update.effective_chat.id}. Allowed users: {config.REPLY_WITH_PHOTO_ID_USER_IDS}"
        )
        return

    # Extract the file ID of the last photo in the message (highest resolution)
    photo_file_id = update.message.photo[-1].file_id

    # Reply to the user with the photo file ID
    await context.bot.send_message(
        chat_id=update.effective_chat.id, text=f"Photo ID: {photo_file_id}"
    )


async def _send_delimiter(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="🟦" * 10,
    )


def _get_info_keyboard() -> list[list[InlineKeyboardButton]]:
    return [
        [InlineKeyboardButton("Зачем нужен этот бот?", callback_data="why_bot_exists")],
        [
            InlineKeyboardButton(
                "Голосую на участке", callback_data="moscow_in_person_info"
            )
        ],
        [
            InlineKeyboardButton(
                "Голосую в ДЭГ, прописка в Москве",
                callback_data="voting_in_moscow_deg",
            )
        ],
        [
            InlineKeyboardButton(
                "Голосую в ДЭГ, прописка не в Москве",
                callback_data="voting_in_region_deg",
            )
        ],
        [InlineKeyboardButton("Как устроен ДЭГ?", callback_data="how_deg_works")],
    ]


async def start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> int:
    logging.debug(f"Got start from {update.effective_chat.id}")

    database_fns.ensure_user_in_db(update)

    reply_markup = InlineKeyboardMarkup(_get_info_keyboard())
    # Example of sending photos (replace 'URL_or_file_id' with actual URLs or file identifiers)
    # await context.bot.send_photo(chat_id=update.effective_chat.id, photo='URL_or_file_id_of_your_photo')
    # await context.bot.send_photo(chat_id=update.effective_chat.id, photo='URL_or_file_id_of_your_second_photo')

    await context.bot.send_photo(
        chat_id=update.effective_chat.id,
        photo=photos.ENTRANCE_PHOTO_ID,
    )

    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="""
Это бот для проверки голосов дистанционного электронного голосования (ДЭГ). Не дайте украсть свой голос!

Сейчас бот выдаёт общую информацию. Во время голосования бот позволит проверить ваш голос.

При голосовании в ДЭГ в бюллетене поставьте галочку «Хочу получить адрес зашифрованной транзакции в блокчейне», сохраните адрес транзакции.

Подробная информация в разделах ниже ⬇️
""".strip(),
        reply_markup=reply_markup,
    )

    return MENU


async def menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    assert query is not None
    assert update.effective_chat is not None

    await query.answer()

    await query.edit_message_reply_markup(reply_markup=None)
    await _send_delimiter(update, context)

    # Send new message with information based on the button pressed
    if query.data == "back":
        return await start(update, context)
    if query.data in [
        "why_bot_exists",
        "moscow_in_person_info",
        "voting_in_moscow_deg",
        "voting_in_region_deg",
        "how_deg_works",
    ]:
        image_ids = {
            "moscow_in_person_info": photos.MOSCOW_IN_PERSON_INFO,
            "voting_in_moscow_deg": photos.VOTING_IN_MOSCOW_DEG,
            "voting_in_region_deg": photos.VOTING_IN_REGION_DEG,
        }.get(query.data, [])

        if not isinstance(image_ids, list):
            image_ids = [image_ids]

        text = {
            "why_bot_exists": """
Во время голосования через ДЭГ у избирателей есть возможность проверить учёт своего голоса.

На практике, из-за сложности этой проверки мало кто пользуется такой опцией.

Бот призван упростить такую проверку.

Во время голосования бот покажет, учитывает ли система ваш зашифрованный голос в базе данных.
После окончания голосования, для избирателей из Москвы, бот проверит, за кого в итоге учёлся голос.
""".strip(),
            "moscow_in_person_info": """
ТРЕБУЙТЕ БУМАЖНЫЙ БЮЛЛЕТЕНЬ. Вам будут предлагать проголосовать в терминале — НЕ СОГЛАШАЙТЕСЬ.

Терминалы на участках это такой же ДЭГ, непрозрачный и фальсифицируемый. Голосуйте бумажным бюллетенем.

Если вы всё равно голосуете через терминал, то ведите себя так, что вы голосуете через ДЭГ.
Нажмите кнопку "Прописка в Москве, голосую через ДЭГ", чтобы узнать, как обезопасить свой голос.
""".strip(),
            "voting_in_moscow_deg": """
Важно поставить галочку около пункта «Хочу получить адрес зашифрованной транзакции в блокчейне». Он находится в самом низу, по умолчанию отжат и специально сделан незаметным. 

❗️Если не прожать эту галку, голос легко сфальсифицировать и невозможно отследить.❗️

После голосования вы попадёте на страницу с транзакцией (третья картинка).

❗️Вам нужно записать этот номер (он состоит из букв, цифр и дефисов). Так вы сможете проверить ваш голос.❗️

Когда завершится подсчёт, бот покажет, за кого в итоге учёлся ваш голос.
""".strip(),
            "voting_in_region_deg": """
В самом голосовании нужно только проголосовать, информацию о транзакции покажут в любом случае.

После голосования нужно раскрыть поле "Информация о транзакции" и скопировать две строки:
- Идентификатор транзакции
- senderPublicKey

❗️Запишите эти номера, во время голосования бот позволит поверить учёт голоса❗️

По идентификатору транзакции можно получить полную транзакцию и сравнить поле senderPublicKey, которое вы сохранили.

Федеральный ДЭГ не раскрывает никому, как учёлся индивидуальный голос. Бот покажет, что ваш голос попал в общий итог.

Когда подведут итоги пришлите идентификатор транзакции и senderPublicKey в бот. Это позволит проверить, учёлся ли голос.
""".strip(),
            "how_deg_works": """
Дистанционное электронное голосование это система голосования онлайн, без бумажного бюллетеня. Вы открываете браузер, голосуете, ваш голос шифруется, отправляется в базу данных и хранится там до окончания голосования. После окончания голоса подсчитываются и объявляются результаты.

Система ДЭГ непрозрачна и непроверяема. С помощью ДЭГ легко подделать голоса и невозможно отследить фальсификации. Разработчики ДЭГ и центральная избирательная комиссия не дают возможность внешним наблюдателям и независимым экспертам проверить честность системы.

В 2021 году ДЭГ перевернул результаты выборов депутатов Госдумы в Москве. По результатам анализа обработанных данных, проведённого экспертами, выявлены массовые фальсификации голосов в пользу кандидатов от партии власти.

Про фальсификации в 2021 году: https://novayagazeta.ru/articles/2021/09/30/mandaty-polzuiutsia-vbrosom
Про устройство работы ДЭГ в Москве: https://habr.com/ru/articles/689002/
""".strip(),
        }[query.data]

        for image_id in image_ids:
            await context.bot.send_photo(
                chat_id=update.effective_chat.id,
                photo=image_id,
            )

        # After providing information, offer to go back to the main menu
        keyboard = _get_info_keyboard() + [
            [InlineKeyboardButton("Назад в главное меню", callback_data="back")]
        ]

        reply_markup = InlineKeyboardMarkup(keyboard)
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=text,
            reply_markup=reply_markup,
        )

        return MENU

    return await start(update, context)


def main() -> None:
    application = Application.builder().token(config.BOT_TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            MENU: [CallbackQueryHandler(menu_handler)],
        },
        fallbacks=[CommandHandler("start", start)],
    )

    application.add_handler(conv_handler)
    application.add_handler(MessageHandler(filters.PHOTO, photo_message_handler))

    application.run_polling()


if __name__ == "__main__":
    main()
