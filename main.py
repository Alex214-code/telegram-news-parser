import linecache
import random
import sys
from ollama import Client
import ollama
import time
from pathlib import Path

import telebot
from telebot import types  # для указание типов
import config
from vosk_tts import Model, Synth
import psycopg2

from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options

import h_chat
import login_details
from h_chat import HuggingChat
from datetime import datetime

import requests
import datetime


class DBHelper:
    def __init__(self, name_of_database: str):
        self.__name_of_database = name_of_database

        # Подключаемся к базе данных
        self.__conn = psycopg2.connect(
            dbname=self.get_name_of_database(), user='postgres',
            password=login_details.DATABASE_PASSWD,
            host='localhost'
        )
        self.__cursor = self.__conn.cursor()

    def get_name_of_database(self):
        return self.__name_of_database

    def get_conn(self):
        return self.__conn

    def get_cursor(self):
        return self.__cursor

    def get_data_from_table(
            self,
            table_name: str,
            where_query: str = None,
            order_query: str = None,
            limit_query: str = 'ALL'
    ):
        if where_query is None:
            tmp_cmd = \
                f"""
                SELECT * FROM {table_name}
                    order by {order_query} desc
                    limit {limit_query}; 
                """
            self.get_cursor().execute(tmp_cmd)

        if where_query is not None:
            tmp_cmd = \
                f"""
                SELECT * FROM {table_name}
                    where {where_query}
                    order by {order_query} desc
                    limit {limit_query};
                """
            self.get_cursor().execute(tmp_cmd)

        return self.get_cursor().fetchall()

    def drop_table(self, table_name: str):
        self.get_cursor().execute(
            f"""
            DROP TABLE IF EXISTS {table_name};
            """
        )
        self.get_conn().commit()


