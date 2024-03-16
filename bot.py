from collections.abc import Sequence
import functools
import logging
import traceback

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

import check_sid
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
MENU, ASKED_FOR_INFO_OPTIONS, MOSCOW_ASKED_IF_CHECKED_SID, MOSCOW_ASKED_FOR_SID = range(
    4
)


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
        chat_id=update.effective_chat.id,
        text=f"Photo ID: {photo_file_id}",
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


def _get_menu_keyboard() -> list[list[InlineKeyboardButton]]:
    return [
        [
            InlineKeyboardButton(
                "ДЭГ Москвы: Проверка транзакции",
                callback_data="moscow_check_sid",
            ),
        ],
        [
            InlineKeyboardButton(
                "Голосую бумажным бюллетенем в любом регионе",
                callback_data="voting_in_person_redirect",
            ),
        ],
        [
            InlineKeyboardButton("Информация про ДЭГ", callback_data="info"),
        ],
    ]


async def start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> int:
    logging.debug(f"Got start from {update.effective_chat.id}")

    database_fns.ensure_user_in_db(update)

    query = update.callback_query
    if query is not None:
        await query.answer()
        await query.edit_message_reply_markup(reply_markup=None)

    reply_markup = InlineKeyboardMarkup(_get_menu_keyboard())
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

При голосовании в ДЭГ в бюллетене поставьте галочку «Хочу получить адрес зашифрованной транзакции в блокчейне», сохраните адрес транзакции.

Сейчас бот может проверить ДЭГ Москвы, или рассказать общую информацию.

Подробная информация в разделах ниже ⬇️
""".strip(),
        reply_markup=reply_markup,
    )

    return MENU


async def redirect_to_dobrostat(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    query = update.callback_query
    if query is not None:
        await query.answer()
        await query.edit_message_reply_markup(reply_markup=None)

    await _send_delimiter(update, context)

    await context.bot.send_photo(
        chat_id=update.effective_chat.id,
        photo=photos.MOSCOW_IN_PERSON_INFO[0],
    )

    reply_markup = InlineKeyboardMarkup(_get_menu_keyboard())

    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="""
Отправьте фотографию заполенного буажного бюллетеня в бота @dobrostatbot.

Бот ведёт независимый учёт голосов.

В Москве не забывайте, что бумажный бюллетень надо просить отдельно. Вам предложат проголосовать через терминал: это ДЭГ. Непрозрачный и непроверяемый.
""".strip(),
        reply_markup=reply_markup,
    )

    return MENU


async def moscow_check_sid_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> int:
    query = update.callback_query
    assert query is not None
    assert update.effective_chat is not None

    await query.answer()

    await query.edit_message_reply_markup(reply_markup=None)

    reply_markup = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("Назад", callback_data="back"),
            ],
            [
                InlineKeyboardButton(
                    "Да, я поставил галочку",
                    callback_data="yes",
                ),
            ],
            [
                InlineKeyboardButton(
                    "Нет, я не ставил галочек проверки голоса",
                    callback_data="no",
                ),
            ],
        ]
    )

    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="""
Для проверки голоса вы были должны сделать:

- Поставить галочку «Хочу получить адрес зашифрованной транзакции в блокчейне» в бюллетене.
- Записать полученный шифр.

Вы это сделали?
""".strip(),
        reply_markup=reply_markup,
    )

    return MOSCOW_ASKED_IF_CHECKED_SID


async def moscow_yes_i_checked_sid(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> int:
    query = update.callback_query
    assert query is not None
    assert update.effective_chat is not None

    await query.answer()

    await query.edit_message_reply_markup(reply_markup=None)

    reply_markup = InlineKeyboardMarkup(
        [[InlineKeyboardButton("В главное меню", callback_data="back")]]
    )

    msg = await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=f"""
Пришлите мне полученный адрес транзакции.

Это должна быть строка из букв, цифр и дефисов.

