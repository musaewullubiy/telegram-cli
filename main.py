import pyrogram
import typer
from pyrogram import Client
from pyrogram.errors import PeerIdInvalid, ChatIdInvalid
import hashlib
import json
import os
import config

client = pyrogram.Client(
    'my_account',
    api_id=config.api_id,
    api_hash=config.api_hash
)

app = typer.Typer()

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
                chat_id = get_chat_id(chat_id)

        client.send_message(chat_id, message)
        print("Отправлено")
    except (PeerIdInvalid, ChatIdInvalid) as e:
        print(f"Ошибка: {e}")
    finally:
        client.stop()

@app.command()
def get_chats(count: int):
    client.start()
    dialogs = client.get_dialogs(limit=count)
    chat_list = [(hash_id(str(dialog.chat.id)), str(dialog.chat.id), dialog.chat.title or dialog.chat.first_name) for dialog in dialogs]

    # Загружаем теги
    tags = load_tags()

    # Определяем максимальную ширину для каждой колонки
    hash_width = len(chat_list[-1][0])
    id_width = len(chat_list[-1][1])
    name_width = max(len(chat[2]) for chat in chat_list)
    tag_width = max(len(tag) for tag in tags.keys()) if tags else 0

    # Форматируем заголовок
    header = f"{'HASH':<{hash_width}}\t{'ID':<{id_width}}\t{'NAME':<{name_width}}\t{'TAG':<{tag_width}}"
    print(header)

    # Форматируем строки
    hashes = {}
    for chat in chat_list:
        hash_val, id_val, name_val = chat
        tag_val = next((tag for tag, chat_id in tags.items() if chat_id == id_val), '')
        print(f"{hash_val:<{hash_width}}\t{id_val:<{id_width}}\t{name_val:<{name_width}}\t{tag_val:<{tag_width}}")
        hashes[hash_val] = id_val

    save_hashes(hashes)
    client.stop()

@app.command()
def tag(chat: str, tag: str):
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
        print(f"Тег '{tag}' добавлен к чату с ID {chat_id}")
    except (PeerIdInvalid, ChatIdInvalid) as e:
        print(f"Ошибка: {e}")
    finally:
        client.stop()

@app.command()
def get_tags():
    tags = load_tags()
    if tags:
        print("Список тегов:")
        for tag, chat_id in tags.items():
            print(f"{tag}: {chat_id}")
    else:
        print("Нет тегов.")

if __name__ == "__main__":
    app()