class LentaParser:
    def __init__(self):
        self.__debugging_mode_flag = True
        self.__options_of_webdriver = Options()

        self.__url = ''
        self.__city = ''
        self.__date = ''
        self.__name_of_rubric = ''
        self.__num_of_rubric = ''
        self.__base_url = "https://lenta.ru"
        self.__news_container = []
        self.__dictionaries_of_news = []
        self.__news_dates = []
        self.__news_times = []
        self.__news_descriptions = []
        self.__dict_of_rubrics = {}
        self.__soup = BeautifulSoup()
        self.__driver = None

        self.__name_of_database = 'jarvis'
        self.__jarvis_database = DBHelper(self.get_name_of_database())

    def set_city(self, city: str):
        self.__city = city

    def get_city(self):
        return self.__city

    def set_date(self, date: str):
        self.__date = date

    def get_date(self):
        return self.__date

    def set_name_of_rubric(self, rubric_name: str):
        self.__name_of_rubric = rubric_name

    def get_name_of_rubric(self):
        return self.__name_of_rubric

    def set_num_of_rubric(self, rubric_num: str):
        self.__num_of_rubric = rubric_num

    def get_num_of_rubric(self):
        return self.__num_of_rubric

    def get_name_of_database(self):
        return self.__name_of_database

    def get_jarvis_database(self):
        return self.__jarvis_database

    def get_debugging_mode_flag(self):
        return self.__debugging_mode_flag

    def get_options(self):
        return self.__options_of_webdriver

    def get_options_of_webdriver(self):
        return self.__options_of_webdriver

    def get_news_dates(self):
        return self.__news_dates

    def get_news_times(self):
        return self.__news_times

    def add_element_to_news_container(self, elem: str):
        self.__news_container.append(elem)

    def get_news_container(self):
        return self.__news_container

    def add_element_to_dictionaries_of_news(self, elem: dict):
        self.__dictionaries_of_news.append(elem)

    def __clear_dictionaries_of_news(self):
        self.__dictionaries_of_news = []

    def get_dictionaries_of_news(self):
        return self.__dictionaries_of_news

    def get_news_descriptions(self):
        return self.__news_descriptions

    def __set_url(self):
        self.__url = \
            f"""
            https://lenta.ru/search?query={self.get_city()}#size=10|sort=2|domain=1|modified,format=yyyy-MM-dd|type=1|modified,from={self.get_date()}|modified,to={self.get_date()}|bloc={self.get_num_of_rubric()}
            """

    def get_url(self):
        self.__set_url()
        return self.__url

    def get_base_url(self):
        return self.__base_url

    def __get_driver(self):
        return self.__driver

    def close_driver(self):
        self.__get_driver().quit()

    def set_soup(self, elem: str, features: str):
        self.__soup = BeautifulSoup(elem, features)

    def get_soup(self):
        return self.__soup

    @staticmethod
    def get_current_time():
        sec_utc = time.time()

        # переводим из секунд в 'struct_time'
        time_local = time.localtime(sec_utc)

        # получаем форматированную строку из 'struct_time'
        current_time = time.strftime('%H:%M', time_local)
        return current_time

    @staticmethod
    def get_converted_date(str_date: str):
        # Словарь месяцев для перевода названия месяца в его номер
        months = {
            "января": "01", "февраля": "02", "марта": "03",
            "апреля": "04", "мая": "05", "июня": "06",
            "июля": "07", "августа": "08", "сентября": "09",
            "октября": "10", "ноября": "11", "декабря": "12"
        }

        # Разбор строки
        parts = str_date.split()

        # Получение дня, месяца и года
        day = parts[0]
        month = months[parts[1]]
        year = parts[2]

        # Создание объекта datetime
        dt = datetime.datetime(year=int(year), month=int(month), day=int(day))

        # Форматирование даты в нужный формат
        formatted_date = dt.strftime('%Y-%m-%d')
        return formatted_date

    @property
    def __is_show_more_button_exist(self):
        try:
            self.__get_driver().find_element(
                By.XPATH,
                """
                /html/body/div[3]/div[3]/main/div[2]/section/div[1]/ul/li[11]/div/button
                """)
            return True
        except:
            return False

    def __check_show_subscribe_box(self):
        try:
            self.__get_driver().find_element(
                By.XPATH,
                """
                /html/body/div[6]/div
                """)
            button_cancel = self.__get_driver().find_element(
                By.XPATH,
                """
                /html/body/div[6]/div/div[3]/button[1]
                """)
            button_cancel.click()
        except:
            pass

    def __check_news_on_page(self):
        try:
            tmp_elem = self.__get_driver().find_element(
                By.XPATH,
                """
                /html/body/div[3]/div[3]/main/div[2]/section/div[3]/h4
                """)
        except:
            raise Exception('news_not_found_on_page')

        if tmp_elem.text == 'Нет результатов':
            raise Exception('news_not_found_on_page')

    def __init_driver(self):
        self.__options_of_webdriver.add_argument(
            "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/90.0.4430.93 Safari/537.36"
        )
        self.__options_of_webdriver.add_argument(
            "user-data-dir=C:\\Users\\morea\\Local Settings\\Application Data\\Google\\Chrome\\User Data\\Jarvis"
        )
        self.__options_of_webdriver.add_argument(
            '--disable-blink-features=AutomationControlled'
        )
        self.__options_of_webdriver.add_argument("--disable-infobars")
        self.__options_of_webdriver.add_argument("--start-maximized")
        self.__options_of_webdriver.add_argument("window-size=1000,800")
        self.__options_of_webdriver.add_experimental_option('useAutomationExtension', False)

        if not self.get_debugging_mode_flag():
            self.__options_of_webdriver.add_argument('--headless')
            self.__driver = webdriver.Chrome(
                options=self.get_options_of_webdriver()
            )
        else:
            self.__driver = webdriver.Chrome(
                options=self.get_options_of_webdriver()
            )
        self.__driver.set_page_load_timeout(6)

    def __init_dict_of_rubrics(self):
        # Открываем сайт
        self.__init_driver()

        try:
            self.__get_driver().get(
                "https://lenta.ru/search?query=Снежинск#size=10|sort=2|domain=1|modified,format=yyyy-MM-dd")
        except:
            self.__get_driver().execute_script("window.stop();")

        filter_button = self.__get_driver().find_element(
            By.XPATH,
            '/html/body/div[3]/div[3]/main/div[2]/form/div[2]/div[3]/div/button'
        )
        filter_button.click()

        all_categories_button = self.__get_driver().find_element(
            By.XPATH,
            '/html/body/div[3]/div[3]/main/div[2]/form/div[2]/div[2]/div[1]/div[2]/button'
        )
        all_categories_button.click()

        category_list = self.__get_driver().find_element(
            By.CSS_SELECTOR,
            'ul.search-page__filter-list.js-search-rubric-filter'
        )

        # Находим все элементы списка и составляем словарь
        categories_elements = category_list.find_elements(By.CLASS_NAME, 'search-page__filter-item')

        categories_dict = {}
        for category_element in categories_elements:
            category_name = category_element.text
            category_id = category_element.get_attribute('data-id')
            if category_id:  # Проверка, так как "Все рубрики" не имеет data-id
                categories_dict[category_name] = category_id

        # Выводим наш словарь на экране
        self.__dict_of_rubrics = categories_dict
        self.close_driver()

    def get_dict_of_rubrics(self):
        self.__init_dict_of_rubrics()
        return self.__dict_of_rubrics

    def __scrap_html(self):
        self.__init_driver()
        try:
            self.__get_driver().get(self.get_url())
        except:
            self.__get_driver().execute_script("window.stop();")

        self.__check_news_on_page()

        while self.__is_show_more_button_exist:
            button = self.__get_driver().find_element(
                By.XPATH,
                """
                /html/body/div[3]/div[3]/main/div[2]/section/div[1]/ul/li[11]/div/button
                """)
            # Скроллим вниз страницы до кнопки
            self.__get_driver().execute_script(
                "arguments[0].scrollIntoView();",
                button
            )
            button.click()
            time.sleep(2)  # Небольшая задержка после клика

        tmp_container_xpath = '/html/body/div[3]/div[3]/main/div[2]/section/div[1]'
        tmp_elements = self.__get_driver().find_elements(
            By.XPATH,
            f"{tmp_container_xpath}"
        )

        for elem in tmp_elements:
            self.add_element_to_news_container(elem.get_attribute('outerHTML'))

    def __scrap_news_elements(self):
        for elem in self.get_news_container():
            self.set_soup(elem, 'html.parser')

            # Поиск всех элементов списка в новостях
            tmp_news_items = self.get_soup().find_all(
                'li',
                class_="search-results__item _news"
            )

            # Собираем информацию по каждой новости
            if tmp_news_items:
                for tmp_item in tmp_news_items:
                    tmp_title = tmp_item.find('h3', class_="card-full-news__title").get_text(
                        strip=True
                    )
                    tmp_rubric = tmp_item.find(
                        'span',
                        class_="card-full-other__info-item card-full-other__rubric"
                    ).get_text(strip=True)
                    tmp_href = tmp_item.find('a')['href']
                    tmp_full_url = self.get_base_url() + tmp_href

                    # print(tmp_title)
                    # print(tmp_rubric)
                    # print(tmp_full_url)
                    self.add_element_to_dictionaries_of_news(
                        {
                            'title': tmp_title,
                            'rubric': tmp_rubric,
                            'link': tmp_full_url
                        }
                    )

    @staticmethod
    def get_differences_between_two_time(time_1, time_2):
        # Преобразование строк в объекты datetime
        datetime1 = datetime.datetime.strptime(time_1, "%H:%M")
        datetime2 = datetime.datetime.strptime(time_2, "%H:%M")

        # Вычисление разницы
        time_difference = datetime1 - datetime2

        # Преобразование разницы в часы
        hours = time_difference.seconds // 3600
        return hours

    @staticmethod
    def normalize_text(text: str):
        text = text.replace('»', '» ')
        text = text.replace('»  ', '» ')
        text = text.replace(' , ', ', ')
        text = text.replace('( ', '(')
        text = text.replace('?', '? ')
        text = text.replace('\n', ' ')

        return text

    def __scrap_news_data(self):
        for part_of_news in self.get_dictionaries_of_news():
            try:
                self.__get_driver().get(part_of_news['link'])
            except:
                self.__get_driver().execute_script("window.stop();")

            # Найти все элементы в контейнере с конкретной XPath
            try:
                tmp_container_of_news_datetime = self.__get_driver().find_element(
                    By.XPATH,
                    """
                    /html/body/div[3]/div[3]/main/div[2]/div[3]/div[1]/div[1]/div/div/div[1]/a[1]
                    """
                )
            except:
                tmp_container_of_news_datetime = self.__get_driver().find_element(
                    By.XPATH,
                    """
                    /html/body/div[4]/div[3]/main/div[2]/div[3]/div[1]/div[1]/div/div/div[1]/a[1]
                    """
                )

            self.get_news_times().append(tmp_container_of_news_datetime.text[:5])
            self.get_news_dates().append(self.get_converted_date(tmp_container_of_news_datetime.text[7:]))

            try:
                tmp_container_of_news_descriptions = self.__get_driver().find_element(
                    By.XPATH,
                    """
                    /html/body/div[3]/div[3]/main/div[2]/div[3]/div[1]/div[2]/div[1]/div[3]
                    """
                )
            except:
                try:
                    tmp_container_of_news_descriptions = self.__get_driver().find_element(
                        By.XPATH,
                        """
                        /html/body/div[3]/div[3]/main/div[2]/div[3]/div[1]/div[2]/div[1]/div[2]
                        """
                    )
                except:
                    tmp_container_of_news_descriptions = self.__get_driver().find_element(
                        By.XPATH,
                        """
                        /html/body/div[4]/div[3]/main/div[2]/div[3]/div[1]/div[2]/div[1]/div[3]
                        """
                    )

            self.get_news_descriptions().append(
                self.normalize_text(
                    tmp_container_of_news_descriptions.text
                )
            )

    def __parse_news(self):
        # self.__clear_dictionaries_of_news()
        self.__scrap_html()
        self.__scrap_news_elements()
        self.__scrap_news_data()

        for index in range(len(self.get_dictionaries_of_news())):
            self.get_dictionaries_of_news()[index]['date'] = self.get_news_dates()[index]
            self.get_dictionaries_of_news()[index]['time'] = self.get_news_times()[index]
            self.get_dictionaries_of_news()[index]['description'] = self.get_news_descriptions()[index]
            self.get_dictionaries_of_news()[index]['city'] = self.get_city()

    def get_parsed_news(self):
        self.__parse_news()
        return self.get_dictionaries_of_news()

    def create_news_table_of_jarvis_database(self):
        tmp_cmd = """
            CREATE TABLE IF NOT EXISTS News (
            id SERIAL NOT NULL, 
            title varchar(300), 
            rubric varchar(50), 
            link varchar(300),
            date varchar(20),
            time varchar(20),
            description varchar,
            city varchar,
            CONSTRAINT "news_pk" PRIMARY KEY (id)
            );
            """
        self.get_jarvis_database().get_cursor().execute(
            tmp_cmd
        )
        self.get_jarvis_database().get_conn().commit()

    def __insert_parsed_news_into_news_database(self):
        tmp_data_from_table = self.get_jarvis_database().get_data_from_table(
            'news',
            f"""(rubric = '{self.get_name_of_rubric()}') and (date = '{self.get_date()}') and (city = '{self.get_city()}')""",
            order_query=f"time"
        )

        is_news_in_table = False
        for tmp_news in self.get_parsed_news():
            for row in tmp_data_from_table:
                if tmp_news['title'] == row[1] and tmp_news['rubric'] == row[2] and tmp_news['date'] == row[4] and tmp_news['city'] == row[7]:
                    is_news_in_table = True
            if not is_news_in_table:
                tmp_cmd = \
                    f"""
                    INSERT INTO news (
                        title, rubric, link, date, time, description, city
                    )
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """
                self.get_jarvis_database().get_cursor().execute(
                    tmp_cmd,
                    (
                        tmp_news['title'],
                        tmp_news['rubric'],
                        tmp_news['link'],
                        tmp_news['date'],
                        tmp_news['time'],
                        tmp_news['description'],
                        tmp_news['city']
                    )
                )
                self.get_jarvis_database().get_conn().commit()
        # self.__clear_dictionaries_of_news()
        self.close_driver()

    def get_data_from_table(self):
        self.__insert_parsed_news_into_news_database()

        tmp_data_from_table = self.get_jarvis_database().get_data_from_table(
            'news',
            f"""(rubric = '{self.get_name_of_rubric()}') and (date = '{self.get_date()}') and (city = '{self.get_city()}')""",
            order_query="time"
        )

        return tmp_data_from_table


