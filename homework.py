import os
import sys
import logging
import time
from http import HTTPStatus
from json.decoder import JSONDecodeError

import requests
import telegram
from dotenv import load_dotenv

load_dotenv()


PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}

logger = logging.getLogger(__name__)
logger.addHandler(logging.StreamHandler(sys.stdout))


def check_tokens(TELEGRAM_TOKEN):
    """Проверяет наличие всех токенов."""
    return all([TELEGRAM_TOKEN, PRACTICUM_TOKEN, TELEGRAM_CHAT_ID])


def send_message(bot, message):
    """Отправляет сообщение в tg."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logger.debug(f'Сообщение отправлено: {message}')
    except telegram.TelegramError as error:
        logger.error(f'Сообщение не отправлено: {error}')


def get_api_answer(timestamp):
    """Делает запрос к API проверки домашних работ Яндекс-Практикума.
    Возвращает  ответ , приведя его из формата JSON к типам данных Python.
    """
    logger.debug('Получаем информацию от API')
    try:
        homework_statuses = requests.get(
            ENDPOINT,
            headers=HEADERS,
            params={'from_date': timestamp}
        )
    except requests.RequestException as error:
        error_message = (f'По запросу {homework_statuses.url}'
                         f'API недоступен {error}')
        raise requests.RequestException(error_message)
    if homework_statuses.status_code != HTTPStatus.OK:
        raise requests.HTTPError(
            f'На запрос {homework_statuses.url} '
            f'API вернул ответ {homework_statuses.status_code}')
    try:
        return homework_statuses.json()
    except JSONDecodeError as Exception:
        message = 'При декодировании ответа со статусами домашних работ'\
                  'произошла ошибка.'
        raise Exception(message)


def check_response(response):
    """Проверяет полученный ответ."""
    logger.info('Ответ от сервера получен')
    try:
        homeworks_response = response['homeworks']
        logger.info('Список домашних работ получен')
    except KeyError:
        raise KeyError('Ошибка в получении статуса работ')
    if 'homeworks' not in response:
        message_status = ('В ответе API нет ключа "homeworks"')
        raise KeyError(message_status)
    elif not isinstance(homeworks_response, list):
        message_list = ('Неверный тип входящих данных')
        raise TypeError(message_list)
    elif 'current_date' not in response:
        message_current_date = ('Ключ "current_date" отсутствует в словаре')
        raise KeyError(message_current_date)
    return homeworks_response


def parse_status(homework: dict) -> str:
    """Извлекает статус работы из ответа ЯндексПракутикум."""
    logger.info("Извлекаем информацию о домашней работе")
    homework_name = homework.get('homework_name')
    homework_status = homework.get('status')
    if homework_name is None:
        raise KeyError(
            'В ответе API отсутствует ожидаемый ключ "homework_name".'
        )
    if homework_status is None:
        error_message = 'Ошибка извлечение статуса работы "status".'
        raise KeyError(error_message)
    verdict = HOMEWORK_VERDICTS.get(homework_status)
    if verdict is None:
        message = 'Обнаружен недокументированный статус домашней работы '
        raise error_message(message)

    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    current_timestamp = int(time.time())
    if not check_tokens(TELEGRAM_TOKEN):
        logger.critical('Ошибка в получении токенов!')
        sys.exit()
    current_report = {}
    prev_report = {}
    while True:
        try:
            response = get_api_answer(current_timestamp)
            homework = check_response(response)[0]
            if homework:
                message = parse_status(homework)
                current_report[response.get(
                    'homework_name')] = response.get('status')
                if current_report != prev_report:
                    send_message(bot, message)
                    prev_report = current_report.copy()
                    current_report[response.get(
                        'homework_name')] = response.get('status')
            current_timestamp = response.get('current_date')
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logger.error(message)
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    logging.basicConfig(
        format=('%(asctime)s'
                '%(name)s'
                '%(levelname)s'
                '%(message)s'
                '%(funcName)s'
                '%(lineno)d'),
        level=logging.INFO,
        filename='program.log',
        filemode='w',
    )
    main()
