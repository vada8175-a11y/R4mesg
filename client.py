"""
Клиент для работы с REST API и WebSocket
Обработка сетевых запросов и real-time соединений
"""

import requests
import websocket
import threading
import json
import time
from datetime import datetime
from kivy.clock import Clock
from kivy.logger import Logger
from functools import partial


class R4MesgClient:
    """
    Клиент для взаимодействия с сервером
    Поддерживает HTTP и WebSocket соединения
    """
    
    def __init__(self, base_url, ws_url):
        self.base_url = base_url
        self.ws_url = ws_url
        self.session = requests.Session()
        self.ws = None
        self.ws_thread = None
        self.reconnect_attempt = 0
        self.max_reconnect_delay = 60  # максимальная задержка 60 секунд
        self.message_callback = None
        self.connected = False
        self.auth_token = None
        self.current_user = None
        
    # ========== HTTP методы ==========
    
    def login(self, username, password):
        """
        Авторизация пользователя
        """
        try:
            response = self.session.post(
                f'{self.base_url}/api/login',
                json={
                    'username': username,
                    'password': password
                },
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                self.auth_token = data['token']
                self.current_user = data['user']
                self.session.headers.update({
                    'Authorization': f'Bearer {self.auth_token}'
                })
                self.save_session()
                return True, data['user']
            else:
                return False, response.json().get('error', 'Ошибка авторизации')
                
        except requests.exceptions.RequestException as e:
            Logger.error(f'Ошибка соединения: {e}')
            return False, 'Ошибка соединения с сервером'
    
    def register(self, username, password, email):
        """
        Регистрация нового пользователя
        """
        try:
            response = self.session.post(
                f'{self.base_url}/api/register',
                json={
                    'username': username,
                    'password': password,
                    'email': email
                },
                timeout=10
            )
            
            if response.status_code == 201:
                return True, 'Регистрация успешна'
            else:
                return False, response.json().get('error', 'Ошибка регистрации')
                
        except requests.exceptions.RequestException as e:
            Logger.error(f'Ошибка соединения: {e}')
            return False, 'Ошибка соединения с сервером'
    
    def get_chats(self):
        """
        Получение списка чатов пользователя
        """
        try:
            response = self.session.get(
                f'{self.base_url}/api/chats',
                timeout=10
            )
            
            if response.status_code == 200:
                return True, response.json()['chats']
            else:
                return False, []
                
        except requests.exceptions.RequestException as e:
            Logger.error(f'Ошибка получения чатов: {e}')
            return False, []
    
    def get_messages(self, chat_id, limit=50, offset=0):
        """
        Получение истории сообщений чата
        """
        try:
            response = self.session.get(
                f'{self.base_url}/api/chats/{chat_id}/messages',
                params={
                    'limit': limit,
                    'offset': offset
                },
                timeout=10
            )
            
            if response.status_code == 200:
                return True, response.json()['messages']
            else:
                return False, []
                
        except requests.exceptions.RequestException as e:
            Logger.error(f'Ошибка получения сообщений: {e}')
            return False, []
    
    def send_message(self, chat_id, text):
        """
        Отправка нового сообщения
        """
        try:
            response = self.session.post(
                f'{self.base_url}/api/chats/{chat_id}/messages',
                json={
                    'text': text,
                    'timestamp': datetime.now().isoformat()
                },
                timeout=10
            )
            
            if response.status_code == 201:
                return True, response.json()['message']
            else:
                return False, None
                
        except requests.exceptions.RequestException as e:
            Logger.error(f'Ошибка отправки сообщения: {e}')
            return False, None
    
    def mark_as_read(self, chat_id, message_ids):
        """
        Отметка сообщений как прочитанных
        """
        try:
            self.session.post(
                f'{self.base_url}/api/chats/{chat_id}/read',
                json={'message_ids': message_ids},
                timeout=5
            )
        except:
            pass  # Не критично, если не отправится
    
    # ========== WebSocket методы ==========
    
    def connect_websocket(self, message_callback):
        """
        Установка WebSocket соединения
        """
        self.message_callback = message_callback
        
        if not self.auth_token:
            Logger.warning('Нет токена авторизации для WebSocket')
            return False
        
        # Запускаем WebSocket в отдельном потоке
        self.ws_thread = threading.Thread(target=self._ws_connect)
        self.ws_thread.daemon = True
        self.ws_thread.start()
        
        return True
    
    def _ws_connect(self):
        """
        Внутренний метод для подключения WebSocket
        """
        ws_url = f"{self.ws_url}/?token={self.auth_token}"
        
        # Настройка WebSocket
        websocket.enableTrace(False)
        self.ws = websocket.WebSocketApp(
            ws_url,
            on_open=self._on_ws_open,
            on_message=self._on_ws_message,
            on_error=self._on_ws_error,
            on_close=self._on_ws_close
        )
        
        # Запуск WebSocket
        self.ws.run_forever()
    
    def _on_ws_open(self, ws):
        """Обработчик открытия соединения"""
        Logger.info('WebSocket соединение установлено')
        self.connected = True
        self.reconnect_attempt = 0
        
        # Отправляем приветственное сообщение
        ws.send(json.dumps({
            'type': 'init',
            'user_id': self.current_user['id']
        }))
    
    def _on_ws_message(self, ws, message):
        """Обработчик входящих сообщений"""
        try:
            data = json.loads(message)
            
            if data['type'] == 'new_message':
                # Вызываем колбэк для нового сообщения
                if self.message_callback:
                    self.message_callback(data['message'])
                    
            elif data['type'] == 'message_status':
                # Обработка статусов сообщений
                pass
                
        except json.JSONDecodeError:
            Logger.error(f'Ошибка парсинга WebSocket сообщения: {message}')
    
    def _on_ws_error(self, ws, error):
        """Обработчик ошибок WebSocket"""
        Logger.error(f'WebSocket ошибка: {error}')
        self.connected = False
    
    def _on_ws_close(self, ws, close_status_code, close_msg):
        """Обработчик закрытия соединения"""
        Logger.info('WebSocket соединение закрыто')
        self.connected = False
        
        # Пытаемся переподключиться
        if self.auth_token:  # Только если пользователь еще авторизован
            self._schedule_reconnect()
    
    def _schedule_reconnect(self):
        """
        Планирование переподключения с экспоненциальной задержкой
        """
        self.reconnect_attempt += 1
        
        # Экспоненциальная задержка
        delay = min(2 ** self.reconnect_attempt, self.max_reconnect_delay)
        
        Logger.info(f'Попытка переподключения через {delay} секунд')
        
        # Используем Clock для планирования в главном потоке
        Clock.schedule_once(
            lambda dt: self.connect_websocket(self.message_callback),
            delay
        )
    
    def disconnect_websocket(self):
        """Закрытие WebSocket соединения"""
        if self.ws:
            self.ws.close()
        self.connected = False
    
    # ========== Работа с сессией ==========
    
    def save_session(self):
        """
        Сохранение сессии (для реального приложения используйте безопасное хранилище)
        """
        # В реальном приложении здесь должно быть шифрование
        session_data = {
            'token': self.auth_token,
            'user': self.current_user
        }
        
        try:
            with open('session.dat', 'w') as f:
                json.dump(session_data, f)
        except:
            pass
    
    def load_session(self):
        """
        Загрузка сохраненной сессии
        """
        try:
            with open('session.dat', 'r') as f:
                session_data = json.load(f)
                
            self.auth_token = session_data['token']
            self.current_user = session_data['user']
            
            if self.auth_token:
                self.session.headers.update({
                    'Authorization': f'Bearer {self.auth_token}'
                })
                return True
                
        except:
            pass
        
        return False
    
    def clear_session(self):
        """Очистка сессии"""
        self.auth_token = None
        self.current_user = None
        try:
            import os
            os.remove('session.dat')
        except:
            pass
    
    def get_current_user(self):
        """Получение текущего пользователя"""
        return self.current_user