class WeatherParser:
    def __init__(
            self,
            name_of_database: str = 'jarvis'
    ):
        self.__weather_api_key = '985bebf438186a073b81fa2c8a75732b'
        self.__city = ''
        self.__city_id = None
        self.__date = ''

        self.__weather_data = {}
        self.__weather_info = {}

        self.__name_of_database = name_of_database
        self.__jarvis_database = DBHelper(self.get_name_of_database())

    def get_name_of_database(self):
        return self.__name_of_database

    def get_jarvis_database(self):
        return self.__jarvis_database

    def set_city(self, city: str):
        self.__city = city

    def get_city(self):
        return self.__city

    def __get_city_id(self):
        try:
            tmp_res = requests.get(
                "https://api.openweathermap.org/data/2.5/find",
                params={
                    'q': self.get_city(),
                    'type': 'like',
                    'units': 'metric',
                    'APPID': self.get_weather_api_key()
                }
            )
            self.__city_id = tmp_res.json()['list'][0]['id']
            return self.__city_id
        except Exception as e:
            print("Exception (find):", e)
            pass

    def get_weather_api_key(self):
        return self.__weather_api_key

    def __init_json_data(self):
        self.__json_data = requests.get(
            "https://api.openweathermap.org/data/2.5/weather",
            params={
                'id': self.__get_city_id(),
                'units': 'metric',
                'lang': 'ru',
                'APPID': self.get_weather_api_key()
            }
        )

    def get_json_data(self):
        self.__init_json_data()
        return self.__json_data

    def __parse_weather_data(self):
        self.__weather_data = self.get_json_data().json()

    def get_weather_data(self):
        self.__parse_weather_data()
        return self.__weather_data

    def set_date(self, date: str):
        self.__date = date

    def get_date(self):
        return self.__date

    def __init_weather_info(self):
        if self.get_weather_data():
            self.__weather_info['city'] = self.get_weather_data()['name']
            self.__weather_info['date'] = self.get_date()
            self.__weather_info['weather_description'] = self.get_weather_data()['weather'][0]['description']
            self.__weather_info['temperature_celsius'] = round(
                self.get_weather_data()['main']['temp']
            )

            self.__weather_info['feels_like'] = round(
                self.get_weather_data()['main']['feels_like']
            )

            self.__weather_info['min_day_temperature_celsius'] = round(
                self.get_weather_data()['main']['temp_min']
            )

            self.__weather_info['max_day_temperature_celsius'] = round(
                self.get_weather_data()['main']['temp_max']
            )

            self.__weather_info['wind_speed__meter_per_second'] = self.get_weather_data()['wind']['speed']

    def __get_weather_info(self):
        self.__init_weather_info()
        return self.__weather_info

    def create_weather_table_of_jarvis_database(self):
        tmp_cmd = """
            CREATE TABLE IF NOT EXISTS weather (
                id SERIAL NOT NULL,
                city varchar(50),
                date varchar(50),
                weather_description varchar(200),
                temperature_celsius varchar(200),
                feels_like varchar(200),
                min_day_temperature_celsius varchar(200),
                max_day_temperature_celsius varchar(200),
                wind_speed__meter_per_second varchar(200),
                CONSTRAINT "weather_pk" PRIMARY KEY (id)
                );
            """
        self.get_jarvis_database().get_cursor().execute(
            tmp_cmd
        )
        self.get_jarvis_database().get_conn().commit()

    def __insert_parsed_weather_into_news_database(self):
        tmp_data_from_table = self.get_jarvis_database().get_data_from_table(
            "weather",
            f"(city = '{self.get_city()}') and (date = '{self.get_date()}')",
            order_query='date'
        )

        tmp_cmd = \
            f"""
            INSERT INTO weather (
                city, 
                date, 
                weather_description,
                temperature_celsius,
                feels_like,
                min_day_temperature_celsius,
                max_day_temperature_celsius,
                wind_speed__meter_per_second
            )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s);
            """

        self.get_jarvis_database().get_cursor().execute(
            tmp_cmd,
            (
                self.__get_weather_info()['city'],
                self.__get_weather_info()['date'],
                self.__get_weather_info()['weather_description'],
                self.__get_weather_info()['temperature_celsius'],
                self.__get_weather_info()['feels_like'],
                self.__get_weather_info()['min_day_temperature_celsius'],
                self.__get_weather_info()['max_day_temperature_celsius'],
                self.__get_weather_info()['wind_speed__meter_per_second']
            )
        )
        self.get_jarvis_database().get_conn().commit()

        is_weather_in_table = False
        for tmp_weather in [self.__get_weather_info()]:
            for row in tmp_data_from_table:
                if tmp_weather['city'] == row[1] and tmp_weather['date'] == row[2]:
                    is_weather_in_table = True
            if not is_weather_in_table:
                self.get_jarvis_database().get_cursor().execute(
                    tmp_cmd,
                    (
                        self.__get_weather_info()['city'],
                        self.__get_weather_info()['date'],
                        self.__get_weather_info()['weather_description'],
                        self.__get_weather_info()['temperature_celsius'],
                        self.__get_weather_info()['feels_like'],
                        self.__get_weather_info()['min_day_temperature_celsius'],
                        self.__get_weather_info()['max_day_temperature_celsius'],
                        self.__get_weather_info()['wind_speed__meter_per_second']
                    )
                )
                self.get_jarvis_database().get_conn().commit()

    def get_data_from_table(self):
        tmp_data_from_table = self.get_jarvis_database().get_data_from_table(
            "weather",
            f"(city = '{self.get_city()}') and (date = '{self.get_date()}')",
            order_query='date'
        )
        if not tmp_data_from_table:
            self.__insert_parsed_weather_into_news_database()
            tmp_data_from_table = self.get_jarvis_database().get_data_from_table(
                "weather",
                f"(city = '{self.get_city()}') and (date = '{self.get_date()}')",
                order_query='date'
            )
            return tmp_data_from_table
        return tmp_data_from_table


