"""
Экраны приложения R4Mesg
LoginScreen, ChatListScreen, ChatScreen
"""

from kivy.uix.screenmanager import Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.recycleview import RecycleView
from kivy.uix.recycleboxlayout import RecycleBoxLayout
from kivy.uix.behaviors import FocusBehavior
from kivy.uix.recycleview.layout import LayoutSelectionBehavior
from kivy.properties import StringProperty, NumericProperty, ObjectProperty, ListProperty, BooleanProperty
from kivy.clock import Clock
from kivy.app import App
from kivy.metrics import dp
from kivy.logger import Logger
from datetime import datetime


class SelectableRecycleBoxLayout(FocusBehavior, LayoutSelectionBehavior, RecycleBoxLayout):
    """Layout для RecycleView с поддержкой выбора элементов"""
    pass


class MessageWidget(BoxLayout):
    """
    Виджет отдельного сообщения
    """
    text = StringProperty('')
    time = StringProperty('')
    is_own = BooleanProperty(False)
    status = StringProperty('delivered')  # sent, delivered, read
    avatar = StringProperty('')
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.register_event_type('on_double_tap')
    
    def on_double_tap(self):
        """Обработка двойного тапа для дополнительных действий"""
        pass


class ChatListItem(BoxLayout):
    """
    Элемент списка чатов
    """
    chat_id = NumericProperty(0)
    name = StringProperty('')
    last_message = StringProperty('')
    last_message_time = StringProperty('')
    avatar = StringProperty('')
    unread_count = NumericProperty(0)
    online = BooleanProperty(False)
    
    def on_touch_down(self, touch):
        if self.collide_point(*touch.pos):
            app = App.get_running_app()
            chat_screen = app.sm.get_screen('chat')
            chat_screen.chat_id = self.chat_id
            chat_screen.chat_name = self.name
            chat_screen.load_messages()
            app.sm.current = 'chat'
            return True
        return super().on_touch_down(touch)


class LoginScreen(Screen):
    """
    Экран авторизации и регистрации
    """
    username_input = ObjectProperty(None)
    password_input = ObjectProperty(None)
    email_input = ObjectProperty(None)
    status_label = ObjectProperty(None)
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.is_login_mode = True
    
    def toggle_mode(self):
        """Переключение между логином и регистрацией"""
        self.is_login_mode = not self.is_login_mode
        
        if self.is_login_mode:
            self.ids.email_input.opacity = 0
            self.ids.email_input.disabled = True
            self.ids.toggle_button.text = 'Нет аккаунта? Зарегистрироваться'
            self.ids.action_button.text = 'Войти'
        else:
            self.ids.email_input.opacity = 1
            self.ids.email_input.disabled = False
            self.ids.toggle_button.text = 'Уже есть аккаунт? Войти'
            self.ids.action_button.text = 'Зарегистрироваться'
    
    def submit(self):
        """Обработка нажатия кнопки действия"""
        username = self.ids.username_input.text.strip()
        password = self.ids.password_input.text.strip()
        
        if not username or not password:
            self.show_status('Заполните все поля', 'error')
            return
        
        app = App.get_running_app()
        
        if self.is_login_mode:
            success, result = app.client.login(username, password)
            
            if success:
                app.current_user = result
                app.sm.current = 'chat_list'
                app.client.connect_websocket(app.on_new_message)
                self.clear_inputs()
            else:
                self.show_status(result, 'error')
        else:
            email = self.ids.email_input.text.strip()
            if not email:
                self.show_status('Заполните все поля', 'error')
                return
            
            success, result = app.client.register(username, password, email)
            
            if success:
                self.show_status('Регистрация успешна! Теперь войдите', 'success')
                self.toggle_mode()
                self.clear_inputs()
            else:
                self.show_status(result, 'error')
    
    def show_status(self, text, status_type='info'):
        """Отображение статуса"""
        self.ids.status_label.text = text
        self.ids.status_label.color = (1, 0, 0, 1) if status_type == 'error' else (0, 1, 0, 1)
        
        # Очищаем статус через 3 секунды
        Clock.schedule_once(lambda dt: self.clear_status(), 3)
    
    def clear_status(self):
        """Очистка статуса"""
        self.ids.status_label.text = ''
    
    def clear_inputs(self):
        """Очистка полей ввода"""
        self.ids.username_input.text = ''
        self.ids.password_input.text = ''
        self.ids.email_input.text = ''


