#!/usr/bin/python
from datetime import datetime
import sys

import pyrogram
import typer
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

def get_id_by_smthg(smthg):
    hashes = load_hashes()
    tags = load_tags()
    chat_id = find_chat_id_by_hash_prefix(hashes, smthg)
    if not chat_id:
        if smthg in hashes:
            chat_id = hashes[smthg]
        elif smthg in tags:
            chat_id = tags[smthg]
        else:
            chat_id = client.get_users(smthg).id
    return int(chat_id)

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
        chat_id = get_id_by_smthg(chat)

        client.send_message(chat_id, message)
        typer.echo("Отправлено")
    except Exception as e:
        typer.echo(f"Ошибка: {e}")
    finally:
        client.stop()

@app.command()
def chats(count: int = typer.Option(10, "-c")):
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
        chat_id = get_id_by_smthg(chat)

        tags = load_tags()
        tags[tag] = chat_id
        save_tags(tags)
        typer.echo(f"Тег '{tag}' добавлен к чату с ID {chat_id}")
    except Exception as e:
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

def get_name(msg):
    if msg.from_user:
        if msg.from_user.last_name:
            name = msg.from_user.first_name + msg.from_user.last_name
        else:
            name = msg.from_user.first_name
    else:
        name = msg.chat.title
    if msg.from_user.username:
        name = f"{name} == @{msg.from_user.username}"
    else:
        name = f"{name} == id:{msg.from_user.id}"

    return name

@app.command()
def show(chat: str,
         count: int = typer.Option(10, "-c"),
         nofiles: bool = typer.Option(False, "--nofiles"),
         by: str = typer.Option(None, "-by")
         ):
    """
    Показывает последние count сообщений из указанного чата.

    :param chat: Идентификатор чата (id, hash или tag)
    :param count: Количество сообщений для отображения
    """
    client.start()
    chat_id = get_id_by_smthg(chat)

    # Получаем последние n сообщений
    messages = client.get_chat_history(chat_id=chat_id, limit=count)

    if by:
        by_id = get_id_by_smthg(by)
        messages = [msg for msg in messages if msg.from_user.id == by_id]

    # Отображаем сообщения
    for msg in list(messages)[::-1]:

        if msg.reply_to_message_id:
            replied_msg = client.get_messages(msg.chat.id, msg.reply_to_message_id)

            replied_name = get_name(replied_msg)
            typer.echo(f"<-<-<-<-<-<-<-<- Отвечает на это сообщение от {replied_name}:")

            replied_text = replied_msg.text or replied_msg.caption or False
            if replied_msg.photo:
                typer.echo(f"\t<-ФОТОГРАФИЯ->")
            elif replied_msg.video:
                typer.echo(f"\t<-ВИДЕОРОЛИК->")


            if replied_text:
                typer.echo(f"\tText: {replied_text}")
            typer.echo(f"\t| {replied_msg.date} |")
            typer.echo(f"->->->->->->->->")

        text = msg.text or msg.caption or False
        if msg.photo:
            if nofiles:
                typer.echo(f"<-ФОТОГРАФИЯ->")
            else:
                # Скачиваем фото и создаем ссылку для открытия
                photo_path = client.download_media(msg.photo.file_id)
                typer.echo(f"file://{photo_path}")

        elif msg.video:
            if nofiles:
                typer.echo(f"<-ВИДЕОРОЛИК->")
            else:
                # Скачиваем видео и создаем ссылку для открытия
                video_path = client.download_media(msg.video.file_id)
                typer.echo(f"file://{video_path}")
        name = get_name(msg)
        typer.echo(name)

        if text:
            typer.echo(f"Text: {text}")

        if msg.reactions:
            reactions = list()
            for reaction in msg.reactions.reactions:
                reactions.append(f"{reaction.count} {reaction.emoji}")
            typer.echo("Reactions: " + "; ".join(reactions))
        typer.echo(f"| {msg.date} |")
        typer.echo(f"- - - - - - - - - - - - - - - - - - - - - -")

    client.stop()

if __name__ == "__main__":
    app()