class controller:
    def __init__(
            self,
            name_of_database: str = 'jarvis'
    ):
        self.__user_id = 0
        self.__first_name = ''
        self.__username = ''
        self.__name_of_database = name_of_database

        self.__lenta_parser = LentaParser()
        self.__weather_parser = WeatherParser()
        self.__hugging_chat = h_chat.HuggingChat(login_details.EMAIL, login_details.PASSWD)
        self.__synth = Synth(Model(model_name="vosk-model-tts-ru-0.6-multi"))

        self.__name_of_database = name_of_database
        self.__jarvis_database = DBHelper(self.get_name_of_database())

        self.__markup_dictionary = {}
        self.__current_markup = ''
        self.__rubric_name = ''
        self.__rubric_num = ''
        self.__date = ''
        self.__city = ''
        self.__reserved_message = ''

    def set_reserved_message(self, message: str):
        self.__reserved_message = message

    def get_reserved_message(self):
        return self.__reserved_message

    def get_hugging_chat(self):
        return self.__hugging_chat

    def get_synth(self):
        return self.__synth

    def set_current_markup(self, markup: str):
        self.__current_markup = markup

    def get_current_markup(self):
        return self.__current_markup

    def set_name_of_rubric(self, rubric_name: str):
        self.__rubric_name = rubric_name

    def get_name_of_rubric(self):
        return self.__rubric_name

    def set_num_of_rubric(self, rubric_num: str):
        self.__rubric_num = rubric_num

    def get_num_of_rubric(self):
        return self.__rubric_num

    def set_date(self, date: str):
        self.__date = date

    def get_date(self):
        return self.__date

    def set_city(self, city: str):
        self.__city = city

    def get_city(self):
        return self.__city

    def get_markup_dictionary(self):
        return self.__markup_dictionary

    def init_markup_dictionary(self):
        start_markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        btn1 = types.KeyboardButton("Посмотреть личный кабинет")
        btn2 = types.KeyboardButton("Узнать информацию о новостях")
        btn3 = types.KeyboardButton("Узнать информацию о погоде")
        btn4 = types.KeyboardButton("Дополнительный функционал")
        btn5 = types.KeyboardButton("❓ Задать вопрос")
        start_markup.add(btn1)
        start_markup.add(btn2)
        start_markup.add(btn3)
        start_markup.add(btn4)
        start_markup.add(btn5)
        self.get_markup_dictionary()['start_markup'] = start_markup

        personal_account_markup = types.ReplyKeyboardMarkup(
            resize_keyboard=True
        )
        change = types.KeyboardButton("Изменить тип вывода")
        back = types.KeyboardButton("Вернуться в главное меню")
        personal_account_markup.add(change)
        personal_account_markup.add(back)
        self.get_markup_dictionary()['personal_account_markup'] = personal_account_markup

        change_type_of_output_markup = types.ReplyKeyboardMarkup(
            resize_keyboard=True
        )
        btn_text = types.KeyboardButton("Текстовый формат вывода (text)")
        btn_voice = types.KeyboardButton("Звуковой формат вывода (voice)")
        back = types.KeyboardButton("Вернуться в главное меню")
        change_type_of_output_markup.add(btn_text)
        change_type_of_output_markup.add(btn_voice)
        change_type_of_output_markup.add(back)
        self.get_markup_dictionary()['change_type_of_output_markup'] = change_type_of_output_markup

        tell_news_markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        rubric_1 = types.KeyboardButton("1) Россия")
        rubric_2 = types.KeyboardButton("2) Мир")
        rubric_3 = types.KeyboardButton("3) Бывший СССР")
        rubric_4 = types.KeyboardButton("4) Экономика")
        rubric_5 = types.KeyboardButton("5) Силовые структуры")
        rubric_6 = types.KeyboardButton("6) Наука и техника")
        rubric_7 = types.KeyboardButton("7) Спорт")
        rubric_8 = types.KeyboardButton("8) Культура")
        rubric_9 = types.KeyboardButton("9) Интернет и СМИ")
        rubric_10 = types.KeyboardButton("10) Ценности")
        rubric_11 = types.KeyboardButton("11) Путешествия")
        rubric_12 = types.KeyboardButton("12) Из жизни")
        rubric_13 = types.KeyboardButton("13) Среда обитания")
        rubric_14 = types.KeyboardButton("14) 69-я параллель")
        rubric_15 = types.KeyboardButton("15) Моя страна")
        rubric_16 = types.KeyboardButton("16) Забота о себе")
        back = types.KeyboardButton("Вернуться в главное меню")
        tell_news_markup.add(rubric_1, rubric_2)
        tell_news_markup.add(rubric_3, rubric_4)
        tell_news_markup.add(rubric_5, rubric_6)
        tell_news_markup.add(rubric_7, rubric_8)
        tell_news_markup.add(rubric_9, rubric_10)
        tell_news_markup.add(rubric_11, rubric_12)
        tell_news_markup.add(rubric_13, rubric_14)
        tell_news_markup.add(rubric_15, rubric_16)
        tell_news_markup.add(back)
        self.get_markup_dictionary()['tell_news_markup'] = tell_news_markup

        back_to_main_menu_markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        back = types.KeyboardButton("Вернуться в главное меню")
        back_to_main_menu_markup.add(back)
        self.get_markup_dictionary()['back_to_main_menu_markup'] = back_to_main_menu_markup

        weather_advice_markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        weather_advice = types.KeyboardButton("Получить совет - как одеться в данную погоду")
        back = types.KeyboardButton("Вернуться в главное меню")
        weather_advice_markup.add(weather_advice)
        weather_advice_markup.add(back)
        self.get_markup_dictionary()['weather_advice_markup'] = weather_advice_markup

        extra_functions_markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        generate_image = types.KeyboardButton("Вывести изображение по промпту")
        # weather_advice = types.KeyboardButton("Вывести изображение по промпту")
        back = types.KeyboardButton("Вернуться в главное меню")
        extra_functions_markup.add(generate_image)
        extra_functions_markup.add(back)
        self.get_markup_dictionary()['extra_functions_markup'] = extra_functions_markup

        faq_markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        btn1 = types.KeyboardButton("Как меня зовут?")
        btn2 = types.KeyboardButton("Что я могу?")
        back = types.KeyboardButton("Вернуться в главное меню")
        faq_markup.add(btn1, btn2)
        faq_markup.add(back)
        self.get_markup_dictionary()['faq_markup'] = faq_markup

    def get_name_of_database(self):
        return self.__name_of_database

    def get_jarvis_database(self):
        return self.__jarvis_database

    def __set_lenta_parser(self):
        self.__lenta_parser.set_name_of_rubric(
            self.get_name_of_rubric()
        )
        self.__lenta_parser.set_num_of_rubric(
            self.get_num_of_rubric()
        )
        self.__lenta_parser.set_date(self.get_date())
        self.__lenta_parser.set_city(self.get_city())

    def get_lenta_parser(self):
        self.__set_lenta_parser()
        return self.__lenta_parser

    def __set_weather_parser(self):
        self.__weather_parser.set_date(self.get_date())
        self.__weather_parser.set_city(self.get_city())

    def get_weather_parser(self):
        self.__set_weather_parser()
        return self.__weather_parser

    def set_user_id(self, user_id: int):
        self.__user_id = user_id

    def get_user_id(self):
        return self.__user_id

    def set_username(self, username: str):
        self.__username = username

    def get_username(self):
        return self.__username

    def set_first_name(self, first_name: str):
        self.__first_name = first_name

    def get_first_name(self):
        return self.__first_name

    def create_user_database(self):
        tmp_cmd = """
        CREATE TABLE IF NOT EXISTS users (
            id int not null,
            first_name varchar,
            username varchar,
            selected_output varchar,
            count_of_requests int,
            date_of_the_last_message varchar,
            CONSTRAINT "user_pk" PRIMARY KEY (id)
        );
        """
        self.get_jarvis_database().get_cursor().execute(
            tmp_cmd
        )
        self.get_jarvis_database().get_conn().commit()

    def insert_new_user_into_user_database(self):
        tmp_data_from_user_table = self.get_jarvis_database().get_data_from_table(
            "users",
            f"id = {self.get_user_id()}",
            order_query="id"
        )

        if not tmp_data_from_user_table:
            tmp_cmd = \
                f"""
                INSERT INTO users (
                    id,
                    first_name, 
                    username,
                    selected_output,
                    count_of_requests,
                    date_of_the_last_message
                )
                    VALUES (%s, %s, %s, %s, %s, %s)
                """
            self.get_jarvis_database().get_cursor().execute(
                tmp_cmd,
                (
                    self.get_user_id(),
                    f'{self.get_first_name()}',
                    f'{self.get_username()}',
                    'text',
                    0,
                    f'{self.get_current_date()}'
                )
            )
            self.get_jarvis_database().get_conn().commit()

    def change_output(self, selected_output: str):
        tmp_cmd = \
            f"""
            UPDATE users
                SET selected_output = '{selected_output}'
                WHERE id = {self.get_user_id()};
            """
        self.get_jarvis_database().get_cursor().execute(
            tmp_cmd
        )
        self.get_jarvis_database().get_conn().commit()

    def update_visit_date(self):
        data_from_user_table = self.get_jarvis_database().get_data_from_table(
            'users',
            f'id = {self.get_user_id()}',
            f'id'
        )

        if self.get_current_date() != data_from_user_table[0][5]:
            tmp_cmd = \
                f"""
                UPDATE users
                    SET date_of_the_last_message = '{self.get_current_date()}'
                    WHERE id = {self.get_user_id()};
                """
            self.get_jarvis_database().get_cursor().execute(
                tmp_cmd
            )
            self.get_jarvis_database().get_conn().commit()

    def update_cnt_of_query(self, action: str):
        data_from_user_table = self.get_jarvis_database().get_data_from_table(
            'users',
            f'id = {self.get_user_id()}',
            f'id'
        )
        if action == 'add':
            tmp_cmd = \
                f"""
                UPDATE users
                    SET count_of_requests = '{data_from_user_table[0][4] + 1}'
                    WHERE id = {self.get_user_id()};
                """
            self.get_jarvis_database().get_cursor().execute(
                tmp_cmd
            )
        elif action == 'remove':
            tmp_cmd = \
                f"""
                UPDATE users
                    SET count_of_requests = '{data_from_user_table[0][4] - 1}'
                    WHERE id = {self.get_user_id()};
                """
            self.get_jarvis_database().get_cursor().execute(
                tmp_cmd
            )
        self.get_jarvis_database().get_conn().commit()

    @staticmethod
    def print_exception():
        exc_type, exc_obj, tb = sys.exc_info()
        f = tb.tb_frame
        lineno = tb.tb_lineno
        filename = f.f_code.co_filename
        linecache.checkcache(filename)
        line = linecache.getline(filename, lineno, f.f_globals)
        print(
            f"""
            EXCEPTION IN ({filename}, LINE {lineno} "{line.strip()}"): {exc_obj}
            """
        )

    @staticmethod
    def get_current_date():
        sec_utc = time.time()

        # переводим из секунд в 'struct_time'
        time_local = time.localtime(sec_utc)

        # получаем форматированную строку из 'struct_time'
        current_date = time.strftime('%Y-%m-%d', time_local)
        return current_date

    @staticmethod
    def __get_pure_date(date: str):
        tmp_stop_flag_yyyy = False
        tmp_pure_yyyy = date.split('-')[0]
        for elem in date.split('-')[0]:
            if elem == '0' and not tmp_stop_flag_yyyy:
                tmp_pure_yyyy = tmp_pure_yyyy.replace(elem, '', 1)
            if elem != '0':
                tmp_stop_flag_yyyy = True

        tmp_stop_flag_mm = False
        tmp_pure_mm = date.split('-')[1]
        for elem in date.split('-')[1]:
            if elem == '0' and not tmp_stop_flag_mm:
                tmp_pure_mm = tmp_pure_mm.replace(elem, '', 1)
            if elem != '0':
                tmp_stop_flag_mm = True

        tmp_stop_flag_dd = False
        tmp_pure_dd = date.split('-')[2]
        for elem in date.split('-')[2]:
            if elem == '0' and not tmp_stop_flag_dd:
                tmp_pure_dd = tmp_pure_dd.replace(elem, '', 1)
            if elem != '0':
                tmp_stop_flag_dd = True
        return tmp_pure_yyyy, tmp_pure_mm, tmp_pure_dd

    @staticmethod
    def send_all_wav_news(bot, message):
        # Получаем текущую папку
        current_dir = Path('.')

        # Находим все файлы с расширением .wav
        wav_files = current_dir.glob('*.wav')

        for file in wav_files:
            with open(f"{file}", "rb") as f:
                bot.send_document(message.chat.id, f)

    @staticmethod
    def delete_all_wav_files():
        # Получаем текущую папку
        current_dir = Path('.')

        # Находим все файлы с расширением .wav
        wav_files = current_dir.glob('*.wav')

        # Удаляем каждый файл
        for file in wav_files:
            file.unlink()

    def is_date_correct(self, date: str):
        if date.count('-') != 2:
            return False
        else:
            tmp_pure_yyyy, tmp_pure_mm, tmp_pure_dd = self.__get_pure_date(date)

            try:
                if int(tmp_pure_yyyy) > int(self.get_current_date().split('-')[0]):
                    return False
            except ValueError:
                return False

            try:
                if int(tmp_pure_mm) > 12:
                    return False
            except ValueError:
                return False

            try:
                if int(tmp_pure_dd) > 31:
                    return False
            except ValueError:
                return False

        return True

    @staticmethod
    def split_message(message, max_length=4096):
        """
        Разбивает сообщение на части, чтобы каждая часть имела максимальную длину max_length.
        """
        return [message[i:i + max_length] for i in range(0, len(message), max_length)]