Пример: {config.HARDCODED_MOSCOW_VALID_SID}
""".strip(),
        reply_markup=reply_markup,
    )
    context.user_data["delete_keyboard_message_id"] = msg.message_id

    return MOSCOW_ASKED_FOR_SID


async def moscow_sid_message_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> int:
    assert update.message is not None

    user_text = update.message.text

    assert user_text is not None

    user_text = user_text.strip()

    reply_buttons = [[InlineKeyboardButton("В главное меню", callback_data="back")]]

    user_data = context.user_data
    delete_keyboard_message_id = user_data.get("delete_keyboard_message_id")
    if delete_keyboard_message_id:
        await context.bot.edit_message_reply_markup(
            chat_id=update.effective_chat.id,
            message_id=delete_keyboard_message_id,
            reply_markup=None,  # This removes the keyboard
        )

    if not check_sid.is_valid_sid(user_text):
        logging.info(f"Entered invalid SID: {user_text}")
        msg = await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="""
Это не похоже на адрес транзакции. Попробуйте еще раз.
    """.strip(),
            reply_markup=InlineKeyboardMarkup(reply_buttons),
        )
        user_data["delete_keyboard_message_id"] = msg.message_id
        return MOSCOW_ASKED_FOR_SID

    try:
        sid_data = check_sid.query_sid(user_text)
    except ValueError as e:
        msg = await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=f"""
Упс, с вашей транзакцией явно пошло не так:

{e}

Напишите @PeterZhizhin. Чтобы выйти в главное меню нажмите /start.
    """.strip(),
            reply_markup=InlineKeyboardMarkup(reply_buttons),
        )
        user_data["delete_keyboard_message_id"] = msg.message_id
        logging.exception(f"Error while querying SID:\n{traceback.format_exc()}")

        database_fns.persist_sid_data(
            sid=user_text,
            error_info=str(e),
            sid_data=None,
        )

        return await start(update, context)

    database_fns.persist_sid_data(
        sid=user_text,
        error_info=None,
        sid_data=sid_data,
    )

    if sid_data is None:
        msg = await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="""
Этот адрес транзакции не найден в базе данных Московского голосования.

Данные обновляются 1 раз в час. Попробуйте позже.
Если прошло много времени, а транзакции нет, то напишите @PeterZhizhin.

Введите другой SID или нажмите кнопку чтобы выйти в меню.
    """.strip(),
            reply_markup=InlineKeyboardMarkup(reply_buttons),
        )
        user_data["delete_keyboard_message_id"] = msg.message_id

        return MOSCOW_ASKED_FOR_SID

    sid_data_formatted = sid_data.human_readable()

    reply_buttons.append(
        [
            InlineKeyboardButton(
                "Что за поле data?",
                callback_data="moscow_what_is_data_field",
            ),
        ]
    )

    msg = await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=f"""
{sid_data_formatted}

Что-то не так? Напишите @PeterZhizhin.

Пришлите ещё один адрес транзакции или нажмите кнопку чтобы выйти в меню.
""".strip(),
        reply_markup=InlineKeyboardMarkup(reply_buttons),
    )
    user_data["delete_keyboard_message_id"] = msg.message_id

    return MOSCOW_ASKED_FOR_SID


async def moscow_what_is_data_field_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> int:
    query = update.callback_query
    assert query is not None
    assert update.effective_chat is not None

    await query.answer()

    await query.edit_message_reply_markup(reply_markup=None)

    reply_buttons = [[InlineKeyboardButton("В главное меню", callback_data="back")]]

    msg = await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="""
В этом поле по-идее должен храниться ваш зашифрованный голос.

Достоверно проверить, так это или нет - невозможно.

Когда вы голосуете, голос шифруется первый раз у вас в браузере ключом, который делят на много частей и который в момент подсчёта публикуют в базе данных голосования.
Далее разработчики шифруют голос второй раз, уже с использованием ключа, доступного только ДИТ Москвы.

Из-за этого в этой системе невозможно независимо подвести итоги.

Разработчики называют "транспортным шифрованием".

Такой механизм упрощает любые фальсификации: так как независимо расшифровать голоса невозможно, то и проверить, что расшифровку не подменили тоже не получится.

