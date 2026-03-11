"""
Главный файл приложения R4Mesg
Инициализация и управление экранами
"""

from kivy.app import App
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.core.window import Window
from kivy.clock import Clock
from kivy.properties import ObjectProperty
from kivy.utils import platform

# Для корректной работы на мобильных устройствах
if platform in ['android', 'ios']:
    from kivy.core.window import Window
    Window.softinput_mode = 'below_target'

from screens import LoginScreen, ChatListScreen, ChatScreen
from client import R4MesgClient


class R4MesgApp(App):
    """
    Главный класс приложения
    """
    client = ObjectProperty(None)
    current_user = ObjectProperty(None)
    
    def build(self):
        # Инициализация клиента API
        self.client = R4MesgClient(
            base_url='https://api.r4mesg.com',  # Замените на реальный URL
            ws_url='wss://ws.r4mesg.com'
        )
        
        # Создание менеджера экранов
        self.sm = ScreenManager()
        
        # Добавление экранов
        self.sm.add_widget(LoginScreen(name='login'))
        self.sm.add_widget(ChatListScreen(name='chat_list'))
        self.sm.add_widget(ChatScreen(name='chat'))
        
        return self.sm
    
    def on_start(self):
        """Вызывается при запуске приложения"""
        # Проверка сохраненной сессии
        if self.client.load_session():
            self.current_user = self.client.get_current_user()
            self.sm.current = 'chat_list'
            # Запуск WebSocket соединения
            self.client.connect_websocket(self.on_new_message)
    
    def on_new_message(self, message):
        """
        Обработчик новых сообщений через WebSocket
        Вызывается из другого потока
        """
        # Планируем обновление UI в главном потоке
        Clock.schedule_once(lambda dt: self.update_ui_with_message(message))
    
    def update_ui_with_message(self, message):
        """Обновление интерфейса новым сообщением"""
        current_screen = self.sm.current_screen
        if current_screen.name == 'chat' and current_screen.chat_id == message['chat_id']:
            current_screen.add_new_message(message)
        else:
            # Обновляем список чатов, показывая новое сообщение
            chat_list_screen = self.sm.get_screen('chat_list')
            chat_list_screen.update_last_message(message)
    
    def logout(self):
        """Выход из аккаунта"""
        self.client.disconnect_websocket()
        self.client.clear_session()
        self.current_user = None
        self.sm.current = 'login'


if __name__ == '__main__':
    R4MesgApp().run()