def main():
    bot = telebot.TeleBot(
        config.BOT_TOKEN,
        parse_mode=None
    )
    user = controller()
    user_data = {}
    user.init_markup_dictionary()
    dict_of_rubrics = user.get_lenta_parser().get_dict_of_rubrics()

    @bot.message_handler(commands=['start'])
    def start(message):
        data_from_user_table = user.get_jarvis_database().get_data_from_table(
            "users",
            f"id = '{message.from_user.id}'",
            f"id"
        )

        if not data_from_user_table:
            user.set_user_id(message.from_user.id)
            user.set_username(message.from_user.username)
            user.set_first_name(message.from_user.first_name)
            bot.send_message(
                message.chat.id,
                text=f"""
                    Приветствую, {user.get_first_name()}!{'\n'}Похоже, что Вы наш новый пользователь. Желаем Вам интересного использования бота!
                """,
                reply_markup=user.get_markup_dictionary()['start_markup']
            )
            user.insert_new_user_into_user_database()
            user.set_current_markup('start_markup')
        else:
            bot.send_message(
                message.chat.id,
                text=f"""
                    Здравствуйте, {data_from_user_table[0][1]}!{'\n'}Я бот Jarvis и готов помочь Вам!
                """,
                reply_markup=user.get_markup_dictionary()['start_markup']
            )
            user.set_current_markup('start_markup')

    @bot.message_handler(func=lambda message: True)
    def handle_message(message):
        user.set_user_id(message.from_user.id)
        try:
            data_from_user_table = user.get_jarvis_database().get_data_from_table(
                "users",
                f"id = '{user.get_user_id()}'",
                f"id"
            )
        except psycopg2.ProgrammingError:
            data_from_user_table = user.get_jarvis_database().get_data_from_table(
                "users",
                f"id = '{user.get_user_id()}'",
                f"id"
            )

        user.set_first_name(data_from_user_table[0][1])
        user.set_username(data_from_user_table[0][2])

        user.update_visit_date()

        chat_id = message.chat.id

        if chat_id in user_data:
            state = user_data[chat_id]["state"]

            if state == 'date_add':
                if not user.is_date_correct(message.text):
                    user.update_cnt_of_query('remove')
                    if user_data:
                        del user_data[chat_id]
                    bot.send_message(
                        message.chat.id,
                        text=f"Дата введена неверно. Пожалуйста, повторите ввод данных заново",
                        reply_markup=user.get_markup_dictionary()['tell_news_markup']
                    )
                    user.set_current_markup('tell_news_markup')
                else:
                    user_data[chat_id]["date"] = message.text
                    user.set_date(user_data[chat_id]["date"])
                    bot.send_message(chat_id, "Введите город, новости которого хотите получить:")
                    user_data[chat_id]["state"] = 'news_city_add'

            elif state == 'news_city_add':
                # Создание списка сообщений
                tmp_all_messages = []
                user_data[chat_id]["city"] = message.text
                user.set_city(user_data[chat_id]["city"])
                if user_data[chat_id]["city"] != 'Вернуться в главное меню':
                    tmp_data = user.get_jarvis_database().get_data_from_table(
                        'news',
                        f"""(rubric = '{user.get_name_of_rubric()}') and (date = '{user.get_date()}') and (city = '{user.get_city()}')""",
                        order_query=f"time"
                    )
                    try:
                        tmp_send_wav_files = True
                        if not tmp_data:
                            for new in user.get_lenta_parser().get_data_from_table():
                                message_text = (
                                    f"""Название новости: {new[1]}\n"""
                                    f"""Рубрика: {new[2]}\n"""
                                    f"""Ссылка: {new[3]}\n"""
                                    f"""Дата новости: {new[4]}\n"""
                                    f"""Время получения новости: {new[5]}\n\n"""
                                    f"""Описание новости: {new[6]}"""
                                )

                                if data_from_user_table[0][3] == 'text':
                                    messages = user.split_message(message_text)
                                    for msg_part in messages:
                                        if msg_part not in tmp_all_messages:
                                            tmp_all_messages.append(msg_part)
                                            bot.send_message(chat_id, msg_part)
                                elif data_from_user_table[0][3] == 'voice':  # Если вывод голосом
                                    messages = user.split_message(message_text)
                                    for msg_part in messages:
                                        filename = f"{msg_part[17:40]}.wav"
                                        user.get_synth().synth(
                                            msg_part,
                                            filename,
                                            speaker_id=3,
                                            speech_rate=1
                                        )
                                    tmp_send_wav_files = True
                        else:
                            if (user.get_lenta_parser().get_differences_between_two_time(
                                    user.get_lenta_parser().get_current_time(),
                                    tmp_data[0][5]) >= 3) and (tmp_data[0][4] == user.get_current_date()):
                                tmp_send_wav_files = False
                                for new in user.get_lenta_parser().get_data_from_table():
                                    message_text = (
                                        f"""Название новости: {new[1]}\n"""
                                        f"""Рубрика: {new[2]}\n"""
                                        f"""Ссылка: {new[3]}\n"""
                                        f"""Дата новости: {new[4]}\n"""
                                        f"""Время получения новости: {new[5]}\n\n"""
                                        f"""Описание новости: {new[6]}"""
                                    )

                                    if data_from_user_table[0][3] == 'text':
                                        messages = user.split_message(message_text)
                                        for msg_part in messages:
                                            if msg_part not in tmp_all_messages:
                                                tmp_all_messages.append(msg_part)
                                                bot.send_message(chat_id, msg_part)
                                    elif data_from_user_table[0][3] == 'voice':  # Если вывод голосом
                                        messages = user.split_message(message_text)
                                        for msg_part in messages:
                                            filename = f"{msg_part[17:40]}.wav"
                                            user.get_synth().synth(
                                                msg_part,
                                                filename,
                                                speaker_id=3,
                                                speech_rate=1
                                            )
                                        tmp_send_wav_files = True
                            else:
                                tmp_data_from_table = user.get_jarvis_database().get_data_from_table(
                                    'news',
                                    f"""(rubric = '{user.get_name_of_rubric()}') and (date = '{user.get_date()}') and (city = '{user.get_city()}')""",
                                    order_query=f"time"
                                )
                                for i in range(len(tmp_data_from_table)):
                                    message_text = (
                                        f"""Название новости: {tmp_data_from_table[i][1]}\n"""
                                        f"""Рубрика: {tmp_data_from_table[i][2]}\n"""
                                        f"""Ссылка: {tmp_data_from_table[i][3]}\n"""
                                        f"""Дата новости: {tmp_data_from_table[i][4]}\n"""
                                        f"""Время получения новости: {tmp_data_from_table[i][5]}\n\n"""
                                        f"""Описание новости: {tmp_data_from_table[i][6]}"""
                                    )

                                    if data_from_user_table[0][3] == 'text':
                                        messages = user.split_message(message_text)
                                        for msg_part in messages:
                                            if msg_part not in tmp_all_messages:
                                                tmp_all_messages.append(msg_part)
                                                bot.send_message(chat_id, msg_part)
                                    elif data_from_user_table[0][3] == 'voice':  # Если вывод голосом
                                        messages = user.split_message(message_text)
                                        for msg_part in messages:
                                            filename = f"{msg_part[17:40]}.wav"
                                            user.get_synth().synth(
                                                msg_part,
                                                filename,
                                                speaker_id=3,
                                                speech_rate=1
                                            )
                                        tmp_send_wav_files = True
                        # Отправка всех собранных сообщений
                        if data_from_user_table[0][3] == 'voice' and tmp_send_wav_files:
                            user.send_all_wav_news(bot, message)
                            user.delete_all_wav_files()
                    except Exception as e:
                        if 'news_not_found_on_page' in e.args:
                            bot.send_message(
                                chat_id,
                                f"""Новостей по рубрике "{user.get_name_of_rubric()}" сейчас нет в городе {user.get_city()}"""
                            )
                            user.get_lenta_parser().close_driver()
                        # else:
                        #     user.print_exception()

            elif state == 'weather_city_add':
                user_data[chat_id]["city"] = message.text
                user.set_city(user_data[chat_id]["city"])
                user.set_date(user.get_current_date())
                if user_data[chat_id]["city"] != 'Вернуться в главное меню':
                    tmp_data = user.get_jarvis_database().get_data_from_table(
                        'weather',
                        f"""(city = '{user.get_city()}') and (date = '{user.get_date()}')""",
                        order_query=f"date"
                    )

                    if not tmp_data:
                        tmp_data = user.get_weather_parser().get_data_from_table()

                        message_text = (
                            f"""Город: {tmp_data[0][1]}\n"""
                            f"""Дата: {tmp_data[0][2]}\n\n"""
                            f"""Описание погоды: {tmp_data[0][3]}\n"""
                            f"""Температура: {tmp_data[0][4]}°C\n"""
                            f"""Ощущается как: {tmp_data[0][5]}°C\n"""
                            f"""Минимальная дневная температура: {tmp_data[0][6]}°C\n"""
                            f"""Максимальная дневная температура: {tmp_data[0][7]}°C\n"""
                            f"""Скорость ветра: {tmp_data[0][8]} ㎧\n"""
                        )
                        if user_data:
                            del user_data[chat_id]
                        user.set_reserved_message(message_text)
                        bot.send_message(
                            message.chat.id,
                            text=f"{message_text}",
                            reply_markup=user.get_markup_dictionary()['weather_advice_markup']
                        )
                        user.set_current_markup('weather_advice_markup')
                    else:
                        if user_data:
                            del user_data[chat_id]
                        message_text = (
                            f"""Город: {tmp_data[0][1]}\n"""
                            f"""Дата: {tmp_data[0][2]}\n\n"""
                            f"""Описание погоды: {tmp_data[0][3]}\n"""
                            f"""Температура: {tmp_data[0][4]}°C\n"""
                            f"""Ощущается как: {tmp_data[0][5]}°C\n"""
                            f"""Минимальная дневная температура: {tmp_data[0][6]}°C\n"""
                            f"""Максимальная дневная температура: {tmp_data[0][7]}°C\n"""
                            f"""Скорость ветра: {tmp_data[0][8]} ㎧\n"""
                        )
                        user.set_reserved_message(message_text)
                        bot.send_message(
                            message.chat.id,
                            text=f"{message_text}",
                            reply_markup=user.get_markup_dictionary()['weather_advice_markup']
                        )
                        user.set_current_markup('weather_advice_markup')

        if (user.get_current_markup() == 'tell_news_markup') and (') ' in message.text):
            user.update_cnt_of_query('add')
            user.set_name_of_rubric(message.text.split(') ')[1])
            user.set_num_of_rubric(dict_of_rubrics[f'{user.get_name_of_rubric()}'])
            bot.send_message(
                chat_id,
                """Пожалуйста, введите дату, за которую хотите получить новости в формате "yyyy-mm-dd":""",
                reply_markup=user.get_markup_dictionary()['back_to_main_menu_markup']
            )
            user_data[message.chat.id] = {"state": 'date_add'}

        if message.text == "Посмотреть личный кабинет":
            data_from_user_table = user.get_jarvis_database().get_data_from_table(
                'users',
                f'id = {user.get_user_id()}',
                f'id'
            )
            bot.send_message(
                message.chat.id,
                text=f"""
                    {data_from_user_table[0][1]}, вот данные вашего личного кабинета:{'\n\n'}Ваш телеграм-id: {data_from_user_table[0][0]}{'\n'}Ваше имя пользователя: {data_from_user_table[0][2]}{'\n'}Ваш текущий формат вывода новостей: {data_from_user_table[0][3]}{'\n'}Ваше общее количество запросов: {data_from_user_table[0][4]}{'\n'}Дата вашего последнего использования бота: {data_from_user_table[0][5]}
                """,
                reply_markup=user.get_markup_dictionary()['personal_account_markup']
            )
            user.set_current_markup('personal_account_markup')
            # bot.send_message(message.chat.id, 'Введите ФИО:')
            # user_data[message.chat.id] = {"state": 'fio_add'}

        elif message.text == "Изменить тип вывода":
            bot.send_message(
                message.chat.id,
                text=f"""
                    Выберите новый тип вывода:
                """,
                reply_markup=user.get_markup_dictionary()['change_type_of_output_markup']
            )
            user.set_current_markup('change_type_of_output_markup')

        elif message.text == "Текстовый формат вывода (text)":
            user.change_output('text')
            data_from_user_table = user.get_jarvis_database().get_data_from_table(
                'users',
                f'id = {user.get_user_id()}',
                f'id'
            )
            bot.send_message(
                message.chat.id,
                text=f"""
                    Формат вывода успешно изменён на "{data_from_user_table[0][3]}"
                """
            )

        elif message.text == "Звуковой формат вывода (voice)":
            user.change_output('voice')
            data_from_user_table = user.get_jarvis_database().get_data_from_table(
                'users',
                f'id = {user.get_user_id()}',
                f'id'
            )
            bot.send_message(
                message.chat.id,
                text=f"""
                    Формат вывода успешно изменён на "{data_from_user_table[0][3]}"
                """
            )

        elif message.text == "Узнать информацию о новостях":
            bot.send_message(
                message.chat.id,
                text=f"Пожалуйста, выберите рубрику:",
                reply_markup=user.get_markup_dictionary()['tell_news_markup']
            )
            user.set_current_markup('tell_news_markup')

        elif message.text == "Узнать информацию о погоде":
            user.update_cnt_of_query('add')
            bot.send_message(
                message.chat.id,
                text=f"Пожалуйста, введите город, по которому хотите получить информацию о погоде на сегодня",
                reply_markup=user.get_markup_dictionary()['back_to_main_menu_markup']
            )
            user.set_current_markup('back_to_main_menu_markup')
            user_data[message.chat.id] = {"state": 'weather_city_add'}

        elif message.text == "Получить совет - как одеться в данную погоду":
            user.update_cnt_of_query('add')
            tmp_get_answer = user.get_hugging_chat().get_chat_response(
                f"Предоставь совет, как одеться в данную погоду: {user.get_reserved_message()}?",
                True
            )

            if tmp_get_answer:
                bot.send_message(
                    message.chat.id,
                    text=f"{tmp_get_answer}"
                )

        elif message.text == "Дополнительный функционал":
            bot.send_message(
                message.chat.id,
                text=f"Добро пожаловать в меню дополнительных функций бота!{'\n'}Для выбора необходимой функции воспользуйтесь клавиатурой ниже",
                reply_markup=user.get_markup_dictionary()['extra_functions_markup']
            )
            user.set_current_markup('extra_functions_markup')

        elif message.text == "❓ Задать вопрос":
            bot.send_message(
                message.chat.id,
                text="""
                Задай мне вопрос
                """,
                reply_markup=user.get_markup_dictionary()['faq_markup']
            )
            user.set_current_markup('faq_markup')

        elif message.text == "Как меня зовут?":
            bot.send_message(message.chat.id, "Меня зовут Jarvis. Пока Тони Старк отдыхает, я работаю в качестве телеграм-бота - это моё хобби!")

        elif message.text == "Что я могу?":
            bot.send_message(message.chat.id, text="Я могу подсказать вам погоду, новости, а также сгенерировать изображение по вашему запросу")

        elif message.text == "Вернуться в главное меню":
            if user_data:
                del user_data[chat_id]
            bot.send_message(
                message.chat.id,
                text="Вы вернулись в главное меню",
                reply_markup=user.get_markup_dictionary()['start_markup']
            )
            user.set_current_markup('start_markup')

    bot.polling(none_stop=True)


def test():
    response = ollama.chat(model='qwen:0.5b', messages=[
        {
            'role': 'user',
            'content': 'Почему небо голубое?',
        },
    ])
    print(response['message']['content'])


if __name__ == '__main__':
    main()
    # test()