class ChatListScreen(Screen):
    """
    Экран со списком чатов
    """
    chats_list = ObjectProperty(None)
    loading = BooleanProperty(False)
    
    def on_enter(self):
        """При входе на экран загружаем список чатов"""
        self.load_chats()
    
    def load_chats(self):
        """Загрузка списка чатов"""
        self.loading = True
        app = App.get_running_app()
        
        # Загружаем в фоне, чтобы не блокировать UI
        Clock.schedule_once(lambda dt: self._do_load_chats(app), 0.1)
    
    def _do_load_chats(self, app):
        """Фактическая загрузка чатов"""
        success, chats = app.client.get_chats()
        
        if success:
            # Форматируем данные для RecycleView
            data = []
            for chat in chats:
                data.append({
                    'chat_id': chat['id'],
                    'name': chat['name'],
                    'last_message': chat.get('last_message', ''),
                    'last_message_time': self.format_time(chat.get('last_message_time')),
                    'avatar': chat.get('avatar', ''),
                    'unread_count': chat.get('unread_count', 0),
                    'online': chat.get('online', False)
                })
            
            self.ids.chats_list.data = data
        
        self.loading = False
    
    def format_time(self, timestamp):
        """Форматирование времени сообщения"""
        if not timestamp:
            return ''
        
        try:
            msg_time = datetime.fromisoformat(timestamp)
            now = datetime.now()
            
            if msg_time.date() == now.date():
                return msg_time.strftime('%H:%M')
            elif (now - msg_time).days < 7:
                return msg_time.strftime('%a')
            else:
                return msg_time.strftime('%d.%m.%y')
        except:
            return ''
    
    def update_last_message(self, message):
        """Обновление последнего сообщения в списке чатов"""
        # Находим чат и обновляем его последнее сообщение
        data = self.ids.chats_list.data[:]
        
        for i, item in enumerate(data):
            if item['chat_id'] == message['chat_id']:
                data[i]['last_message'] = message['text']
                data[i]['last_message_time'] = self.format_time(message['timestamp'])
                break
        
        self.ids.chats_list.data = data
    
    def logout(self):
        """Выход из аккаунта"""
        app = App.get_running_app()
        app.logout()


class ChatScreen(Screen):
    """
    Экран чата с сообщениями
    """
    chat_id = NumericProperty(0)
    chat_name = StringProperty('')
    messages_list = ObjectProperty(None)
    message_input = ObjectProperty(None)
    loading = BooleanProperty(False)
    
    def on_enter(self):
        """При входе в чат загружаем сообщения"""
        self.load_messages()
    
    def on_leave(self):
        """При выходе из чата очищаем данные"""
        self.ids.messages_list.data = []
    
    def load_messages(self):
        """Загрузка истории сообщений"""
        if self.chat_id == 0:
            return
        
        self.loading = True
        app = App.get_running_app()
        
        # Загружаем в фоне
        Clock.schedule_once(lambda dt: self._do_load_messages(app), 0.1)
    
    def _do_load_messages(self, app):
        """Фактическая загрузка сообщений"""
        success, messages = app.client.get_messages(self.chat_id)
        
        if success:
            # Форматируем данные для RecycleView
            data = []
            for msg in messages:
                data.append({
                    'text': msg['text'],
                    'time': self.format_time(msg['timestamp']),
                    'is_own': msg['user_id'] == app.current_user['id'],
                    'status': msg.get('status', 'delivered'),
                    'avatar': msg.get('avatar', '')
                })
            
            self.ids.messages_list.data = data
            
            # Прокручиваем вниз к последним сообщениям
            Clock.schedule_once(lambda dt: self.scroll_to_bottom(), 0.2)
        
        self.loading = False
    
    def format_time(self, timestamp):
        """Форматирование времени сообщения"""
        try:
            msg_time = datetime.fromisoformat(timestamp)
            return msg_time.strftime('%H:%M')
        except:
            return ''
    
    def send_message(self):
        """Отправка сообщения"""
        text = self.ids.message_input.text.strip()
        
        if not text or self.chat_id == 0:
            return
        
        app = App.get_running_app()
        
        # Отправляем сообщение
        success, message = app.client.send_message(self.chat_id, text)
        
        if success:
            # Добавляем сообщение в список
            new_message = {
                'text': message['text'],
                'time': self.format_time(message['timestamp']),
                'is_own': True,
                'status': 'sent',
                'avatar': ''
            }
            
            data = self.ids.messages_list.data[:]
            data.append(new_message)
            self.ids.messages_list.data = data
            
            # Очищаем поле ввода
            self.ids.message_input.text = ''
            
            # Прокручиваем вниз
            self.scroll_to_bottom()
    
    def add_new_message(self, message):
        """Добавление нового сообщения (из WebSocket)"""
        if message['chat_id'] != self.chat_id:
            return
        
        new_message = {
            'text': message['text'],
            'time': self.format_time(message['timestamp']),
            'is_own': False,
            'status': 'delivered',
            'avatar': message.get('avatar', '')
        }
        
        data = self.ids.messages_list.data[:]
        data.append(new_message)
        self.ids.messages_list.data = data
        
        self.scroll_to_bottom()
        
        # Отмечаем сообщение как прочитанное
        app = App.get_running_app()
        app.client.mark_as_read(self.chat_id, [message['id']])
    
    def scroll_to_bottom(self):
        """Прокрутка списка вниз"""
        if self.ids.messages_list.data:
            self.ids.messages_list.scroll_y = 0
    
    def go_back(self):
        """Возврат к списку чатов"""
        app = App.get_running_app()
        app.sm.current = 'chat_list'