import os
import time

from hugchat import hugchat
from hugchat.login import Login

from login_details import EMAIL, PASSWD


class HuggingChat:
    def __init__(
            self,
            email: str,
            password: str,
            cookie_path_dir: str = "cookies/"
    ):
        self.__email = email
        self.__password = password
        self.__cookies = {}
        self.__cnt_of_messages = 0
        self.__cookie_path_dir = cookie_path_dir
        self.__conversation_id = None
        self.__conversation_flag = False
        self.__stop_flag = False
        self.__chatbot = hugchat.ChatBot(cookies=self.get_cookies())

    def set_conversation_flag(
            self,
            flag: bool
    ):
        self.__conversation_flag = flag

    def get_conversation_flag(self):
        return self.__conversation_flag

    def get_email(self):
        return self.__email

    def get_password(self):
        return self.__password

    def __chat_authorization(self):
        self.__sign = Login(self.get_email(), self.get_password())

    def get_cookie_path_dir(self):
        return self.__cookie_path_dir

    def get_cookies(self):
        self.__chat_authorization()
        self.__cookies = self.__sign.login(
            cookie_dir_path=self.get_cookie_path_dir(),
            save_cookies=True
        )
        return self.__cookies.get_dict()

    def get_chatbot(self):
        return self.__chatbot

    def get_conversation_id(self):
        return self.__conversation_id

    def get_chat_response(
            self,
            prompt: str,
            new_conv: bool = False
    ):
        if new_conv:
            self.get_chatbot().new_conversation(
                switch_to=True,
            )
            self.__conversation_id = self.get_chatbot().new_conversation()
        else:
            pass

        self.get_chatbot().change_conversation(self.get_conversation_id())
        return self.get_chatbot().chat(prompt)

    def print_chat_response(
            self,
            prompt: str,
            new_conv: bool = False
    ):
        print(self.get_chat_response(prompt, new_conv))

    def set_cnt_of_messages(self,
                            cnt_of_msg: int
                            ):
        self.__cnt_of_messages = cnt_of_msg

    def increment_cnt_of_messages(self):
        self.__cnt_of_messages += 1

    def get_cnt_of_messages(self):
        return self.__cnt_of_messages

    def start_loop_dialog(self):
        while not self.__stop_flag:
            print(
                """
                Чтобы выйти - введите '0'
                Чтобы очистить чат - введи '1',
                """
            )
            user_resp = input(
                'Напиши свой запрос: '
            )

            if user_resp == '0':
                self.__stop_flag = True
                break
            else:
                if self.get_cnt_of_messages() == 0:
                    self.set_conversation_flag(True)
                elif self.get_cnt_of_messages() > 0:
                    self.set_conversation_flag(False)

                if user_resp == '1':
                    self.get_chatbot().new_conversation(
                        switch_to=True,
                    )
                    self.__conversation_id = self.get_chatbot().new_conversation()
                    print('История чата очищена!')
                    time.sleep(3)
                    print('\n\n')
                    self.start_loop_dialog()

                self.print_chat_response(
                    user_resp,
                    self.get_conversation_flag()
                )
                self.increment_cnt_of_messages()
            print('\n')

    def delete_all_conversations(self):
        self.get_chatbot().delete_all_conversations()


def main():
    # Create your ChatBot
    # system_prompt = """
    # Ты опытный программист, который очень любит парсить сайты, особенно сайт
    # 'lenta.ru'
    # """

    chat = HuggingChat(EMAIL, PASSWD)
    chat.start_loop_dialog()
    print('\n\n')


if __name__ == '__main__':
    if not os.path.exists('cookies'):
        os.mkdir('cookies')

    main()

# See PyCharm help at https://www.jetbrains.com/help/pycharm/
