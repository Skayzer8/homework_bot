import logging
import os
import time
from http import HTTPStatus

import requests
import telegram
from dotenv import load_dotenv

load_dotenv()
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s, %(funcName)s, %(levelname)s, %(message)s',
    handlers=[logging.FileHandler(
        'main.log',
        mode='w',
        encoding='UTF-8'),
        logging.StreamHandler()])

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_TIME = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_STATUSES = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}


def send_message(bot, message):
    """Отправка ботом сообщения пользователю со статусом работы."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logger.info('Сообщение в чат {TELEGRAM_CHAT_ID}: {message}')
    except Exception:
        logger.error('Сообщение в телеграм не отправилось')


def get_api_answer(current_timestamp):
    """
    Получение ответа от API. Параметр - временная метка.
    Возвращает ответ API, преобразовав его из формата JSON
    к типам данных Python.
    """
    timestamp = 0
    # current_timestamp
    params = {'from_date': timestamp}
    try:
        homework_statuses = requests.get(
            ENDPOINT,
            headers=HEADERS,
            params=params
        )
    except Exception as error:
        logging.error(f'Ошибка запроса к  API: {error}')
        raise Exception(f'Ошибка запроса к  API: {error}')
    if homework_statuses.status_code != HTTPStatus.OK:
        status_code = homework_statuses.status_code
        logging.error(f'Ошибка доступности  API: {status_code}')
        raise Exception(f'Ошибка доступности  API: {status_code}')
    return homework_statuses.json()


def check_response(response):
    """
    Проверка ответа API на корректность.
    Функция должна вернуть, список домашних работ (может быть и пустым),
    доступный в ответе API по ключу 'homeworks'.
    """
    if type(response) is not dict:
        raise TypeError('Ответ API не является словарем')
    try:
        homeworks_set = response['homeworks']
    except KeyError:
        logger.error('По ключу homeworks в словаре ничего не найдено')
        raise KeyError('По ключу homeworks в словаре ничего не найдено')
    try:
        homework = homeworks_set[0]
    except IndexError:
        logger.error('На данный момент нет домашних работ на проверке')
        raise IndexError('На данный момент нет домашних работ на проверке')
    return homework


def parse_status(homework):
    """
    Извлекает из информации о  домашней работе статус этой работы.
    В качестве параметра  получает  один элемент из списка домашних работ,
    Возвращает строку, содержащую  один из вердиктов  HOMEWORK_STATUSES.
    """
    if 'homework_name' not in homework:
        raise KeyError('Не найден ключ "homework_name" в ответе от сервера')
    if 'status' not in homework:
        raise Exception('Не найден ключ "status" в ответе от сервера')
    homework_name = homework['homework_name']
    homework_status = homework['status']
    if homework_status not in HOMEWORK_STATUSES:
        raise Exception(f'Недокументированный статус работы:{homework_status}')
    verdict = HOMEWORK_STATUSES[homework_status]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def check_tokens():
    """
    Проверка наличия токенов.
    Если отсутствует хотя бы одна переменная  окружения —
    функция должна вернуть False, иначе — True.
    """
    if all([PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID]):
        return True


def main():
    """Основная логика работы бота."""
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    current_timestamp = int(time.time())
    new_error_message = ''
    new_message = ''
    if not check_tokens():
        logger.critical('Проверка наличия токенов провалена')
        raise Exception('Проверка наличия токенов провалена')
    while True:
        try:
            response = get_api_answer(current_timestamp)
            current_timestamp = response.get('current_date')
            homework = check_response(response)
            message = parse_status(homework)
            if message != new_message:
                send_message(bot, message)
                new_message = message
                time.sleep(RETRY_TIME)
        except Exception as error:
            logger.error(error)
            error_message = str(error)
            if error_message != new_error_message:
                send_message(bot, error_message)
                new_error_message = error_message
        time.sleep(RETRY_TIME)


if __name__ == '__main__':
    main()