Введите ещё один SID или нажмите кнопку чтобы выйти в меню.
""".strip(),
        reply_markup=InlineKeyboardMarkup(reply_buttons),
    )
    user_data = context.user_data or {}
    user_data["delete_keyboard_message_id"] = msg.message_id

    return MOSCOW_ASKED_FOR_SID


async def moscow_did_not_check_sid(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> int:
    query = update.callback_query
    assert query is not None
    assert update.effective_chat is not None

    await query.answer()

    await query.edit_message_reply_markup(reply_markup=None)

    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="""
Если вы проголосовали через в ДЭГ через Интернет или на участке через терминал, но не поставили галочку, то проверить голос не получится.

Более того, голос очень легко могут подменить. Однако мы не знаем, будут ли они это делать. Но, на всякий случай, считайте, что вы проголосовали за Путина.

Расскажите о галочке проверки своего голоса своим друзьям и знакомым.
""".strip(),
        reply_markup=InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        "Информация", callback_data="did_not_check_get_info"
                    )
                ],
            ]
        ),
    )

    return MOSCOW_ASKED_IF_CHECKED_SID


async def ask_for_info_options(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> int:
    query = update.callback_query
    assert query is not None
    assert update.effective_chat is not None

    await query.answer()

    await query.edit_message_reply_markup(reply_markup=None)
    await _send_delimiter(update, context)

    reply_markup = InlineKeyboardMarkup(_get_info_keyboard())

    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="Выбирите пункт меню:",
        reply_markup=reply_markup,
    )

    return ASKED_FOR_INFO_OPTIONS


async def menu_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    data_override: str | None = None,
) -> int:
    query = update.callback_query
    assert query is not None
    assert update.effective_chat is not None

    await query.answer()

    await query.edit_message_reply_markup(reply_markup=None)
    await _send_delimiter(update, context)

    query_data = query.data if data_override is None else data_override

    # Send new message with information based on the button pressed
    if query_data == "back":
        return await start(update, context)
    if query_data in [
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
        }.get(query_data, [])

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

Отправьте фотографию заполненного бюллетеня в бот наших коллег: @dobrostatbot. Они ведут независимый подсчёт бумажных бюллетеней.

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
        }[query_data]

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

        return ASKED_FOR_INFO_OPTIONS

    return await start(update, context)


def main() -> None:
    application = Application.builder().token(config.BOT_TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            MENU: [
                CallbackQueryHandler(ask_for_info_options, pattern="^info$"),
                CallbackQueryHandler(
                    moscow_check_sid_handler, pattern="^moscow_check_sid$"
                ),
                CallbackQueryHandler(
                    redirect_to_dobrostat, pattern="^voting_in_person_redirect$"
                ),
            ],
            ASKED_FOR_INFO_OPTIONS: [
                CallbackQueryHandler(start, pattern="^back$"),
                CallbackQueryHandler(menu_handler),
            ],
            MOSCOW_ASKED_IF_CHECKED_SID: [
                CallbackQueryHandler(start, pattern="^back$"),
                CallbackQueryHandler(moscow_did_not_check_sid, pattern="^no$"),
                CallbackQueryHandler(
                    functools.partial(
                        menu_handler, data_override="voting_in_moscow_deg"
                    ),
                    pattern="did_not_check_get_info",
                ),
                CallbackQueryHandler(moscow_yes_i_checked_sid, pattern="^yes$"),
            ],
            MOSCOW_ASKED_FOR_SID: [
                MessageHandler(filters.TEXT, moscow_sid_message_handler),
                CallbackQueryHandler(start, pattern="^back$"),
                CallbackQueryHandler(
                    moscow_what_is_data_field_handler,
                    pattern="moscow_what_is_data_field",
                ),
            ],
        },
        fallbacks=[CommandHandler("start", start)],
    )

    application.add_handler(conv_handler)
    application.add_handler(MessageHandler(filters.PHOTO, photo_message_handler))

    application.run_polling()


if __name__ == "__main__":
    main()
