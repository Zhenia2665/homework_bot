import os
import sys
import logging
import time
from http import HTTPStatus
import telegram
import requests
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
        message = 'Важное сообщение'
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logger.debug(f'Сообщение отправлено: {message}')
    except telegram.TelegramError as error:
        print('Сообщение не отправлено')
        logging.error(error)


def get_api_answer(timestamp):
    """Выполняет запрос к API."""
    current_timestamp = int(time.time())
    timestamp = current_timestamp or int(time.time())
    params = dict(
        url=ENDPOINT,
        headers=HEADERS,
        params={'from_date': timestamp}
    )
    try:
        logger.info('Запрос к API')
        homework_statuses = requests.get(**params)
    except Exception as error:
        logger.error(f'Ошибка при запросе к API: {error}')
    try:
        if homework_statuses.status_code != HTTPStatus.OK:
            error_message = 'Статус страницы не равен 200'
            raise requests.HTTPError(error_message)
        return homework_statuses.json()
    except ValueError:
        logger.error('Ошибка парсинга ответа из формата json')
        raise ValueError('Ошибка парсинга ответа из формата json')


def check_response(response):
    """Проверяет полученный ответ."""
    logger.info('Ответ от сервера получен')
    try:
        homeworks_response = response['homeworks']
        logger.info('Список домашних работ получен')
    except KeyError:
        logger.error('Ключ "homeworks" отсутствует в словаре')
        raise KeyError('Ключ "homeworks" отсутствует в словаре')
    if not homeworks_response:
        message_status = ('Отсутствует статус homeworks')
        raise KeyError(message_status)
    elif not isinstance(homeworks_response, list):
        message_list = ('Неверный тип входящих данных')
        raise TypeError(message_list)
    elif 'current_date' not in response.keys():
        message_current_date = ('Ключ "current_date" отсутствует в словаре')
        raise KeyError(message_current_date)
    return homeworks_response


def parse_status(homework):
    """Извлекает статус домашней работы."""
    try:
        homework_name = homework.get('homework_name')
        homework_status = homework.get('status')
        verdict = HOMEWORK_VERDICTS[homework_status]
    except KeyError:
        logger.error('Такого названия не существует')
        raise KeyError('Такого названия не существует')
    if not verdict:
        message_verdict = 'Такого статуса нет в словаре'
        raise KeyError(message_verdict)
    elif homework_status not in HOMEWORK_VERDICTS:
        message_homework_status = 'Такого статуса не существует'
        raise KeyError(message_homework_status)
    elif not homework_status:
        message_status = ('Отсутствует статус homeworks')
        raise KeyError(message_status)
    elif not homework_name:
        message_verdict = 'Нет имени работы homework_name'
        raise KeyError(message_verdict)
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
        else:
            logger.error('Сбой, ошибка не найдена')
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
