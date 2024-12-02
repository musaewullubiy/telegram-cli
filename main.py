#!/usr/bin/python
import sys

import pyrogram
import typer
from pyrogram import Client
from pyrogram.errors import PeerIdInvalid, ChatIdInvalid
import hashlib
import json

import configparser
import os

config_file = 'config.ini'
config = configparser.ConfigParser()
app = typer.Typer()

@app.command()
def setup():
    print("https://my.telegram.org/auth")
    api_id = input("Введите api_id: ")
    api_hash = input("Введите api_hash: ")

    # Если файл не существует, создаем его с заданными значениями
    config['Telegram'] = {
        'api_id': api_id,
        'api_hash': api_hash
    }

    # Записываем конфигурацию в файл
    with open(config_file, 'w') as configfile:
        config.write(configfile)

    print(f"Файл конфигурации {config_file} создан с заданными значениями.")

try:
    config.read(config_file)
    api_id = config.get('Telegram', 'api_id')
    api_hash = config.get('Telegram', 'api_hash')

except Exception as e:
    setup()
    sys.exit()

client = pyrogram.Client(
    'my_account',
    api_id=api_id,
    api_hash=api_hash
)

HASHES_FILE = 'chat_hashes.json'
TAGS_FILE = 'chat_tags.json'

def hash_id(chat_id: str) -> str:
    return hashlib.sha256(chat_id.encode()).hexdigest()

def get_chat_id(chat_id: str):
    if chat_id:
        try:
            return int(chat_id)
        except ValueError:
            raise typer.BadParameter("Неверный формат chat_id. Должно быть целым числом.")

def load_hashes():
    if os.path.exists(HASHES_FILE):
        with open(HASHES_FILE, 'r') as file:
            return json.load(file)
    return {}

def save_hashes(hashes):
    all_hashes = load_hashes()
    for i in all_hashes:
        hashes[i] = all_hashes[i]
    with open(HASHES_FILE, 'w') as file:
        json.dump(hashes, file, indent=4)

def load_tags():
    if os.path.exists(TAGS_FILE):
        with open(TAGS_FILE, 'r') as file:
            return json.load(file)
    return {}

def save_tags(tags):
    with open(TAGS_FILE, 'w') as file:
        json.dump(tags, file, indent=4)

def find_chat_id_by_hash_prefix(hashes, prefix):
    matching_hashes = [hash_val for hash_val in hashes if hash_val.startswith(prefix)]
    if matching_hashes:
        return hashes[matching_hashes[0]]
    return None

@app.command()
def send(
    chat: str = typer.Option(None, help="ID чата, префикс хеша или тег."),
    message: str = typer.Argument(..., help="Сообщение для отправки.")
):
    """
        Отправляет сообщение

        :param chat: Идентификатор чата (id, hash или tag)
        :param message: Желаемое сообщение
    """
    client.start()
    try:
        hashes = load_hashes()
        tags = load_tags()

        if chat in hashes:
            chat_id = hashes[chat]
        elif chat in tags:
            chat_id = tags[chat]
        else:
            # Поиск по префиксу хеша
            chat_id = find_chat_id_by_hash_prefix(hashes, chat)
            if not chat_id:
                chat_id = get_chat_id(chat)

        client.send_message(chat_id, message)
        typer.echo("Отправлено")
    except (PeerIdInvalid, ChatIdInvalid) as e:
        typer.echo(f"Ошибка: {e}")
    finally:
        client.stop()

@app.command()
def get_chats(count: int):
    """
        Показывает последние count чатов

        :param count: Количество чатов
    """
    client.start()
    dialogs = client.get_dialogs(limit=count)
    chat_list = [(hash_id(str(dialog.chat.id)), str(dialog.chat.id), dialog.chat.title or dialog.chat.first_name) for dialog in dialogs]

    # Загружаем теги
    tags = load_tags()

    # Определяем максимальную ширину для каждой колонки
    hash_width = len(chat_list[-1][0])
    id_width = 17
    name_width = max(len(chat[2]) for chat in chat_list)
    tag_width = max(len(tag) for tag in tags.keys()) if tags else 0

    # Форматируем заголовок
    header = f"{'HASH':<{hash_width}}\t{'ID':<{id_width}}\t{'NAME':<{name_width}}\t{'TAG':<{tag_width}}"
    typer.echo(header)

    # Форматируем строки
    hashes = {}
    for chat in chat_list:
        hash_val, id_val, name_val = chat
        tag_val = next((tag for tag, chat_id in tags.items() if chat_id == id_val), '')
        typer.echo(f"{hash_val:<{hash_width}}\t{id_val:<{id_width}}\t{name_val:<{name_width}}\t{tag_val:<{tag_width}}")
        hashes[hash_val] = id_val

    save_hashes(hashes)
    client.stop()

@app.command()
def tag(chat: str, tag: str):
    """
        Добавляет тег к чату.

        :param chat: Идентификатор чата (id, hash или tag)
        :param tag: Желаемый тег
    """
    client.start()
    try:
        hashes = load_hashes()
        tags = load_tags()

        if chat in hashes:
            chat_id = hashes[chat]
        elif chat in tags:
            chat_id = tags[chat]
        else:
            # Поиск по префиксу хеша
            chat_id = find_chat_id_by_hash_prefix(hashes, chat)
            if not chat_id:
                chat_id = get_chat_id(chat)

        tags[tag] = chat_id
        save_tags(tags)
        typer.echo(f"Тег '{tag}' добавлен к чату с ID {chat_id}")
    except (PeerIdInvalid, ChatIdInvalid) as e:
        typer.echo(f"Ошибка: {e}")
    finally:
        client.stop()

@app.command()
def get_tags():
    """
        Показывает список тегов прикрепленных к чатам.
    """
    tags = load_tags()
    if tags:
        typer.echo("Список тегов:")
        for tag, chat_id in tags.items():
            typer.echo(f"{tag}: {chat_id}")
    else:
        typer.echo("Нет тегов.")

@app.command()
def show(chat: str, count: int):
    """
    Показывает последние n сообщений из указанного чата.

    :param chat: Идентификатор чата (id, hash или tag)
    :param count: Количество сообщений для отображения
    """
    client.start()
    try:
        hashes = load_hashes()
        tags = load_tags()

        if chat in hashes:
            chat_id = hashes[chat]
        elif chat in tags:
            chat_id = tags[chat]
        else:
            # Поиск по префиксу хеша
            chat_id = find_chat_id_by_hash_prefix(hashes, chat)
            if not chat_id:
                chat_id = get_chat_id(chat)

        # Получаем последние n сообщений
        messages = client.get_chat_history(chat_id=chat_id, limit=count)

        # Отображаем сообщения
        for msg in list(messages)[::-1]:
            text = msg.text or msg.caption or "No text"
            if msg.from_user.last_name:
                name = msg.from_user.first_name + msg.from_user.last_name
            else:
                name = msg.from_user.first_name

            typer.echo(f"{name}\nText:")
            typer.echo(f"{text}\n")
            typer.echo(f"| {msg.date} |")
            typer.echo(f"- - - - - - - - - - - - - - - - - - - - - -")
    except (PeerIdInvalid, ChatIdInvalid) as e:
        typer.echo(f"Ошибка: {e}")
    finally:
        client.stop()

if __name__ == "__main__":
    app()
